from collections.abc import Iterator
from typing import Any

from python_calamine import CalamineWorkbook

from autoinput.domain import SourceError
from autoinput.sources.base import Source, source_registry, to_text


@source_registry.register(".xlsx", ".xlsm", ".xls", ".xlsb", ".ods")
class ExcelSource(Source):
    label = "Excel / ODS"

    def sheet_names(self) -> list[str]:
        return list(CalamineWorkbook.from_path(str(self.path)).sheet_names)

    def _rows(self) -> Iterator[dict[str, Any]]:
        wb = CalamineWorkbook.from_path(str(self.path))
        sheet_ref = self.options.sheet
        try:
            sheet = (
                wb.get_sheet_by_index(sheet_ref)
                if isinstance(sheet_ref, int)
                else wb.get_sheet_by_name(sheet_ref)
            )
        except Exception as e:
            raise SourceError(f"Sheet '{sheet_ref}' not found. Sheets: {wb.sheet_names}") from e

        rows = sheet.to_python(skip_empty_area=False)
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
