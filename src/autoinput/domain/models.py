"""Pure data models shared by every layer. No I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autoinput.core.keys import parse_combo

# ─── Source side ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Record:
    """One input row. `index` is 1-based, matching what users see in Excel."""

    index: int
    data: dict[str, str]


class SourceOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encoding: str | None = None  # None = auto-detect
    delimiter: str | None = None  # None = auto-detect
    sheet: str | int = 0
    header_row: int = Field(default=1, ge=1)
    record_path: str | None = None  # JSON: dotted path to the list, e.g. "data.items"
    record_tag: str | None = None  # XML: element name of one record
    # Excel only. Row numbers are 1-based sheet rows, as shown in Excel.
    header_rows: int = Field(default=1, ge=1, le=10)  # multi-level header: "Parent / Child"
    data_start: int | None = Field(default=None, ge=1)  # None = right after the header
    data_end: int | None = Field(default=None, ge=1)  # None = last row
    skip_rows: list[int] = Field(default_factory=list)
    include_rows: list[int] = Field(default_factory=list)  # overrides smart skipping
    smart_rows: bool = False  # skip numbering/section/total rows, fill merged cells down
    display_values: bool = True  # import "01", "1.000.000" as formatted in Excel
    thousands_separator: str = "."
    decimal_separator: str = ","


# ─── Target side (profile) ──────────────────────────────────────────────────


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldSpec(_Strict):
    """How to reach and fill one control in the target app."""

    label: str = ""
    locator: dict[str, str]  # driver-specific, e.g. {"auto_id": "txtName"} or {"css": "#name"}
    kind: Literal["text", "select", "check"] = "text"
    clear: bool = True
    sensitive: bool = False  # mask value in logs / UI


class Step(_Strict):
    action: Literal["click", "fill", "fill_all", "press", "wait", "sleep"]
    target: str | None = None  # field name (fill) or locator key in profile.controls (click/wait)
    keys: str | None = None  # "Escape", "Control+S", "ControlOrMeta+N" (see core/keys.py)
    seconds: float = 0.0
    timeout: float = 10.0
    state: Literal["visible", "gone"] = "visible"

    @model_validator(mode="after")
    def _check(self) -> Step:
        needs_target = {"click", "fill", "wait"}
        if self.action in needs_target and not self.target:
            raise ValueError(f"step '{self.action}' requires 'target'")
        if self.action == "press":
            if not self.keys:
                raise ValueError("step 'press' requires 'keys'")
            parse_combo(self.keys)
        return self


class Profile(_Strict):
    """A target app screen: how to connect, which fields exist, and what to do per record."""

    id: str
    name: str
    driver: str = "dry_run"
    connect: dict[str, str] = Field(default_factory=dict)
    fields: dict[str, FieldSpec]
    controls: dict[str, dict[str, str]] = Field(default_factory=dict)  # buttons, dialogs…
    record_steps: list[Step] = Field(default_factory=lambda: [Step(action="fill_all")])
    on_error_steps: list[Step] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_refs(self) -> Profile:
        for step in [*self.record_steps, *self.on_error_steps]:
            if step.action == "fill" and step.target not in self.fields:
                raise ValueError(f"fill step references unknown field '{step.target}'")
            if step.action in {"click", "wait"} and step.target not in self.controls:
                raise ValueError(f"{step.action} step references unknown control '{step.target}'")
        return self


# ─── Mapping ────────────────────────────────────────────────────────────────


class FieldMap(_Strict):
    field: str  # profile field name
    source: str | None = None  # source column; None -> use `const`
    const: str | None = None
    default: str = ""
    required: bool = False
    transforms: list[str] = Field(default_factory=list)  # "strip", "date:%d/%m/%Y,%Y-%m-%d"


class Mapping(_Strict):
    name: str
    profile: str  # Profile.id
    source_options: SourceOptions = Field(default_factory=SourceOptions)
    fields: list[FieldMap]


@dataclass(slots=True)
class MappedRecord:
    record: Record
    values: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)  # field -> message

    @property
    def ok(self) -> bool:
        return not self.errors


# ─── Run ────────────────────────────────────────────────────────────────────


class RunOptions(_Strict):
    dry_run: bool = True
    step_mode: bool = False
    rows: set[int] | None = None  # None = all rows
    stop_on_error: bool = False
    delay_between_records: float = Field(default=0.3, ge=0)
    countdown_seconds: int = Field(default=3, ge=0)
    screenshot_on_error: bool = True


class RowStatus(StrEnum):
    PENDING = "pending"
    INVALID = "invalid"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    REVIEW = "needs_review"
    SKIPPED = "skipped"


@dataclass(slots=True)
class RowResult:
    index: int
    status: RowStatus
    message: str = ""
    screenshot: str | None = None


@dataclass(slots=True)
class RunReport:
    run_id: str
    results: list[RowResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    cancelled: bool = False

    def count(self, status: RowStatus) -> int:
        return sum(1 for r in self.results if r.status == status)

    @property
    def failed_rows(self) -> set[int]:
        failed = {RowStatus.FAILED, RowStatus.INVALID}
        return {r.index for r in self.results if r.status in failed}

    @property
    def retryable_rows(self) -> set[int]:
        """Rows that failed before anything uncertain happened; invalid data needs a fixed file."""
        return {r.index for r in self.results if r.status == RowStatus.FAILED}

    @property
    def review_rows(self) -> set[int]:
        return {r.index for r in self.results if r.status == RowStatus.REVIEW}
