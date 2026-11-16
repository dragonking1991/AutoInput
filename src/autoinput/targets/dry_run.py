from autoinput.domain import FieldSpec
from autoinput.infra.logging import mask
from autoinput.targets.base import Driver, driver_registry


@driver_registry.register("dry_run")
class DryRunDriver(Driver):
    """Performs nothing; records every action. Used for previews, tests and debugging."""

    actions: list[tuple[str, ...]]
    needs_focus = False

    def connect(self) -> None:
        self.actions = []
        self.log.info(f"[DRY RUN] connect {self.profile.connect or '(no connect info)'}")

    def fill(self, spec: FieldSpec, value: str) -> None:
        shown = mask(value) if spec.sensitive else value
        self.actions.append(("fill", str(spec.locator), shown))
        self.log.info(f"[DRY RUN] fill {spec.locator} = {shown!r}")

    def click(self, locator: dict[str, str]) -> None:
        self.actions.append(("click", str(locator)))
        self.log.info(f"[DRY RUN] click {locator}")

    def press(self, keys: str) -> None:
        self.actions.append(("press", keys))
        self.log.info(f"[DRY RUN] press {keys}")

    def wait(self, locator: dict[str, str], state: str, timeout: float) -> None:
        self.actions.append(("wait", str(locator), state))
