"""macOS desktop driver (Accessibility API via pyobjc).

Profile `connect` keys: bundle_id (e.g. "com.apple.TextEdit") or app_name (e.g. "TextEdit");
optional input_mode: "ax" (default, set value directly) | "keyboard" (type like a human,
for Electron/Java apps that ignore AXValue).
Locators match AX attributes: identifier, title, description, role, subrole, placeholder,
value, help; optional "index" picks the n-th match (0-based).
Find locators with `autoinput ax-tree --app "<name>"` or Xcode's Accessibility Inspector.

Requires: System Settings → Privacy & Security → Accessibility → allow your terminal / AutoInput.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from autoinput.core.keys import parse_combo
from autoinput.domain import DriverError, FieldSpec
from autoinput.targets.base import Driver, driver_registry

LOCATOR_ATTRS = {
    "identifier": "AXIdentifier",
    "title": "AXTitle",
    "description": "AXDescription",
    "role": "AXRole",
    "subrole": "AXSubrole",
    "placeholder": "AXPlaceholderValue",
    "value": "AXValue",
    "help": "AXHelp",
}
_MAX_NODES = 8000
_POLL = 0.15
_TRUE = {"1", "true", "yes", "x", "có"}


def matches(attrs: dict[str, str], locator: dict[str, str]) -> bool:
    """Pure matcher (unit-tested): every locator key except `index` must equal the AX attribute."""
    for key, expected in locator.items():
        if key == "index":
            continue
        if key not in LOCATOR_ATTRS:
            raise DriverError(f"Unsupported mac locator '{key}'. Use: {', '.join(LOCATOR_ATTRS)}")
        if attrs.get(LOCATOR_ATTRS[key], "") != expected:
            return False
    return True


@driver_registry.register("mac")
class MacDriver(Driver):
    def connect(self) -> None:
        if sys.platform != "darwin":
            raise DriverError("The 'mac' driver only runs on macOS. Use dry_run to preview.")
        try:
            import ApplicationServices as ax  # noqa: N813
            from AppKit import NSWorkspace
        except ImportError as e:
            raise DriverError("pyobjc missing. Install with: uv sync --extra mac") from e
        if not ax.AXIsProcessTrusted():
            raise DriverError(
                "macOS chưa cấp quyền Accessibility. Mở System Settings → Privacy & Security → "
                "Accessibility và bật cho Terminal/AutoInput, rồi chạy lại."
            )
        self._ax = ax
        cfg = self.profile.connect
        bundle_id, name = cfg.get("bundle_id"), cfg.get("app_name")
        if not (bundle_id or name):
            raise DriverError("Profile connect needs bundle_id or app_name for the mac driver")

        app = self._running_app(NSWorkspace, bundle_id, name)
        if app is None:
            # Arguments are passed as a list (no shell), so app names can't inject commands.
            subprocess.run(
                ["open", "-b", bundle_id] if bundle_id else ["open", "-a", name], check=False
            )
            deadline = time.monotonic() + 30
            while app is None and time.monotonic() < deadline:
                time.sleep(0.5)
                app = self._running_app(NSWorkspace, bundle_id, name)
            if app is None:
                raise DriverError(f"Không mở được ứng dụng {bundle_id or name}")
        self._app = app
        self._root = ax.AXUIElementCreateApplication(app.processIdentifier())
        self._activate()
        self._keyboard_mode = cfg.get("input_mode", "ax") == "keyboard"
        self.log.info(f"Connected to {app.localizedName()} (pid {app.processIdentifier()})")

    @staticmethod
    def _running_app(ws: Any, bundle_id: str | None, name: str | None) -> Any:
        for app in ws.sharedWorkspace().runningApplications():
            if (bundle_id and app.bundleIdentifier() == bundle_id) or (
                name and app.localizedName() == name
            ):
                return app
        return None

    def _activate(self) -> None:
        from AppKit import NSApplicationActivateIgnoringOtherApps

        self._app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        time.sleep(0.2)

    # ── AX helpers ──
    def _attr(self, el: Any, name: str) -> Any:
        err, value = self._ax.AXUIElementCopyAttributeValue(el, name, None)
        return value if err == 0 else None

    def _attrs(self, el: Any) -> dict[str, str]:
        out = {}
        for ax_name in LOCATOR_ATTRS.values():
            v = self._attr(el, ax_name)
            if isinstance(v, str | int | float):  # skip AXUIElement / array values
                out[ax_name] = str(v)
        return out

    def _walk(self, root: Any) -> Iterator[tuple[int, Any]]:
        queue: deque[tuple[int, Any]] = deque([(0, root)])
        seen = 0
        while queue and seen < _MAX_NODES:
            depth, el = queue.popleft()
            seen += 1
            yield depth, el
            for child in self._attr(el, "AXChildren") or []:
                queue.append((depth + 1, child))

    def _search(self, locator: dict[str, str]) -> Any | None:
        wanted = int(locator.get("index", 0))
        hit = 0
        for window in self._attr(self._root, "AXWindows") or []:
            for _, el in self._walk(window):
                if matches(self._attrs(el), locator):
                    if hit == wanted:
                        return el
                    hit += 1
        return None

    def _find(self, locator: dict[str, str], timeout: float = 10) -> Any:
        deadline = time.monotonic() + timeout
        while True:
            if (el := self._search(locator)) is not None:
                return el
            if time.monotonic() > deadline:
                raise DriverError(f"Control not found: {locator}", context={"locator": locator})
            time.sleep(_POLL)

    def _press_el(self, el: Any) -> None:
        if self._ax.AXUIElementPerformAction(el, "AXPress") != 0:
            raise DriverError("Control does not support press")

    # ── Driver API ──
    def fill(self, spec: FieldSpec, value: str) -> None:
        el = self._find(spec.locator)
        match spec.kind:
            case "text":
                self._ax.AXUIElementSetAttributeValue(el, "AXFocused", True)
                if self._keyboard_mode or (
                    self._ax.AXUIElementSetAttributeValue(el, "AXValue", value) != 0
                ):
                    if spec.clear:
                        self.press("Meta+A")
                        self.press("Delete")
                    self._type(value)
            case "select":
                if self._attr(el, "AXRole") == "AXComboBox":
                    self._ax.AXUIElementSetAttributeValue(el, "AXValue", value)
                    return
                self._press_el(el)  # opens the popup menu
                item = self._find({"role": "AXMenuItem", "title": value}, timeout=3)
                self._press_el(item)
            case "check":
                current = str(self._attr(el, "AXValue") or "0") == "1"
                if current != (value.strip().lower() in _TRUE):
                    self._press_el(el)

    def click(self, locator: dict[str, str]) -> None:
        self._press_el(self._find(locator))

    def press(self, keys: str) -> None:
        from pynput.keyboard import Controller, Key

        mods, key = parse_combo(keys, platform="darwin")
        mod_keys = {"control": Key.ctrl, "shift": Key.shift, "alt": Key.alt, "meta": Key.cmd}
        named = {
            "escape": Key.esc, "enter": Key.enter, "tab": Key.tab, "backspace": Key.backspace,
            "delete": Key.backspace, "space": Key.space, "home": Key.home, "end": Key.end,
            "pageup": Key.page_up, "pagedown": Key.page_down, "arrowup": Key.up,
            "arrowdown": Key.down, "arrowleft": Key.left, "arrowright": Key.right,
            **{f"f{n}": getattr(Key, f"f{n}") for n in range(1, 13)},
        }  # fmt: skip
        kb = Controller()
        with kb.pressed(*(mod_keys[m] for m in mods)):
            kb.tap(named.get(key, key))

    def _type(self, text: str) -> None:
        from pynput.keyboard import Controller

        Controller().type(text)

    def wait(self, locator: dict[str, str], state: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self._search(locator) is not None
            if found == (state == "visible"):
                return
            time.sleep(_POLL)
        raise DriverError(f"Timeout waiting for {locator} to be {state}")

    def screenshot(self, path: Path) -> bool:
        result = subprocess.run(["screencapture", "-x", str(path)], check=False)
        return result.returncode == 0

    def dump_tree(self, max_depth: int = 12) -> Iterator[str]:
        """Human-readable AX tree used by `autoinput ax-tree` to discover locators."""
        reverse = {v: k for k, v in LOCATOR_ATTRS.items()}
        for window in self._attr(self._root, "AXWindows") or []:
            for depth, el in self._walk(window):
                if depth > max_depth:
                    continue
                attrs = self._attrs(el)
                role = attrs.pop("AXRole", "?")
                attrs.pop("AXValue", None)
                desc = " ".join(f'{reverse[k]}="{v}"' for k, v in attrs.items() if v)
                yield f"{'  ' * depth}{role} {desc}"
