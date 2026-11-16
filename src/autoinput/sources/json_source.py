import json
from collections.abc import Iterator
from typing import Any

from autoinput.domain import SourceError
from autoinput.sources.base import Source, source_registry


@source_registry.register(".json", ".jsonl", ".ndjson")
class JsonSource(Source):
    label = "JSON / JSON Lines"

    def _rows(self) -> Iterator[dict[str, Any]]:
        if self.path.suffix.lower() in {".jsonl", ".ndjson"}:
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        yield flatten(json.loads(line))
            return

        data = json.loads(self.path.read_text(encoding="utf-8"))
        items = self._locate_list(data)
        for item in items:
            yield flatten(item) if isinstance(item, dict) else {"value": item}

    def _locate_list(self, data: Any) -> list[Any]:
        if self.options.record_path:
            for key in self.options.record_path.split("."):
                if not isinstance(data, dict) or key not in data:
                    raise SourceError(f"record_path '{self.options.record_path}' not found")
                data = data[key]
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Auto-detect: first list of objects inside the root object.
            for value in data.values():
                if isinstance(value, list):
                    return value
            return [data]
        raise SourceError("JSON root must be an object or an array")


def flatten(obj: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """{"a": {"b": 1}} -> {"a.b": 1}. Lists are kept as JSON text."""
    out: dict[str, Any] = {}
    for key, value in obj.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, f"{name}."))
        elif isinstance(value, list):
            out[name] = json.dumps(value, ensure_ascii=False)
        else:
            out[name] = value
    return out
