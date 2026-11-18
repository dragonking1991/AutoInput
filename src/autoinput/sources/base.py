from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from itertools import islice
from pathlib import Path
from typing import Any, ClassVar

from autoinput.core.registry import Registry
from autoinput.domain import Record, SourceError, SourceOptions
from autoinput.infra.logging import get_logger


class Source(ABC):
    """Reads a file into flat string records. Subclasses only implement `_rows`."""

    label: ClassVar[str] = ""

    def __init__(self, path: Path, options: SourceOptions | None = None) -> None:
        if not path.is_file():
            raise SourceError(f"File not found: {path}")
        self.path = path
        self.options = options or SourceOptions()
        self.log = get_logger("source")
        self._columns: list[str] | None = None

    @abstractmethod
    def _rows(self) -> Iterator[dict[str, Any]]:
        """Yield raw rows (header already applied)."""

    def _indexed_rows(self) -> Iterator[tuple[int, dict[str, Any]]]:
        """(row number shown to users, row). Defaults to the data-row ordinal."""
        return enumerate(self._rows(), start=1)

    def records(self) -> Iterator[Record]:
        try:
            for i, row in self._indexed_rows():
                data = {str(k).strip(): to_text(v) for k, v in row.items() if k is not None}
                if any(data.values()):
                    yield Record(index=i, data=data)
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(
                f"Cannot read {self.path.name}: {e}", context={"file": str(self.path)}
            ) from e

    def columns(self) -> list[str]:
        if self._columns is None:
            seen: dict[str, None] = {}
            for rec in islice(self.records(), 50):
                seen.update(dict.fromkeys(rec.data))
            self._columns = list(seen)
        return self._columns

    def preview(self, limit: int = 200) -> list[Record]:
        return list(islice(self.records(), limit))


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 123 as 123.0
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


source_registry: Registry[type[Source]] = Registry("source")
