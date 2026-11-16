from typing import Any


class AutoInputError(Exception):
    """Base error. `context` carries structured details for logs and the UI."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class SourceError(AutoInputError):
    pass


class ConfigError(AutoInputError):
    pass


class MappingError(AutoInputError):
    pass


class DriverError(AutoInputError):
    pass


class RunCancelled(AutoInputError):
    pass
