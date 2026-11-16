"""Headless entry point — debug each flow (parse / map / drive) separately."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from autoinput.core.rows import parse_rows
from autoinput.domain import AutoInputError, Profile, RowStatus, RunOptions
from autoinput.engine import Journal, RunControl, RunEvent, Runner, start_kill_switch
from autoinput.infra.logging import setup_logging
from autoinput.infra.settings import get_settings
from autoinput.infra.storage import list_profiles, load_mapping, load_profile
from autoinput.mapping import Mapper
from autoinput.sources import open_source

app = typer.Typer(no_args_is_help=True, help="AutoInput – feed files into data-entry apps.")
console = Console()

FileArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Input file")]
MappingOpt = Annotated[Path, typer.Option("--mapping", "-m", exists=True, help="Mapping YAML")]


def _profile_for(profile_id: str) -> Profile:
    path = list_profiles(get_settings().profiles_dir).get(profile_id)
    if not path:
        raise AutoInputError(f"Profile '{profile_id}' not found in {get_settings().profiles_dir}/")
    return load_profile(path)


@app.callback()
def _setup(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    setup_logging("DEBUG" if verbose else "WARNING")


@app.command()
def inspect(file: FileArg, limit: int = 10) -> None:
    """Parse only: show detected columns and the first rows."""
    source = open_source(file)
    table = Table("#", *source.columns(), title=f"{file.name} ({type(source).label})")
    for rec in source.preview(limit):
        table.add_row(str(rec.index), *(rec.data.get(c, "") for c in source.columns()))
    console.print(table)


@app.command()
def profiles() -> None:
    """List available target profiles."""
    for pid, path in list_profiles(get_settings().profiles_dir).items():
        p = load_profile(path)
        console.print(
            f"[bold]{pid}[/] – {p.name} [dim](driver={p.driver}, {len(p.fields)} fields)[/]"
        )


@app.command()
def validate(file: FileArg, mapping: MappingOpt) -> None:
    """Parse + map + validate every row, without touching any app."""
    m = load_mapping(mapping)
    profile = _profile_for(m.profile)
    source = open_source(file, m.source_options)
    problems = Mapper.check(m, profile, source.columns())
    if problems:
        console.print("[red]Mapping problems:[/]\n- " + "\n- ".join(problems))
        raise typer.Exit(1)

    mapper = Mapper(m, profile)
    bad = 0
    for item in mapper.apply_all(source.records()):
        if not item.ok:
            bad += 1
            console.print(f"[red]Row {item.record.index}[/]: {item.errors}")
    console.print("[green]All rows valid[/]" if not bad else f"[yellow]{bad} invalid row(s)[/]")
    raise typer.Exit(1 if bad else 0)


@app.command()
def run(
    file: FileArg,
    mapping: MappingOpt,
    dry_run: Annotated[bool, typer.Option("--dry-run/--live")] = True,
    step: Annotated[bool, typer.Option(help="Confirm each record")] = False,
    rows: Annotated[str | None, typer.Option(help="e.g. 1-5,9")] = None,
    stop_on_error: bool = False,
) -> None:
    """Run the full pipeline. Defaults to --dry-run; pass --live to really type."""
    settings = get_settings()
    m = load_mapping(mapping)
    profile = _profile_for(m.profile)
    source = open_source(file, m.source_options)
    control = RunControl()
    options = RunOptions(
        dry_run=dry_run, step_mode=step, rows=parse_rows(rows), stop_on_error=stop_on_error
    )

    def on_event(e: RunEvent) -> None:
        match e.kind:
            case "countdown":
                console.print(f"Starting in {e.message}… switch to the target app now")
            case "row_finished" if e.result:
                color = "green" if e.result.status == RowStatus.DONE else "red"
                console.print(
                    f"[{color}]{e.position}/{e.total} row {e.row}: {e.result.status}[/] {e.result.message}"
                )
            case "paused":
                typer.prompt("Enter to continue", default="", show_default=False)
                control.resume()

    runner = Runner(
        profile,
        Mapper(m, profile),
        options,
        control=control,
        on_event=on_event,
        journal=Journal(settings.journal_path),
    )
    stop_hotkey = (
        start_kill_switch(settings.kill_switch, control.cancel)
        if runner.driver.needs_focus
        else (lambda: None)
    )
    try:
        report = runner.run(source.records(), source_name=str(file))
    finally:
        stop_hotkey()

    console.print(
        f"\nRun {report.run_id}: done={report.count(RowStatus.DONE)} "
        f"failed={report.count(RowStatus.FAILED)} invalid={report.count(RowStatus.INVALID)} "
        f"in {report.duration_seconds:.1f}s"
        + (" [yellow](cancelled)[/]" if report.cancelled else "")
    )
    if report.failed_rows:
        console.print(f"Retry with: --rows {','.join(map(str, sorted(report.failed_rows)))}")


@app.command("ax-tree")
def ax_tree(
    app_name: Annotated[str, typer.Option("--app", help='App name, e.g. "TextEdit"')],
    depth: int = 12,
) -> None:
    """macOS: print the accessibility tree of a running app to find field locators."""
    from autoinput.targets.mac import MacDriver

    driver = MacDriver(
        Profile(id="_", name="_", driver="mac", connect={"app_name": app_name}, fields={})
    )
    driver.connect()
    for line in driver.dump_tree(depth):
        console.print(line, markup=False, highlight=False)


@app.command()
def gui() -> None:
    """Open the desktop app."""
    from autoinput.ui.app import main as gui_main

    gui_main()


def main() -> None:
    try:
        app()
    except AutoInputError as e:
        console.print(f"[red]Error:[/] {e.message}")
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
