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
    Step,
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


def test_cancel_between_fields_marks_live_row_for_review(simple_profile: Profile) -> None:
    control = RunControl()

    class CancellingDriver(DryRunDriver):
        def fill(self, spec: FieldSpec, value: str) -> None:
            super().fill(spec, value)
            control.cancel()

    driver = CancellingDriver(simple_profile)
    report = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(dry_run=False),
        driver=driver,
        control=control,
    ).run(RECORDS)
    assert len(driver.actions) == 1
    assert report.cancelled
    assert report.review_rows == {1}
    assert report.failed_rows == set()


def test_failure_after_save_is_not_automatically_retryable(
    simple_profile: Profile, tmp_path
) -> None:
    simple_profile.controls["new"] = {"auto_id": "new"}
    simple_profile.record_steps.append(Step(action="click", target="new"))

    class SavedThenFailedDriver(DryRunDriver):
        def click(self, locator: dict[str, str]) -> None:
            if locator["auto_id"] == "new":
                raise DriverError("New form unavailable")
            super().click(locator)

    driver = SavedThenFailedDriver(simple_profile)
    journal = Journal(tmp_path / "review.sqlite3")
    report = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(dry_run=False, delay_between_records=0),
        driver=driver,
        journal=journal,
    ).run(RECORDS)
    assert report.review_rows == {1}
    assert report.failed_rows == set()
    assert len(report.results) == 1
    assert journal.results(report.run_id) == report.results
    csv = journal.export_csv(report.run_id, tmp_path / "review.csv")
    assert "needs_review" in csv.read_text(encoding="utf-8-sig")
    assert [action for action in driver.actions if action[0] == "click"] == [
        ("click", "{'auto_id': 's'}"),
    ]


def test_cli_exits_with_error_for_uncertain_live_record(monkeypatch, samples):
    from typer.testing import CliRunner

    import autoinput.cli as cli

    class PostSaveFailure(DryRunDriver):
        def click(self, locator):
            if locator.get("css") == "#new":
                raise DriverError("New form unavailable")
            super().click(locator)

    def make_runner(profile, mapper, options, **kwargs):
        return Runner(profile, mapper, options, driver=PostSaveFailure(profile), **kwargs)

    monkeypatch.setattr(cli, "Runner", make_runner)
    monkeypatch.setattr(cli, "setup_logging", lambda *args: None)
    result = CliRunner().invoke(
        cli.app,
        [
            "run",
            str(samples / "customers.csv"),
            "-m",
            str(samples.parent / "mappings/demo_web_form.yaml"),
            "--live",
            "--rows",
            "1",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "needs_review=1" in result.output
    assert "Retry with:" not in result.output


def test_run_uses_snapshot_of_mapping_profile_and_options(simple_profile: Profile) -> None:
    mapper = _mapper(simple_profile)
    options = RunOptions(rows={1}, delay_between_records=0)
    driver = DryRunDriver(simple_profile)
    runner = Runner(simple_profile, mapper, options, driver=driver)
    mapper.mapping.fields[0].source = "Changed"
    simple_profile.record_steps.clear()
    options.rows = {3}
    report = runner.run(RECORDS)
    assert [r.index for r in report.results] == [1]
    assert driver.actions[0] == ("fill", "{'auto_id': 'n'}", "A")


def test_journal_reuses_connection_and_commits_each_result(simple_profile, tmp_path, monkeypatch):
    import sqlite3

    journal = Journal(tmp_path / "j.sqlite3")
    connect = sqlite3.connect
    connections = []

    def tracked_connect(*args, **kwargs):
        db = connect(*args, **kwargs)
        connections.append(db)
        return db

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    observed = []

    def on_event(event):
        if event.kind == "row_finished":
            with connect(journal.path) as db:
                observed.append(db.execute("SELECT COUNT(*) FROM rows").fetchone()[0])

    report = Runner(
        simple_profile,
        _mapper(simple_profile),
        RunOptions(delay_between_records=0),
        journal=journal,
        on_event=on_event,
    ).run(RECORDS)
    assert len(connections) == 2  # start_run and the per-run writer
    assert observed == [1, 2, 3]
    assert len(journal.results(report.run_id)) == 3
