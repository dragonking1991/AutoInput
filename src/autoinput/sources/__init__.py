from pathlib import Path

from autoinput.domain import SourceError, SourceOptions
from autoinput.sources import csv_source, excel_source, json_source, xml_source  # noqa: F401 - register
from autoinput.sources.base import Source, source_registry


def open_source(path: Path, options: SourceOptions | None = None) -> Source:
    ext = path.suffix.lower()
    if ext not in source_registry:
        raise SourceError(
            f"Unsupported file type '{ext}'",
            context={"supported": source_registry.keys()},
        )
    return source_registry.get(ext)(path, options)


def supported_extensions() -> list[str]:
    return source_registry.keys()


__all__ = ["Source", "open_source", "source_registry", "supported_extensions"]
