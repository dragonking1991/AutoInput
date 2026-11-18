from collections.abc import Callable
from time import monotonic

from PySide6.QtCore import QObject, QThread, Signal, Slot

from autoinput.domain import AutoInputError, Record, RunCancelled
from autoinput.engine import RunControl, RunEvent, Runner


class FunctionWorker(QObject):
    result = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(self, operation: Callable[[RunControl], object], control: RunControl) -> None:
        super().__init__()
        self.operation = operation
        self.control = control

    @Slot()
    def run(self) -> None:
        try:
            result = self.operation(self.control)
            self.control.checkpoint()
            self.result.emit(result)
        except RunCancelled:
            pass
        except Exception as e:
            self.failed.emit(
                e.message if isinstance(e, AutoInputError) else f"{type(e).__name__}: {e}"
            )
        finally:
            self.done.emit()


class BackgroundTask(QObject):
    result = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, operation: Callable[[RunControl], object], parent: QObject) -> None:
        super().__init__(parent)
        self.control = RunControl()
        self._thread = QThread(self)
        self.worker = FunctionWorker(operation, self.control)
        self.worker.moveToThread(self._thread)
        self._thread.started.connect(self.worker.run)
        self.worker.result.connect(self._result)
        self.worker.failed.connect(self._failed)
        self.worker.done.connect(self._thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self._thread.finished.connect(self.finished)

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self.control.cancel()

    @Slot(object)
    def _result(self, result: object) -> None:
        if not self.control.is_cancelled:
            self.result.emit(result)

    @Slot(str)
    def _failed(self, message: str) -> None:
        if not self.control.is_cancelled:
            self.failed.emit(message)


class RunWorker(QObject):
    """Runs the engine off the GUI thread. Signals are queued back to the GUI thread safely."""

    event_received = Signal(object)  # RunEvent
    rows_received = Signal(object)  # list[RunEvent]
    failed = Signal(str)
    done = Signal()

    def __init__(self, runner: Runner, records: list[Record], source_name: str) -> None:
        super().__init__()
        self.runner = runner
        self.records = records
        self.source_name = source_name
        self._events: list[RunEvent] = []
        self._last_flush = monotonic()
        runner.on_event = self._on_event

    def _flush(self) -> None:
        if self._events:
            self.rows_received.emit(self._events)
            self._events = []
        self._last_flush = monotonic()

    def _on_event(self, event: RunEvent) -> None:
        if event.kind in {"row_started", "row_finished"}:
            self._events.append(event)
            if (
                event.position == 1
                or len(self._events) >= 200
                or monotonic() - self._last_flush >= 0.05
            ):
                self._flush()
        else:
            self._flush()
            self.event_received.emit(event)

    @Slot()
    def run(self) -> None:
        try:
            self.runner.run(self.records, self.source_name)
        except AutoInputError as e:
            self.failed.emit(e.message)
        except Exception as e:  # never let a worker die silently
            self.failed.emit(f"{type(e).__name__}: {e}")
        finally:
            self._flush()
            self.done.emit()


def start_worker(worker: RunWorker) -> QThread:
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit)
    worker.done.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread


__all__ = ["RunEvent", "RunWorker", "start_worker"]
