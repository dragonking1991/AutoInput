from pathlib import Path

import pytest
from pydantic import ValidationError

from autoinput.core.keys import parse_combo, to_pywinauto
from autoinput.domain import DriverError, Step
from autoinput.infra.storage import list_profiles, load_mapping
from autoinput.targets.mac import matches
from autoinput.targets.web import _resolve_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("combo", "platform", "expected"),
    [
        ("Escape", "darwin", ([], "escape")),
        ("Control+Shift+S", "win32", (["control", "shift"], "S")),
        ("Cmd+N", "darwin", (["meta"], "N")),
        ("ControlOrMeta+A", "darwin", (["meta"], "A")),
        ("ControlOrMeta+A", "win32", (["control"], "A")),
    ],
)
def test_parse_combo(combo: str, platform: str, expected: tuple[list[str], str]) -> None:
    assert parse_combo(combo, platform) == expected


@pytest.mark.parametrize(
    ("combo", "expected"),
    [("Escape", "{ESC}"), ("Control+s", "^s"), ("Alt+F4", "%{F4}"), ("Shift+(", "+{(}")],
)
def test_to_pywinauto(combo: str, expected: str) -> None:
    assert to_pywinauto(combo) == expected


def test_profile_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError, match="Unknown key"):
        Step(action="press", keys="Escap")


def test_mac_locator_matching() -> None:
    attrs = {"AXRole": "AXTextField", "AXIdentifier": "fullName"}
    assert matches(attrs, {"role": "AXTextField", "identifier": "fullName", "index": "0"})
    assert not matches(attrs, {"role": "AXButton"})
    with pytest.raises(DriverError, match="Unsupported mac locator"):
        matches(attrs, {"auto_id": "x"})


def test_web_resolves_local_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    assert _resolve_url("samples/demo_form.html").startswith("file://")
    assert _resolve_url("https://x.test") == "https://x.test"
    with pytest.raises(DriverError):
        _resolve_url("missing.html")


def test_web_wait_can_be_cancelled_between_polls(monkeypatch, simple_profile) -> None:
    from autoinput.domain import RunCancelled
    from autoinput.engine import RunControl
    from autoinput.targets.web import WebDriver

    playwright = pytest.importorskip("playwright.sync_api")
    control = RunControl()
    driver = WebDriver(simple_profile)
    driver.checkpoint = control.checkpoint
    calls = []

    class Locator:
        def wait_for(self, *, state, timeout):
            calls.append((state, timeout))
            control.cancel()
            raise playwright.TimeoutError("still waiting")

    monkeypatch.setattr(driver, "_loc", lambda locator: Locator())
    with pytest.raises(RunCancelled):
        driver.wait({"css": "#saved"}, "visible", 10)
    assert len(calls) == 1
    assert 0 < calls[0][1] <= 200


def test_all_shipped_profiles_and_mappings_are_valid() -> None:
    profiles = list_profiles(ROOT / "profiles")
    assert len(profiles) == len(list((ROOT / "profiles").glob("*.yaml")))
    for path in (ROOT / "mappings").glob("*.yaml"):
        assert load_mapping(path).profile in profiles


def test_installed_app_keeps_config_in_user_folder(tmp_path, monkeypatch) -> None:
    """A packaged app starts with an arbitrary cwd, so config must not depend on it."""
    import sys

    from autoinput.infra.settings import AppSettings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(ROOT), raising=False)
    settings = AppSettings(data_dir=tmp_path / "data")
    assert settings.profiles_path == tmp_path / "data" / "profiles"

    settings.seed_config()
    assert (settings.profiles_path / "demo_web_form.yaml").is_file()
    edited = settings.mappings_path / "demo_web_form.yaml"
    edited.write_text("user edit", encoding="utf-8")
    settings.seed_config()
    assert edited.read_text(encoding="utf-8") == "user edit"


def test_web_demo_url_resolves_from_bundle_when_cwd_differs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert _resolve_url("samples/demo_form.html").endswith("samples/demo_form.html")


def test_logging_never_starts_helper_processes(tmp_path) -> None:
    """Regression: loguru enqueue=True started multiprocessing's resource tracker, which in the
    packaged app re-executed AutoInput itself and opened windows endlessly."""
    import subprocess
    import sys

    code = (
        "import multiprocessing.resource_tracker as rt\n"
        "from autoinput.infra.logging import setup_logging, get_logger\n"
        "setup_logging(); get_logger('app').info('x')\n"
        "print(rt._resource_tracker._pid)\n"
    )
    env = {**__import__("os").environ, "AUTOINPUT_DATA_DIR": str(tmp_path)}
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=30
    )
    assert out.stdout.strip() == "None", out.stderr


def test_launcher_ignores_interpreter_style_reexec() -> None:
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "launcher.py"), "-B", "-s", "-c", "pass"],
        capture_output=True, text=True, timeout=30,
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
    )  # fmt: skip
    assert out.returncode == 0
    assert out.stdout == ""


def test_gui_refuses_to_start_inside_running_gui(monkeypatch) -> None:
    import os

    from autoinput.ui import app

    monkeypatch.setenv("AUTOINPUT_GUI_PID", str(os.getppid()))  # a live process
    assert app._spawned_by_running_gui()
    monkeypatch.setenv("AUTOINPUT_GUI_PID", "999999")  # not running
    assert not app._spawned_by_running_gui()
