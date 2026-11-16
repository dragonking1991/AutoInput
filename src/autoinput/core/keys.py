"""Neutral key-combo syntax used in profiles (same as Playwright): "Escape", "Control+S", "Meta+N".

"ControlOrMeta" means Cmd on macOS and Ctrl elsewhere, so one profile works on both.
"""

import sys

_MODIFIERS = {
    "control": "control",
    "ctrl": "control",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "meta": "meta",
    "cmd": "meta",
    "command": "meta",
    "controlormeta": "controlormeta",
}

NAMED_KEYS = {
    "escape", "enter", "tab", "backspace", "delete", "space", "home", "end", "pageup",
    "pagedown", "arrowup", "arrowdown", "arrowleft", "arrowright",
    *(f"f{n}" for n in range(1, 13)),
}  # fmt: skip


def parse_combo(combo: str, platform: str = sys.platform) -> tuple[list[str], str]:
    """'Control+Shift+S' -> (['control', 'shift'], 's'). Raises ValueError on unknown keys."""
    parts = [p.strip() for p in combo.split("+")]
    if not combo.strip() or any(not p for p in parts):
        raise ValueError(f"Invalid key combo '{combo}'")
    *mods_raw, key_raw = parts
    mods: list[str] = []
    for m in mods_raw:
        canon = _MODIFIERS.get(m.lower())
        if canon is None:
            raise ValueError(f"Unknown modifier '{m}' in '{combo}'")
        if canon == "controlormeta":
            canon = "meta" if platform == "darwin" else "control"
        mods.append(canon)
    key = key_raw.lower()
    if len(key_raw) != 1 and key not in NAMED_KEYS:
        raise ValueError(f"Unknown key '{key_raw}' in '{combo}'")
    return mods, key if len(key_raw) != 1 else key_raw


_PYWINAUTO_MODS = {"control": "^", "shift": "+", "alt": "%"}
_PYWINAUTO_KEYS = {
    "escape": "{ESC}", "enter": "{ENTER}", "tab": "{TAB}", "backspace": "{BACKSPACE}",
    "delete": "{DELETE}", "space": "{SPACE}", "home": "{HOME}", "end": "{END}",
    "pageup": "{PGUP}", "pagedown": "{PGDN}", "arrowup": "{UP}", "arrowdown": "{DOWN}",
    "arrowleft": "{LEFT}", "arrowright": "{RIGHT}",
    **{f"f{n}": f"{{F{n}}}" for n in range(1, 13)},
}  # fmt: skip


def to_pywinauto(combo: str) -> str:
    mods, key = parse_combo(combo, platform="win32")
    if "meta" in mods:
        raise ValueError("Meta/Win key combos are not supported on Windows targets")
    escaped = f"{{{key}}}" if key in "+^%~(){}[]" else key
    token = _PYWINAUTO_KEYS.get(key, escaped)
    return "".join(_PYWINAUTO_MODS[m] for m in mods) + token
