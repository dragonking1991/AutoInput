from __future__ import annotations

import time
import uuid
from collections.abc import Iterable

from autoinput.domain import (
    AutoInputError,
    MappedRecord,
    Profile,
    Record,
    RowResult,
    RowStatus,
    RunCancelled,
    RunOptions,
    RunReport,
    Step,
)
from autoinput.engine.control import EventSink, RunControl, RunEvent
from autoinput.engine.journal import Journal
from autoinput.infra.logging import get_logger
from autoinput.infra.settings import get_settings
from autoinput.mapping import Mapper
from autoinput.targets import Driver, create_driver


class Runner:
    """Orchestrates map -> validate -> drive for each record. UI-agnostic and thread-agnostic."""

    def __init__(
        self,
        profile: Profile,
        mapper: Mapper,
        options: RunOptions,
        *,
        driver: Driver | None = None,
        control: RunControl | None = None,
        on_event: EventSink | None = None,
        journal: Journal | None = None,
    ) -> None:
        self.profile = profile
        self.mapper = mapper
        self.options = options
        self.driver = driver or create_driver(profile, dry_run=options.dry_run)
        self.control = control or RunControl()
        self.on_event = on_event or (lambda _e: None)
        self.journal = journal
        self.log = get_logger("engine")

    def run(self, records: Iterable[Record], source_name: str = "") -> RunReport:
        rows = self.options.rows
        mapped = [self.mapper.apply(r) for r in records if rows is None or r.index in rows]
        report = RunReport(run_id=uuid.uuid4().hex[:12])
        total = len(mapped)
        started = time.monotonic()

        if self.journal:
            self.journal.start_run(
                report.run_id, source_name, self.profile.id, self.options.dry_run
            )
        self.log.info(f"Run {report.run_id}: {total} records, dry_run={self.options.dry_run}")
        self.on_event(RunEvent("started", total=total))

        try:
            self._countdown()
            with self.driver:
                for pos, item in enumerate(mapped, start=1):
                    self.control.checkpoint()
                    self.on_event(
                        RunEvent("row_started", row=item.record.index, position=pos, total=total)
                    )
                    result = self._process(item)
                    report.results.append(result)
                    if self.journal:
                        self.journal.record(report.run_id, result)
                    self.on_event(
                        RunEvent(
                            "row_finished",
                            row=result.index,
                            position=pos,
                            total=total,
                            result=result,
                        )
                    )

                    if result.status == RowStatus.FAILED and self.options.stop_on_error:
                        self.log.warning("Stopping on first error (stop_on_error)")
                        break
                    if pos < total:
                        if self.options.step_mode:
                            self.control.pause()
                            self.on_event(
                                RunEvent("paused", row=item.record.index, position=pos, total=total)
                            )
                        else:
                            self.control.sleep(self.options.delay_between_records)
        except RunCancelled:
            report.cancelled = True
            self.log.warning("Run cancelled")
        finally:
            report.duration_seconds = time.monotonic() - started
            self.on_event(RunEvent("finished", total=total, report=report))
        return report

    def _countdown(self) -> None:
        if self.options.dry_run or not self.driver.needs_focus:
            return
        for remaining in range(self.options.countdown_seconds, 0, -1):
            self.on_event(RunEvent("countdown", message=str(remaining)))
            self.control.sleep(1)

    def _process(self, item: MappedRecord) -> RowResult:
        index = item.record.index
        if not item.ok:
            msg = "; ".join(f"{f}: {e}" for f, e in item.errors.items())
            return RowResult(index, RowStatus.INVALID, msg)
        try:
            for step in self.profile.record_steps:
                self.control.checkpoint()
                self._execute(step, item.values)
            return RowResult(index, RowStatus.DONE)
        except RunCancelled:
            raise
        except Exception as e:
            msg = e.message if isinstance(e, AutoInputError) else f"{type(e).__name__}: {e}"
            self.log.error(f"Row {index} failed: {msg}")
            shot = self._screenshot(index)
            self._recover()
            return RowResult(index, RowStatus.FAILED, msg, shot)

    def _execute(self, step: Step, values: dict[str, str]) -> None:
        fields, controls, d = self.profile.fields, self.profile.controls, self.driver
        match step.action:
            case "fill_all":
                for name, spec in fields.items():  # profile order = tab order of the form
                    if name in values:
                        d.fill(spec, values[name])
            case "fill":
                assert step.target
                if step.target in values:
                    d.fill(fields[step.target], values[step.target])
            case "click":
                assert step.target
                d.click(controls[step.target])
            case "press":
                assert step.keys
                d.press(step.keys)
            case "wait":
                assert step.target
                d.wait(controls[step.target], step.state, step.timeout)
            case "sleep":
                self.control.sleep(step.seconds)

    def _screenshot(self, index: int) -> str | None:
        if not self.options.screenshot_on_error:
            return None
        directory = get_settings().screenshots_dir
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{time.strftime('%Y%m%d_%H%M%S')}_row{index}.png"
        return str(path) if self.driver.screenshot(path) else None

    def _recover(self) -> None:
        """Best-effort: bring the target app back to a known state (e.g. press Esc, close dialog)."""
        for step in self.profile.on_error_steps:
            try:
                self._execute(step, {})
            except Exception as e:
                self.log.warning(f"Recovery step {step.action} failed: {e}")
