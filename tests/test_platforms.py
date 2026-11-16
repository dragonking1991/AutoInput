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


def test_all_shipped_profiles_and_mappings_are_valid() -> None:
    profiles = list_profiles(ROOT / "profiles")
    assert len(profiles) == len(list((ROOT / "profiles").glob("*.yaml")))
    for path in (ROOT / "mappings").glob("*.yaml"):
        assert load_mapping(path).profile in profiles
