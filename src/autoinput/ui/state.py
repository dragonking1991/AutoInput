"""Single source of truth shared by all wizard pages."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from autoinput.domain import Mapping, Profile, Record, SourceError, SourceOptions
from autoinput.engine.control import RunControl
from autoinput.mapping import Mapper
from autoinput.sources import Source, open_source

MAX_ROWS_IN_MEMORY = 100_000


@dataclass
class SourceData:
    source: Source
    records: list[Record]
    sheets: list[str]


def read_source(path: Path, options: SourceOptions | None, control: RunControl) -> SourceData:
    from autoinput.sources.excel_source import ExcelSource

    source = open_source(path, options)
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
    return SourceData(source, records, sheets)


class AppState(QObject):
    source_changed = Signal()
    mapping_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.source: Source | None = None
        self.records: list[Record] = []
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
