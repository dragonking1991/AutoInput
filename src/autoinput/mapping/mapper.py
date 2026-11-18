import re
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
        if not mapping.fields and any(
            step.action in {"fill", "fill_all"} for step in profile.record_steps
        ):
            problems.append("Chưa ánh xạ trường dữ liệu nào")
        if mapping.profile != profile.id:
            problems.append(f"Cấu hình dành cho '{mapping.profile}', không phải '{profile.id}'")
        known_cols = set(columns) if columns is not None else None
        for fm in mapping.fields:
            if fm.field not in profile.fields:
                problems.append(f"Trường '{fm.field}' không có trong ứng dụng đích '{profile.id}'")
            if known_cols is not None and fm.source and fm.source not in known_cols:
                problems.append(f"Không thấy cột '{fm.source}' trong file")
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
            raise MappingError("Bắt buộc nhưng đang trống")
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
            names = {_norm(col), _norm(col.rsplit("/", 1)[-1])}  # "Phụ cấp / Tiền cơm"
            score = max(SequenceMatcher(None, c, n).ratio() for c in candidates for n in names)
            if score > best_score:
                best, best_score = col, score
        if best:
            suggestions[name] = best
            used.add(best)
    return suggestions


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T00:00:00)?$")
_PHONE = re.compile(r"^(\+?84|0)[\d .-]{8,13}$")
_PHONE_FIELD = re.compile(r"phone|mobile|tel|sdt|dien ?thoai|di dong")


def suggest_transforms(values: list[str], field: str, label: str = "") -> list[str]:
    """Transforms that suit the sample values, e.g. Excel dates -> dd/mm/yyyy."""
    samples = [v for v in values if v][:20]
    if not samples:
        return ["strip"]
    target = no_accents(f"{field} {label}").lower()
    if all(_ISO_DATE.match(v) for v in samples):
        return ["date:%d/%m/%Y"]
    if _PHONE_FIELD.search(target) and all(_PHONE.match(v) for v in samples):
        return ["phone_vn"]
    if any("  " in v for v in samples):
        return ["collapse_spaces"]
    return ["strip"]
