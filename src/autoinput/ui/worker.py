from PySide6.QtCore import QObject, QThread, Signal, Slot

from autoinput.domain import AutoInputError, Record
from autoinput.engine import RunEvent, Runner


class RunWorker(QObject):
    """Runs the engine off the GUI thread. Signals are queued back to the GUI thread safely."""

    event = Signal(object)  # RunEvent
    failed = Signal(str)
    done = Signal()

    def __init__(self, runner: Runner, records: list[Record], source_name: str) -> None:
        super().__init__()
        self.runner = runner
        self.records = records
        self.source_name = source_name
        runner.on_event = self.event.emit

    @Slot()
    def run(self) -> None:
        try:
            self.runner.run(self.records, self.source_name)
        except AutoInputError as e:
            self.failed.emit(e.message)
        except Exception as e:  # never let a worker die silently
            self.failed.emit(f"{type(e).__name__}: {e}")
        finally:
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
