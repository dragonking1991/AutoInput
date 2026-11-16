from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Name -> plugin lookup shared by sources, transforms and drivers."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, T] = {}

    def register(self, *keys: str) -> Callable[[T], T]:
        def decorator(item: T) -> T:
            for key in keys:
                normalized = key.lower()
                if normalized in self._items:
                    raise ValueError(f"{self._kind} '{key}' is already registered")
                self._items[normalized] = item
            return item

        return decorator

    def get(self, key: str) -> T:
        try:
            return self._items[key.lower()]
        except KeyError:
            available = ", ".join(sorted(self._items)) or "none"
            raise KeyError(f"Unknown {self._kind} '{key}'. Available: {available}") from None

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._items

    def keys(self) -> list[str]:
        return sorted(self._items)
