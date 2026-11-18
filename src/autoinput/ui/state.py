"""Single source of truth shared by all wizard pages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, Signal

from autoinput.domain import Mapping, Profile, Record, SourceError, SourceOptions
from autoinput.engine.control import RunControl
from autoinput.infra.templates import TemplateMemory
from autoinput.mapping import Mapper
from autoinput.sources import Source, open_source
from autoinput.sources.excel_source import ExcelPreview, ExcelSource

MAX_ROWS_IN_MEMORY = 100_000


@dataclass
class SourceData:
    source: Source
    records: list[Record]
    sheets: list[str]
    excel_preview: ExcelPreview | None = None
    note: str = ""


AutoLayout = Literal["off", "remember", "detect"]


def read_source(
    path: Path, options: SourceOptions | None, control: RunControl, auto: AutoLayout = "off"
) -> SourceData:
    """`auto`: "remember" reuses settings saved for this workbook, else detects the table;
    "detect" always re-detects. Both only change Excel options."""
    source = open_source(path, options)
    note = ""
    if auto != "off" and isinstance(source, ExcelSource):
        sheets = source.sheet_names()
        remembered = (
            TemplateMemory().source_options(sheets, source.options) if auto == "remember" else None
        )
        if remembered is not None:
            source = open_source(path, remembered)
            note = "Đã dùng lại thiết lập đã nhớ cho file có cùng cấu trúc"
        else:
            source = open_source(path, source.detect_options())
            note = "Đã tự nhận diện bảng"
    control.checkpoint()
    records: list[Record] = []
    for record in source.records():
        control.checkpoint()
        if len(records) == MAX_ROWS_IN_MEMORY:
            raise SourceError(
                f"File vượt giới hạn {MAX_ROWS_IN_MEMORY:,} dòng của giao diện. "
                "Hãy chia nhỏ file hoặc dùng CLI; chưa có dòng nào được nhập."
            )
        records.append(record)
    control.checkpoint()
    source.columns()
    sheets = source.sheet_names() if isinstance(source, ExcelSource) else []
    preview = source.sheet_preview() if isinstance(source, ExcelSource) else None
    control.checkpoint()
    return SourceData(source, records, sheets, preview, note)


class AppState(QObject):
    source_changed = Signal()
    mapping_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.source: Source | None = None
        self.records: list[Record] = []
        self.sheets: list[str] = []
        self.profile: Profile | None = None
        self.mapping: Mapping | None = None
        self.source_busy = False
        self.validation_pending = False
        self.validated = False

    def load_source(self, path: Path, options: SourceOptions | None = None) -> None:
        data = read_source(path, options, RunControl())
        self.set_source(data)

    def set_source(self, data: SourceData | None) -> None:
        self.validated = False
        self.records = data.records if data else []
        self.sheets = data.sheets if data else []
        self.source = data.source if data else None
        self.source_changed.emit()

    @property
    def columns(self) -> list[str]:
        return self.source.columns() if self.source else []

    def set_mapping(self, profile: Profile | None, mapping: Mapping | None) -> None:
        self.validated = False
        self.profile, self.mapping = profile, mapping
        self.mapping_changed.emit()

    def mapping_problems(self) -> list[str]:
        if not (self.profile and self.mapping):
            return ["Chưa chọn ứng dụng đích"]
        return Mapper.check(self.mapping, self.profile, self.columns)

    def mapper(self) -> Mapper | None:
        if self.profile and self.mapping and not self.mapping_problems():
            return Mapper(self.mapping, self.profile)
        return None
