from loguru import logger
from PySide6.QtCore import QObject, Signal


class LogBridge(QObject):
    """loguru sink -> Qt signal, so logs from any thread land safely in the GUI."""

    line = Signal(str)

    def install(self, level: str = "INFO") -> int:
        return logger.add(
            lambda msg: self.line.emit(msg.rstrip()),
            level=level,
            format="{time:HH:mm:ss} | {level: <7} | {extra[flow]: <7} | {message}",
        )
