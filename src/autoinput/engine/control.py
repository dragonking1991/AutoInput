from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from autoinput.domain import RowResult, RunCancelled, RunReport

EventKind = Literal["started", "countdown", "row_started", "row_finished", "paused", "finished"]


@dataclass(frozen=True, slots=True)
class RunEvent:
    kind: EventKind
    row: int | None = None
    position: int = 0  # 1-based position within this run
    total: int = 0
    result: RowResult | None = None
    report: RunReport | None = None
    message: str = ""


EventSink = Callable[[RunEvent], None]


class RunControl:
    """Thread-safe pause / resume / cancel. The runner calls `checkpoint()` between actions."""

    def __init__(self) -> None:
        self._running = threading.Event()
        self._running.set()
        self._cancelled = threading.Event()

    @property
    def is_paused(self) -> bool:
        return not self._running.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def cancel(self) -> None:
        self._cancelled.set()
        self._running.set()  # wake a paused runner so it can exit

    def checkpoint(self) -> None:
        self._running.wait()
        if self._cancelled.is_set():
            raise RunCancelled("Run cancelled by user")

    def sleep(self, seconds: float) -> None:
        """Interruptible sleep: returns early (raising) on cancel."""
        if self._cancelled.wait(seconds):
            raise RunCancelled("Run cancelled by user")
