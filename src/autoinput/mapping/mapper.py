from collections.abc import Iterable, Iterator
from difflib import SequenceMatcher

from autoinput.domain import (
    ConfigError,
    FieldMap,
    MappedRecord,
    Mapping,
    MappingError,
    Profile,
    Record,
)
from autoinput.transforms import apply_transforms, validate_specs
from autoinput.transforms.builtins import no_accents


class Mapper:
    """Applies a Mapping to records. Collects every field error instead of failing fast."""

    def __init__(self, mapping: Mapping, profile: Profile) -> None:
        problems = self.check(mapping, profile)
        if problems:
            raise ConfigError("Mapping is not valid:\n- " + "\n- ".join(problems))
        self.mapping = mapping
        self.profile = profile

    @staticmethod
    def check(
        mapping: Mapping, profile: Profile, columns: Iterable[str] | None = None
    ) -> list[str]:
        problems: list[str] = []
        if mapping.profile != profile.id:
            problems.append(f"Mapping targets profile '{mapping.profile}', not '{profile.id}'")
        known_cols = set(columns) if columns is not None else None
        for fm in mapping.fields:
            if fm.field not in profile.fields:
                problems.append(f"Field '{fm.field}' does not exist in profile '{profile.id}'")
            if known_cols is not None and fm.source and fm.source not in known_cols:
                problems.append(f"Column '{fm.source}' not found in file")
            problems.extend(f"{fm.field}: {p}" for p in validate_specs(fm.transforms))
        return problems

    def apply(self, record: Record) -> MappedRecord:
        result = MappedRecord(record=record)
        for fm in self.mapping.fields:
            try:
                result.values[fm.field] = self._value(fm, record)
            except MappingError as e:
                result.errors[fm.field] = e.message
        return result

    def apply_all(self, records: Iterable[Record]) -> Iterator[MappedRecord]:
        return (self.apply(r) for r in records)

    @staticmethod
    def _value(fm: FieldMap, record: Record) -> str:
        raw = fm.const if fm.const is not None else record.data.get(fm.source or "", "")
        value = apply_transforms(raw, fm.transforms) if raw else ""
        value = value or fm.default
        if fm.required and not value:
            raise MappingError("Required value is empty")
        return value


def _norm(text: str) -> str:
    return "".join(c for c in no_accents(text).lower() if c.isalnum())


def suggest_mapping(columns: list[str], profile: Profile, threshold: float = 0.6) -> dict[str, str]:
    """Best-guess field -> column by fuzzy-matching field names/labels (accent-insensitive)."""
    suggestions: dict[str, str] = {}
    used: set[str] = set()
    for name, spec in profile.fields.items():
        candidates = [_norm(name), _norm(spec.label)] if spec.label else [_norm(name)]
        best, best_score = None, threshold
        for col in columns:
            if col in used:
                continue
            score = max(SequenceMatcher(None, c, _norm(col)).ratio() for c in candidates)
            if score > best_score:
                best, best_score = col, score
        if best:
            suggestions[name] = best
            used.add(best)
    return suggestions
