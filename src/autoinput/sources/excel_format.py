"""Read Excel cell styles and render numbers the way Excel displays them.

Formatting is best-effort: any failure returns empty styles so loading never breaks.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from autoinput.infra.logging import get_logger

log = get_logger("source")

THEME_COLORS = [
    "#FFFFFF", "#000000", "#E7E6E6", "#44546A", "#4472C4",
    "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47",
]  # fmt: skip


@dataclass(frozen=True, slots=True)
class CellStyle:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size: float | None = None
    font: str | None = None
    color: str | None = None
    background: str | None = None
    horizontal: str | None = None  # left | center | right
    vertical: str | None = None  # top | center | bottom
    wrap: bool = False
    number_format: str = "General"
    borders: tuple[bool, bool, bool, bool] = (False, False, False, False)  # top right bottom left


@dataclass
class SheetStyles:
    cells: dict[tuple[int, int], CellStyle] = field(default_factory=dict)  # 0-based
    column_widths: dict[int, int] = field(default_factory=dict)  # pixels at 96 dpi
    row_heights: dict[int, int] = field(default_factory=dict)  # pixels at 96 dpi
    hidden_rows: set[int] = field(default_factory=set)
    hidden_columns: set[int] = field(default_factory=set)
    default_width: int = 64
    default_height: int = 20

    def number_format(self, row: int, col: int) -> str | None:
        style = self.cells.get((row, col))
        return style.number_format if style else None


def _chars_to_px(chars: float) -> int:
    return max(0, round(chars * 7 + 5)) if chars else 0


def _points_to_px(points: float) -> int:
    return round(points * 96 / 72)


def read_styles(path: Path, sheet: str, nrows: int, ncols: int) -> SheetStyles:
    try:
        suffix = path.suffix.lower()
        if suffix == ".xls":
            return _read_xls(path, sheet, nrows, ncols)
        if suffix in {".xlsx", ".xlsm"}:
            return _read_xlsx(path, sheet, nrows, ncols)
    except Exception as e:
        log.warning(f"Cannot read Excel formatting of {path.name}: {e}")
    return SheetStyles()


# ─── .xls (BIFF) ────────────────────────────────────────────────────────────

_XLS_HORIZONTAL = {1: "left", 2: "center", 3: "right", 5: "left", 6: "center", 7: "left"}
_XLS_VERTICAL = {0: "top", 1: "center", 2: "bottom"}


def _rgb(value: tuple[int, int, int] | None) -> str | None:
    return "#{:02X}{:02X}{:02X}".format(*value) if value else None


def _read_xls(path: Path, sheet: str, nrows: int, ncols: int) -> SheetStyles:
    import xlrd

    book = xlrd.open_workbook(str(path), formatting_info=True, on_demand=True)
    try:
        sh = book.sheet_by_name(sheet)
        styles = SheetStyles()
        cache: dict[int, CellStyle] = {}
        for r in range(min(nrows, sh.nrows)):
            for c in range(min(ncols, sh.row_len(r))):
                xf_index = sh.cell_xf_index(r, c)
                if xf_index not in cache:
                    cache[xf_index] = _xls_style(book, book.xf_list[xf_index])
                styles.cells[(r, c)] = cache[xf_index]
        default_width = getattr(sh, "defcolwidth", None) or 8.43
        styles.default_width = _chars_to_px(default_width)
        for c in range(ncols):
            styles.column_widths[c] = round(sh.computed_column_width(c) / 256 * 7 + 5)
            info = sh.colinfo_map.get(c)
            if info is not None and info.hidden:
                styles.hidden_columns.add(c)
        if sh.default_row_height:
            styles.default_height = _points_to_px(sh.default_row_height / 20)
        for r in range(nrows):
            row_info = sh.rowinfo_map.get(r)
            if row_info is None:
                continue
            if row_info.hidden:
                styles.hidden_rows.add(r)
            elif row_info.height:
                styles.row_heights[r] = _points_to_px(row_info.height / 20)
        return styles
    finally:
        book.release_resources()


def _xls_style(book: Any, xf: Any) -> CellStyle:
    font = book.font_list[xf.font_index]
    color = _rgb(book.colour_map.get(font.colour_index))
    background = None
    if xf.background.fill_pattern:
        background = _rgb(book.colour_map.get(xf.background.pattern_colour_index))
    border = xf.border
    fmt = book.format_map.get(xf.format_key)
    return CellStyle(
        bold=bool(font.bold),
        italic=bool(font.italic),
        underline=bool(font.underline_type),
        size=font.height / 20 if font.height else None,
        font=font.name or None,
        color=None if color == "#000000" else color,
        background=None if background == "#FFFFFF" else background,
        horizontal=_XLS_HORIZONTAL.get(xf.alignment.hor_align),
        vertical=_XLS_VERTICAL.get(xf.alignment.vert_align),
        wrap=bool(xf.alignment.text_wrapped),
        number_format=fmt.format_str if fmt else "General",
        borders=(
            bool(border.top_line_style),
            bool(border.right_line_style),
            bool(border.bottom_line_style),
            bool(border.left_line_style),
        ),
    )


# ─── .xlsx / .xlsm ──────────────────────────────────────────────────────────


def _xlsx_color(color: Any) -> str | None:
    if color is None:
        return None
    try:
        if color.type == "rgb" and isinstance(color.rgb, str) and len(color.rgb) >= 6:
            return "#" + color.rgb[-6:].upper()
        if color.type == "theme" and isinstance(color.theme, int):
            base = THEME_COLORS[color.theme % len(THEME_COLORS)]
            return _tint(base, float(color.tint or 0))
        if color.type == "indexed" and isinstance(color.indexed, int):
            from openpyxl.styles.colors import COLOR_INDEX

            if color.indexed < len(COLOR_INDEX):
                return "#" + str(COLOR_INDEX[color.indexed])[-6:]
    except Exception:
        return None
    return None


def _tint(hex_color: str, tint: float) -> str:
    if not tint:
        return hex_color
    channels = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    if tint < 0:
        channels = [round(c * (1 + tint)) for c in channels]
    else:
        channels = [round(c + (255 - c) * tint) for c in channels]
    return "#{:02X}{:02X}{:02X}".format(*channels)


def _xlsx_style(cell: Any) -> CellStyle:
    font, fill, alignment, border = cell.font, cell.fill, cell.alignment, cell.border
    background = None
    if fill is not None and fill.fill_type == "solid":
        background = _xlsx_color(fill.fgColor)
    color = _xlsx_color(font.color) if font is not None else None
    horizontal = alignment.horizontal if alignment is not None else None
    if horizontal in {"centerContinuous", "distributed"}:
        horizontal = "center"
    elif horizontal in {"general", "fill", "justify"}:
        horizontal = None
    vertical = alignment.vertical if alignment is not None else None
    if vertical in {"justify", "distributed"}:
        vertical = "center"
    return CellStyle(
        bold=bool(font and font.b),
        italic=bool(font and font.i),
        underline=bool(font and font.u),
        size=float(font.sz) if font is not None and font.sz else None,
        font=font.name if font is not None else None,
        color=None if color == "#000000" else color,
        background=None if background in {"#FFFFFF", "#000000"} else background,
        horizontal=horizontal,
        vertical=vertical,
        wrap=bool(alignment is not None and alignment.wrap_text),
        number_format=cell.number_format or "General",
        borders=tuple(  # type: ignore[arg-type]
            bool(border is not None and getattr(border, side).style)
            for side in ("top", "right", "bottom", "left")
        ),
    )


def _read_xlsx(path: Path, sheet: str, nrows: int, ncols: int) -> SheetStyles:
    from openpyxl import load_workbook

    styles = SheetStyles()
    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        cache: dict[int, CellStyle] = {}
        for r, row in enumerate(ws.iter_rows(min_row=1, max_row=nrows, max_col=ncols)):
            for c, cell in enumerate(row):
                # Read-only cells keep the id in ``_style_id``; empty cells have no style.
                style_id = getattr(cell, "_style_id", getattr(cell, "style_id", None))
                if style_id is None or getattr(cell, "font", None) is None:
                    continue
                if style_id not in cache:
                    cache[style_id] = _xlsx_style(cell)
                styles.cells[(r, c)] = cache[style_id]
        worksheet_path = getattr(ws, "_worksheet_path", None)
    finally:
        wb.close()
    if worksheet_path:
        _read_xlsx_sizes(path, worksheet_path.lstrip("/"), nrows, ncols, styles)
    return styles


def _iter_elements(stream: Any) -> Iterator[Any]:
    from defusedxml.ElementTree import iterparse

    for _event, element in iterparse(stream, events=("start",)):
        yield element


def _read_xlsx_sizes(path: Path, member: str, nrows: int, ncols: int, styles: SheetStyles) -> None:
    default_width = 8.43
    with zipfile.ZipFile(path) as archive, archive.open(member) as stream:
        for element in _iter_elements(stream):
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "sheetFormatPr":
                if element.get("defaultColWidth"):
                    default_width = float(element.get("defaultColWidth"))
                elif element.get("baseColWidth"):
                    default_width = float(element.get("baseColWidth")) + 0.71
                if element.get("defaultRowHeight"):
                    styles.default_height = _points_to_px(float(element.get("defaultRowHeight")))
            elif tag == "col":
                first, last = int(element.get("min", 1)) - 1, int(element.get("max", 1)) - 1
                for c in range(first, min(last, ncols - 1) + 1):
                    if element.get("width"):
                        styles.column_widths[c] = _chars_to_px(float(element.get("width")))
                    if element.get("hidden") in {"1", "true"}:
                        styles.hidden_columns.add(c)
            elif tag == "row":
                r = int(element.get("r", 0)) - 1
                if r >= nrows:
                    break
                if element.get("hidden") in {"1", "true"}:
                    styles.hidden_rows.add(r)
                elif element.get("ht") and element.get("customHeight") in {"1", "true"}:
                    styles.row_heights[r] = _points_to_px(float(element.get("ht")))
    styles.default_width = _chars_to_px(default_width)


# ─── Display values ─────────────────────────────────────────────────────────

_BUILTIN_FORMATS = {"0": "0", "1": "0", "3": "#,##0"}
_DATE_TOKEN = re.compile(r"yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|am/pm", re.IGNORECASE)
_LITERAL = re.compile(r'"([^"]*)"|\\(.)|_.|\*.|\[[^\]]*\]')


def _clean_section(section: str) -> str:
    def literal(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            return match.group(1)
        if match.group(2) is not None:
            return match.group(2)
        return ""

    return _LITERAL.sub(literal, section)


def is_date_format(fmt: str) -> bool:
    cleaned = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', "", fmt.split(";")[0]).lower()
    return bool(re.search(r"[dy]|h.*m|m.*s", cleaned)) and "#" not in cleaned


def _format_date(value: date | datetime | time, fmt: str) -> str:
    section = re.sub(r"\[[^\]]*\]", "", fmt.split(";")[0])
    tokens = list(_DATE_TOKEN.finditer(section))
    result, last = [], 0
    for i, match in enumerate(tokens):
        result.append(_clean_section(section[last : match.start()]))
        token = match.group(0).lower()
        if token in {"m", "mm"}:
            prev = tokens[i - 1].group(0).lower() if i else ""
            nxt = tokens[i + 1].group(0).lower() if i + 1 < len(tokens) else ""
            if prev.startswith("h") or nxt.startswith("s"):
                token = "min" + token
        result.append(_date_part(value, token))
        last = match.end()
    result.append(_clean_section(section[last:]))
    return "".join(result).strip()


def _date_part(value: date | datetime | time, token: str) -> str:
    hour = getattr(value, "hour", 0)
    minute = getattr(value, "minute", 0)
    second = getattr(value, "second", 0)
    year, month, day = (
        (value.year, value.month, value.day) if isinstance(value, date) else (1900, 1, 1)
    )
    parts = {
        "yyyy": f"{year:04d}",
        "yy": f"{year % 100:02d}",
        "mmmm": date(2000, month, 1).strftime("%B"),
        "mmm": date(2000, month, 1).strftime("%b"),
        "mm": f"{month:02d}",
        "m": str(month),
        "dddd": date(year, month, day).strftime("%A"),
        "ddd": date(year, month, day).strftime("%a"),
        "dd": f"{day:02d}",
        "d": str(day),
        "hh": f"{hour:02d}",
        "h": str(hour),
        "minmm": f"{minute:02d}",
        "minm": str(minute),
        "ss": f"{second:02d}",
        "s": str(second),
        "am/pm": "AM" if hour < 12 else "PM",
    }
    return parts[token]


def format_value(value: Any, fmt: str | None, thousands: str = ".", decimal: str = ",") -> str:
    """Render a cell value as Excel shows it. Unsupported formats fall back to plain text."""
    from autoinput.sources.base import to_text

    fmt = _BUILTIN_FORMATS.get(fmt or "", fmt or "General")
    if value is None or isinstance(value, (str, bool)) or fmt in {"General", "@"}:
        return to_text(value)
    try:
        if isinstance(value, (datetime, date, time)):
            return _format_date(value, fmt) if is_date_format(fmt) else to_text(value)
        if not isinstance(value, (int, float)):
            return to_text(value)
        return _format_number(float(value), fmt, thousands, decimal) or to_text(value)
    except Exception:
        return to_text(value)


def _format_number(value: float, fmt: str, thousands: str, decimal: str) -> str | None:
    sections = fmt.split(";")
    section = sections[0]
    negative = value < 0
    if negative and len(sections) > 1 and sections[1].strip():
        section, value = sections[1], -value
        negative = False
    section = _clean_section(section)
    match = re.search(r"[#0?][#0?,]*(?:\.[#0?]*)?|\.[#0?]+", section)
    if not match or re.search(r"[eE][+-]|/", section):
        return None
    pattern = match.group(0)
    if "%" in section:
        value *= 100
    integer_part, _, fraction_part = pattern.partition(".")
    trailing_commas = len(integer_part) - len(integer_part.rstrip(","))
    integer_part = integer_part.rstrip(",")
    value /= 1000**trailing_commas
    max_decimals = len(fraction_part)
    min_decimals = fraction_part.count("0")
    quantum = Decimal(1).scaleb(-max_decimals)
    number = Decimal(repr(abs(value))).quantize(quantum, rounding=ROUND_HALF_UP)
    whole, _, frac = f"{number:f}".partition(".")
    frac = frac.rstrip("0").ljust(min_decimals, "0") if max_decimals else ""
    whole = whole.zfill(integer_part.count("0")) if integer_part.count("0") else whole
    if not integer_part.count("0") and whole == "0":
        whole = ""
    if "," in integer_part:
        groups: list[str] = []
        while len(whole) > 3:
            whole, groups = whole[:-3], [whole[-3:], *groups]
        whole = thousands.join([whole, *groups]) if whole else thousands.join(groups)
    text = whole + (decimal + frac if frac else "")
    if not text:
        text = "0"
    if negative and number != 0:
        text = "-" + text
    return (section[: match.start()] + text + section[match.end() :]).strip()
