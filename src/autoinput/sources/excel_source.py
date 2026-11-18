from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from python_calamine import CalamineSheet, CalamineWorkbook

from autoinput.domain import Record, SourceError
from autoinput.sources.base import Source, source_registry, to_text


@dataclass
class ExcelPreview:
    columns: list[str]
    rows: list[Record]
    spans: list[tuple[int, int, int, int]]


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


@source_registry.register(".xlsx", ".xlsm", ".xls", ".xlsb", ".ods")
class ExcelSource(Source):
    label = "Excel / ODS"

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

    def sheet_preview(self, limit: int = 200) -> ExcelPreview:
        with CalamineWorkbook.from_path(str(self.path)) as wb:
            sheet = self._sheet(wb)
            rows = sheet.to_python(skip_empty_area=False, nrows=limit)
            width = max((len(row) for row in rows), default=0)
            columns = [_column_name(i + 1) for i in range(width)]
            spans = []
            for (top, left), (bottom, right) in sheet.merged_cell_ranges or []:
                if top >= len(rows) or left >= width:
                    continue
                height = min(bottom + 1, len(rows)) - top
                span_width = min(right + 1, width) - left
                if height > 1 or span_width > 1:
                    spans.append((top, left, height, span_width))
            return ExcelPreview(
                columns=columns,
                rows=[
                    Record(index=i + 1, data=dict(zip(columns, map(to_text, row), strict=False)))
                    for i, row in enumerate(rows)
                ],
                spans=spans,
            )

    def _rows(self) -> Iterator[dict[str, Any]]:
        with CalamineWorkbook.from_path(str(self.path)) as wb:
            rows = self._sheet(wb).to_python(skip_empty_area=False)
        header_idx = self.options.header_row - 1
        if len(rows) <= header_idx:
            return
        header = _unique([to_text(h) or f"Column{i + 1}" for i, h in enumerate(rows[header_idx])])
        for row in rows[header_idx + 1 :]:
            yield dict(zip(header, row, strict=False))


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return result
