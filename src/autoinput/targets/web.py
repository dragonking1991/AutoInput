"""Web form driver (Playwright).

Profile `connect` keys: url (http(s) URL or a local .html path), or cdp_url to attach to an already logged-in Chrome
(start Chrome with --remote-debugging-port=9222). Optional: headless=true.
Locators: {"css": "#name"} | {"label": "Họ tên"} | {"placeholder": "..."} | {"text": "Lưu"}.
"""

from pathlib import Path
from typing import Any

from autoinput.domain import DriverError, FieldSpec
from autoinput.targets.base import Driver, driver_registry


@driver_registry.register("web")
class WebDriver(Driver):
    needs_focus = False  # Playwright drives the page directly; the user can keep working

    def connect(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise DriverError(
                "Playwright missing. Install: uv sync --extra web && playwright install"
            ) from e

        cfg = self.profile.connect
        self._pw = sync_playwright().start()
        if cdp := cfg.get("cdp_url"):
            browser = self._pw.chromium.connect_over_cdp(cdp)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            self.page = context.pages[0] if context.pages else context.new_page()
        else:
            headless = cfg.get("headless", "false").lower() == "true"
            self._browser = self._pw.chromium.launch(headless=headless)
            self.page = self._browser.new_page()
        if url := cfg.get("url"):
            self.page.goto(_resolve_url(url))

    def close(self) -> None:
        if browser := getattr(self, "_browser", None):
            browser.close()
        if pw := getattr(self, "_pw", None):
            pw.stop()

    def _loc(self, locator: dict[str, str]) -> Any:
        ((kind, value),) = locator.items()
        match kind:
            case "css":
                return self.page.locator(value)
            case "label":
                return self.page.get_by_label(value)
            case "placeholder":
                return self.page.get_by_placeholder(value)
            case "text":
                return self.page.get_by_text(value, exact=True)
        raise DriverError(f"Unsupported web locator '{kind}'")

    def fill(self, spec: FieldSpec, value: str) -> None:
        loc = self._loc(spec.locator)
        match spec.kind:
            case "text":
                loc.fill(value)
            case "select":
                loc.select_option(label=value)
            case "check":
                loc.set_checked(value.strip().lower() in {"1", "true", "yes", "x", "có"})

    def click(self, locator: dict[str, str]) -> None:
        self._loc(locator).click()

    def press(self, keys: str) -> None:
        self.page.keyboard.press(keys)

    def wait(self, locator: dict[str, str], state: str, timeout: float) -> None:
        self._loc(locator).wait_for(
            state="hidden" if state == "gone" else "visible", timeout=timeout * 1000
        )

    def screenshot(self, path: Path) -> bool:
        self.page.screenshot(path=str(path))
        return True


def _resolve_url(url: str) -> str:
    """Allow local HTML files (relative to the working dir) in profiles, e.g. samples/demo_form.html."""
    if "://" in url:
        return url
    path = Path(url).expanduser().resolve()
    if not path.is_file():
        raise DriverError(f"URL/file not found: {url}")
    return path.as_uri()
