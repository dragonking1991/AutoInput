from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import ClassVar

from autoinput.core.registry import Registry
from autoinput.domain import FieldSpec, Profile
from autoinput.infra.logging import get_logger


class Driver(ABC):
    """Talks to one kind of target technology. Must not know about files or mappings."""

    # True when the driver uses the real keyboard/mouse, so the user must not touch them.
    needs_focus: ClassVar[bool] = True

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.log = get_logger("driver")
        self.checkpoint: Callable[[], None] = lambda: None

    @abstractmethod
    def connect(self) -> None: ...

    def close(self) -> None:  # noqa: B027 - optional hook
        pass

    @abstractmethod
    def fill(self, spec: FieldSpec, value: str) -> None: ...

    @abstractmethod
    def click(self, locator: dict[str, str]) -> None: ...

    @abstractmethod
    def press(self, keys: str) -> None: ...

    @abstractmethod
    def wait(self, locator: dict[str, str], state: str, timeout: float) -> None: ...

    def screenshot(self, path: Path) -> bool:
        return False

    def __enter__(self) -> Driver:
        try:
            self.checkpoint()
            self.connect()
            self.checkpoint()
        except BaseException:
            try:
                self.close()
            except Exception as e:
                self.log.warning(f"Connection cleanup failed: {e}")
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


driver_registry: Registry[type[Driver]] = Registry("driver")
