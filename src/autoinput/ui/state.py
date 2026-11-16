"""Single source of truth shared by all wizard pages."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from autoinput.domain import Mapping, Profile, Record, SourceOptions
from autoinput.mapping import Mapper
from autoinput.sources import Source, open_source

MAX_ROWS_IN_MEMORY = 100_000


class AppState(QObject):
    source_changed = Signal()
    mapping_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.source: Source | None = None
        self.records: list[Record] = []
        self.profile: Profile | None = None
        self.mapping: Mapping | None = None

    def load_source(self, path: Path, options: SourceOptions | None = None) -> None:
        source = open_source(path, options)
        self.records = source.preview(MAX_ROWS_IN_MEMORY)
        self.source = source
        self.source_changed.emit()

    @property
    def columns(self) -> list[str]:
        return self.source.columns() if self.source else []

    def set_mapping(self, profile: Profile | None, mapping: Mapping | None) -> None:
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
