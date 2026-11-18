"""Remembers how a file layout was set up so the next month's file is ready in one click.

Source settings are keyed by the workbook's sheet names; mappings by the column names.
Stored in <data_dir>/templates.json and never touches the user's YAML files.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from autoinput.domain import Mapping, SourceOptions
from autoinput.infra.logging import get_logger
from autoinput.infra.settings import get_settings

log = get_logger("app")

SOURCE_KEYS = ("sheet", "header_row", "header_rows", "smart_rows", "data_start", "display_values")


def _key(prefix: str, names: list[str]) -> str:
    return prefix + hashlib.sha1("\n".join(names).encode()).hexdigest()[:16]


class TemplateMemory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().data_dir / "templates.json"

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            log.warning(f"Ignoring unreadable {self.path.name}: {e}")
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning(f"Cannot save {self.path.name}: {e}")

    def source_options(self, sheets: list[str], base: SourceOptions) -> SourceOptions | None:
        stored = self._read().get(_key("source:", sheets)) if sheets else None
        if not isinstance(stored, dict):
            return None
        try:
            update = {k: stored[k] for k in SOURCE_KEYS if k in stored}
            if isinstance(update.get("sheet"), str) and update["sheet"] not in sheets:
                update.pop("sheet")
            return SourceOptions.model_validate({**base.model_dump(), **update})
        except ValueError:
            return None

    def remember_source(self, sheets: list[str], options: SourceOptions) -> None:
        if not sheets:
            return
        data = self._read()
        data[_key("source:", sheets)] = options.model_dump(include=set(SOURCE_KEYS))
        self._write(data)

    def mapping(self, columns: list[str]) -> tuple[str, Mapping] | None:
        stored = self._read().get(_key("mapping:", sorted(columns))) if columns else None
        if not isinstance(stored, dict):
            return None
        try:
            return str(stored["profile"]), Mapping.model_validate(stored["mapping"])
        except (KeyError, ValueError):
            return None

    def remember_mapping(self, columns: list[str], profile_id: str, mapping: Mapping) -> None:
        if not columns:
            return
        data = self._read()
        data[_key("mapping:", sorted(columns))] = {
            "profile": profile_id,
            "mapping": mapping.model_dump(mode="json", exclude_defaults=True),
        }
        self._write(data)
