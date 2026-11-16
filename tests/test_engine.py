import threading

from autoinput.domain import (
    DriverError,
    FieldMap,
    FieldSpec,
    Mapping,
    Profile,
    Record,
    RowStatus,
    RunOptions,
)
from autoinput.engine import Journal, RunControl, RunEvent, Runner
from autoinput.mapping import Mapper
from autoinput.targets.dry_run import DryRunDriver


def _mapper(profile: Profile) -> Mapper:
    m = Mapping(
        name="m",
        profile=profile.id,
        fields=[
            FieldMap(field="name", source="Name", required=True),
            FieldMap(field="code", source="Code"),
        ],
    )
    return Mapper(m, profile)


RECORDS = [
    Record(1, {"Name": "A", "Code": "1"}),
    Record(2, {"Name": "", "Code": "2"}),
    Record(3, {"Name": "C"}),
]


def test_dry_run_executes_steps_and_skips_invalid(simple_profile: Profile, tmp_path) -> None:
    driver = DryRunDriver(simple_profile)
    events: list[RunEvent] = []
    journal = Journal(tmp_path / "j.sqlite3")
    runner = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(delay_between_records=0),
        driver=driver,
        on_event=events.append,
        journal=journal,
    )
    report = runner.run(RECORDS)

    assert [r.status for r in report.results] == [RowStatus.DONE, RowStatus.INVALID, RowStatus.DONE]
    assert report.failed_rows == {2}
    assert driver.actions[:3] == [
        ("fill", "{'auto_id': 'n'}", "A"),
        ("fill", "{'auto_id': 'c'}", "1"),
        ("click", "{'auto_id': 's'}"),
    ]
    assert events[0].kind == "started" and events[-1].kind == "finished"
    assert [r.status for r in journal.results(report.run_id)] == [r.status for r in report.results]


def test_rows_filter(simple_profile: Profile) -> None:
    runner = Runner(
        simple_profile, _mapper(simple_profile), RunOptions(rows={3}, delay_between_records=0)
    )
    assert [r.index for r in runner.run(RECORDS).results] == [3]


class FailingDriver(DryRunDriver):
    def click(self, locator: dict[str, str]) -> None:
        raise DriverError("Control not found")


def test_driver_failure_marks_row_and_stops(simple_profile: Profile) -> None:
    runner = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(stop_on_error=True, delay_between_records=0, screenshot_on_error=False),
        driver=FailingDriver(simple_profile),
    )
    report = runner.run(RECORDS)
    assert len(report.results) == 1
    assert report.results[0].status == RowStatus.FAILED
    assert "Control not found" in report.results[0].message


def test_step_mode_pauses_and_cancel_stops(simple_profile: Profile) -> None:
    control = RunControl()
    paused = threading.Event()

    def on_event(e: RunEvent) -> None:
        if e.kind == "paused":
            paused.set()

    runner = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(step_mode=True),
        control=control,
        on_event=on_event,
    )
    result: list = []
    t = threading.Thread(target=lambda: result.append(runner.run(RECORDS)))
    t.start()
    assert paused.wait(2)
    control.cancel()
    t.join(2)
    report = result[0]
    assert report.cancelled
    assert len(report.results) == 1


def test_sensitive_values_are_masked(tmp_path) -> None:
    profile = Profile(
        id="s", name="S", fields={"id": FieldSpec(locator={"auto_id": "x"}, sensitive=True)}
    )
    mapper = Mapper(
        Mapping(name="m", profile="s", fields=[FieldMap(field="id", source="ID")]), profile
    )
    driver = DryRunDriver(profile)
    Runner(profile, mapper, RunOptions(delay_between_records=0), driver=driver).run(
        [Record(1, {"ID": "012345"})]
    )
    assert driver.actions[0][2] == "••••45"
