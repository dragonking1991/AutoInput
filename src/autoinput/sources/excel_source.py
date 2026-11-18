from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import pairwise
from statistics import median
from typing import Any

from python_calamine import CalamineSheet, CalamineWorkbook

from autoinput.domain import Record, SourceError, SourceOptions
from autoinput.sources.base import Source, source_registry, to_text
from autoinput.sources.excel_format import SheetStyles, format_value, read_styles

Merge = tuple[int, int, int, int]  # top, left, bottom, right (0-based, inclusive)

STYLE_ROWS = 500
FOOTER_WORDS = (
    "tổng", "cộng", "người lập", "kế toán", "thủ trưởng", "giám đốc", "hiệu trưởng",
    "thủ quỹ", "total", "grand total",
)  # fmt: skip


@dataclass
class TableLayout:
    """How a sheet maps to records. Rows are 1-based sheet rows."""

    header: tuple[int, int]
    columns: list[str]
    data_rows: list[int]
    roles: dict[int, tuple[str, str]] = field(default_factory=dict)  # row -> (role, reason)

    def summary(self) -> str:
        top, bottom = self.header
        parts = [f"tiêu đề dòng {top}" + (f"–{bottom}" if bottom > top else "")]
        if self.data_rows:
            parts.append(
                f"{len(self.data_rows)} dòng dữ liệu ({self.data_rows[0]}–{self.data_rows[-1]})"
            )
        else:
            parts.append("chưa có dòng dữ liệu")
        skipped = [r for r, (role, reason) in self.roles.items() if role == "skip" and reason]
        if skipped:
            parts.append("bỏ qua " + _ranges(skipped))
        return " • ".join(parts)


@dataclass
class ExcelPreview:
    columns: list[str]
    rows: list[Record]
    spans: list[tuple[int, int, int, int]]
    styles: SheetStyles = field(default_factory=SheetStyles)
    layout: TableLayout | None = None


def _ranges(rows: list[int], limit: int = 6) -> str:
    groups: list[list[int]] = []
    for row in sorted(rows):
        if groups and row == groups[-1][-1] + 1:
            groups[-1].append(row)
        else:
            groups.append([row])
    text = [f"{g[0]}" if len(g) == 1 else f"{g[0]}–{g[-1]}" for g in groups[:limit]]
    return ", ".join(text) + ("…" if len(groups) > limit else "")


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _filled(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not _as_int(value)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        return int(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*\(?\s*(\d{1,3})\s*\)?\s*", value)
        return int(match.group(1)) if match else None
    return None


def _is_numbering(row: list[Any]) -> bool:
    values = [v for v in row if _filled(v)]
    numbers = [_as_int(v) for v in values]
    return (
        len(values) >= 3
        and all(n is not None for n in numbers)
        and all(a < b for a, b in pairwise(numbers))  # type: ignore[operator]
    )


def _is_footer(row: list[Any]) -> bool:
    for value in [v for v in row if _filled(v)][:3]:
        if isinstance(value, str):
            text = " ".join(value.lower().split()).strip(" :.-")
            if any(text == w or text.startswith(w + " ") for w in FOOTER_WORDS):
                return True
    return False


def _is_section(row: list[Any], typical: float) -> bool:
    values = [v for v in row if _filled(v)]
    return (
        typical >= 4
        and len(values) <= max(2, typical * 0.4)
        and not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
    )


@source_registry.register(".xlsx", ".xlsm", ".xls", ".xlsb", ".ods")
class ExcelSource(Source):
    label = "Excel / ODS"

    _cache: tuple[str, list[list[Any]], list[Merge]] | None = None
    _styles_cache: SheetStyles | None = None
    _layout_cache: TableLayout | None = None
    _formats: dict[int, str] | None = None

    def sheet_names(self) -> list[str]:
        with CalamineWorkbook.from_path(str(self.path)) as wb:
            return list(wb.sheet_names)

    def _sheet(self, wb: CalamineWorkbook) -> CalamineSheet:
        sheet_ref = self.options.sheet
        try:
            return (
                wb.get_sheet_by_index(sheet_ref)
                if isinstance(sheet_ref, int)
                else wb.get_sheet_by_name(sheet_ref)
            )
        except Exception as e:
            raise SourceError(f"Sheet '{sheet_ref}' not found. Sheets: {wb.sheet_names}") from e

    def _load(self) -> tuple[str, list[list[Any]], list[Merge]]:
        if self._cache is None:
            with CalamineWorkbook.from_path(str(self.path)) as wb:
                sheet = self._sheet(wb)
                rows = sheet.to_python(skip_empty_area=False)
                merges = [
                    (top, left, bottom, right)
                    for (top, left), (bottom, right) in sheet.merged_cell_ranges or []
                ]
                self._cache = (sheet.name, rows, merges)
        return self._cache

    def _width(self) -> int:
        return max((len(row) for row in self._load()[1]), default=0)

    def styles(self) -> SheetStyles:
        if self._styles_cache is None:
            name, rows, _ = self._load()
            start = self.options.data_start or self.options.header_row + self.options.header_rows
            nrows = min(len(rows), max(STYLE_ROWS, start + STYLE_ROWS))
            self._styles_cache = read_styles(self.path, name, nrows, self._width())
        return self._styles_cache

    def display(self, row: int, col: int, value: Any) -> str:
        """Cell text as Excel shows it (0-based coordinates)."""
        styles = self.styles()
        fmt = styles.number_format(row, col) or self._column_formats().get(col)
        return format_value(
            value, fmt, self.options.thousands_separator, self.options.decimal_separator
        )

    def _column_formats(self) -> dict[int, str]:
        if self._formats is None:
            counts: dict[int, dict[str, int]] = {}
            for (_, col), style in self.styles().cells.items():
                if style.number_format not in {"General", "@"}:
                    bucket = counts.setdefault(col, {})
                    bucket[style.number_format] = bucket.get(style.number_format, 0) + 1
            self._formats = {c: max(b, key=b.__getitem__) for c, b in counts.items()}
        return self._formats

    def sheet_preview(self, limit: int = STYLE_ROWS) -> ExcelPreview:
        _, all_rows, merges = self._load()
        rows = all_rows[:limit]
        width = self._width()
        columns = [_column_name(i + 1) for i in range(width)]
        spans = []
        for top, left, bottom, right in merges:
            if top >= len(rows) or left >= width:
                continue
            height = min(bottom + 1, len(rows)) - top
            span_width = min(right + 1, width) - left
            if height > 1 or span_width > 1:
                spans.append((top, left, height, span_width))
        styles = self.styles()
        return ExcelPreview(
            columns=columns,
            rows=[
                Record(
                    index=r + 1,
                    data={columns[c]: self.display(r, c, value) for c, value in enumerate(row)},
                )
                for r, row in enumerate(rows)
            ],
            spans=spans,
            styles=styles,
            layout=self.layout(),
        )

    def _header_names(self, rows: list[list[Any]], merges: list[Merge]) -> list[str]:
        width = self._width()
        top = self.options.header_row - 1
        bottom = min(top + self.options.header_rows - 1, len(rows) - 1)
        fill: dict[tuple[int, int], Any] = {}
        if bottom > top:
            for m_top, m_left, m_bottom, m_right in merges:
                if m_bottom < top or m_top > bottom:
                    continue
                for r in range(max(m_top, top), min(m_bottom, bottom) + 1):
                    for c in range(m_left, min(m_right, width - 1) + 1):
                        fill[(r, c)] = rows[m_top][m_left]
        names = []
        for c in range(width):
            parts: list[str] = []
            for r in range(top, bottom + 1):
                value = fill.get((r, c), rows[r][c] if c < len(rows[r]) else None)
                text = " ".join(to_text(value).split())
                if text and text not in parts:
                    parts.append(text)
            names.append(" / ".join(parts) or f"Column{c + 1}")
        return _unique(names)

    def _data_grid(self) -> list[list[Any]]:
        _, rows, merges = self._load()
        if not self.options.smart_rows:
            return rows
        start = self.options.header_row + self.options.header_rows - 1
        rows = [list(row) for row in rows]
        for top, left, bottom, _right in merges:
            if top < start or bottom == top:
                continue
            for r in range(top + 1, min(bottom, len(rows) - 1) + 1):
                if left < len(rows[r]) and not _filled(rows[r][left]):
                    rows[r][left] = rows[top][left]
        return rows

    def layout(self) -> TableLayout:
        if self._layout_cache is not None:
            return self._layout_cache
        _, raw_rows, merges = self._load()
        rows = self._data_grid()
        opts = self.options
        h_top = opts.header_row
        h_bottom = min(h_top + opts.header_rows - 1, max(len(rows), h_top))
        columns = self._header_names(raw_rows, merges) if len(rows) >= h_top else []
        start = opts.data_start or h_bottom + 1
        end = min(opts.data_end or len(rows), len(rows))
        counts = [sum(map(_filled, rows[r - 1])) for r in range(start, end + 1)]
        typical = median([n for n in counts if n]) if any(counts) else 0
        roles: dict[int, tuple[str, str]] = {}
        data_rows: list[int] = []
        footer = seen_data = False
        for n in range(1, len(rows) + 1):
            row = rows[n - 1]
            if n < h_top:
                roles[n] = ("title", "")
            elif n <= h_bottom:
                roles[n] = ("header", "")
            elif n < start:
                roles[n] = ("skip", "trước dòng bắt đầu dữ liệu")
            elif n > end:
                roles[n] = ("skip", "sau dòng kết thúc dữ liệu")
            elif not any(map(_filled, row)):
                roles[n] = ("skip", "")
            elif n in opts.include_rows:
                roles[n] = ("data", "")
            elif n in opts.skip_rows:
                roles[n] = ("skip", "bạn chọn bỏ qua")
            elif opts.smart_rows and footer:
                roles[n] = ("skip", "sau dòng tổng / chữ ký")
            elif opts.smart_rows and seen_data and _is_footer(row):
                footer = True
                roles[n] = ("skip", "dòng tổng / chữ ký")
            elif opts.smart_rows and not seen_data and _is_numbering(row):
                roles[n] = ("skip", "dòng đánh số cột")
            elif opts.smart_rows and _is_section(row, typical):
                roles[n] = ("skip", "dòng nhóm / mục")
            else:
                roles[n] = ("data", "")
                seen_data = True
            if roles[n][0] == "data":
                data_rows.append(n)
        self._layout_cache = TableLayout((h_top, h_bottom), columns, data_rows, roles)
        return self._layout_cache

    def detect_options(self) -> SourceOptions:
        """Best guess for header rows and smart filtering; the user can override it."""
        _, rows, merges = self._load()
        best, score = 0, 1
        for r, row in enumerate(rows[:30]):
            texts = sum(map(_is_text, row))
            if texts > score:
                best, score = r, texts
        depth = 1
        for top, left, bottom, right in merges:
            if top != best:
                continue
            depth = max(depth, bottom - top + 1)
            below = rows[best + 1] if best + 1 < len(rows) else []
            if right > left and any(_is_text(v) for v in below[left : right + 1]):
                depth = max(depth, 2)
        return self.options.model_copy(
            update={
                "header_row": best + 1,
                "header_rows": min(depth, 3),
                "smart_rows": True,
                "data_start": None,
                "data_end": None,
                "skip_rows": [],
                "include_rows": [],
            }
        )

    def _indexed_rows(self) -> Iterator[tuple[int, dict[str, Any]]]:
        layout = self.layout()
        rows = self._data_grid()
        for n in layout.data_rows:
            row = rows[n - 1]
            values = (
                [self.display(n - 1, c, v) for c, v in enumerate(row)]
                if self.options.display_values
                else row
            )
            yield n, dict(zip(layout.columns, values, strict=False))

    def _rows(self) -> Iterator[dict[str, Any]]:
        for _, row in self._indexed_rows():
            yield row


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return result
