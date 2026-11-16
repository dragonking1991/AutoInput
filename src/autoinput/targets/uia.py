"""Windows desktop driver (pywinauto, UI Automation backend).

Profile `connect` keys: title_re (required), exe (optional, launched if not running), backend (uia|win32).
Field locators are pywinauto `child_window` criteria, e.g. {"auto_id": "txtName"}.
"""

import sys
import time
from pathlib import Path
from typing import Any

from autoinput.core.keys import to_pywinauto
from autoinput.domain import DriverError, FieldSpec
from autoinput.targets.base import Driver, driver_registry


@driver_registry.register("uia")
class UiaDriver(Driver):
    def connect(self) -> None:
        if sys.platform != "win32":
            raise DriverError("The 'uia' driver only runs on Windows. Use dry_run to preview.")
        try:
            from pywinauto import Application
            from pywinauto.findwindows import ElementNotFoundError
        except ImportError as e:
            raise DriverError("pywinauto missing. Install with: uv sync --extra windows") from e

        cfg = self.profile.connect
        backend = cfg.get("backend", "uia")
        title_re = cfg.get("title_re")
        if not title_re:
            raise DriverError("Profile connect.title_re is required for the uia driver")
        try:
            app = Application(backend=backend).connect(title_re=title_re, timeout=5)
        except ElementNotFoundError:
            if not cfg.get("exe"):
                raise DriverError(f"No window matches '{title_re}' and no exe configured") from None
            self.log.info(f"Launching {cfg['exe']}")
            app = Application(backend=backend).start(cfg["exe"])
        self.window = app.window(title_re=title_re)
        self.window.wait("ready", timeout=30)
        self.window.set_focus()
        self.log.info(f"Connected to '{self.window.window_text()}'")

    def _find(self, locator: dict[str, str], timeout: float = 10) -> Any:
        try:
            ctrl = self.window.child_window(**locator)
            ctrl.wait("exists enabled visible", timeout=timeout)
            return ctrl
        except Exception as e:
            raise DriverError(f"Control not found: {locator}", context={"locator": locator}) from e

    def fill(self, spec: FieldSpec, value: str) -> None:
        ctrl = self._find(spec.locator)
        match spec.kind:
            case "text":
                # ValuePattern is faster and IME/keyboard-layout safe; fall back to typing.
                try:
                    ctrl.set_edit_text(value)
                except Exception:
                    ctrl.set_focus()
                    if spec.clear:
                        ctrl.type_keys("^a{DELETE}")
                    ctrl.type_keys(value, with_spaces=True, with_tabs=True, with_newlines=True)
            case "select":
                ctrl.select(value)
            case "check":
                want = value.strip().lower() in {"1", "true", "yes", "x", "có"}
                if bool(ctrl.get_toggle_state()) != want:
                    ctrl.toggle()

    def click(self, locator: dict[str, str]) -> None:
        self._find(locator).click_input()

    def press(self, keys: str) -> None:
        self.window.type_keys(to_pywinauto(keys))

    def wait(self, locator: dict[str, str], state: str, timeout: float) -> None:
        ctrl = self.window.child_window(**locator)
        try:
            if state == "gone":
                ctrl.wait_not("exists", timeout=timeout)
            else:
                ctrl.wait("exists visible", timeout=timeout)
        except Exception as e:
            raise DriverError(f"Timeout waiting for {locator} to be {state}") from e
        time.sleep(0.05)

    def screenshot(self, path: Path) -> bool:
        try:
            self.window.capture_as_image().save(path)
            return True
        except Exception:
            return False
