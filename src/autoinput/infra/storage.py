from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from autoinput.domain import ConfigError, Mapping, Profile

M = TypeVar("M", bound=BaseModel)


def _load(path: Path, model: type[M]) -> M:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return model.model_validate(raw)
    except FileNotFoundError as e:
        raise ConfigError(f"File not found: {path}") from e
    except (yaml.YAMLError, ValidationError) as e:
        raise ConfigError(f"Invalid {model.__name__} file '{path.name}':\n{e}") from e


def load_profile(path: Path) -> Profile:
    return _load(path, Profile)


def load_mapping(path: Path) -> Mapping:
    return _load(path, Mapping)


def save_mapping(mapping: Mapping, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = mapping.model_dump(mode="json", exclude_defaults=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def list_profiles(directory: Path) -> dict[str, Path]:
    """Profile id -> file path. Invalid files are skipped so one bad file can't break the UI."""
    found: dict[str, Path] = {}
    for path in sorted(directory.glob("*.y*ml")):
        try:
            found[load_profile(path).id] = path
        except ConfigError:
            continue
    return found
