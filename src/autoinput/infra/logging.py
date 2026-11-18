import sys
from typing import Literal

from loguru import logger

from autoinput.infra.settings import get_settings

Flow = Literal["app", "source", "mapping", "driver", "engine", "ui"]

_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | flow={extra[flow]: <7} | "
    "{name}:{line} | {message}"
)
_configured = False


def setup_logging(level: str | None = None) -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.configure(extra={"flow": "app"})
    if sys.stderr is not None:  # None in windowed PyInstaller builds
        logger.add(sys.stderr, level=level or settings.log_level, format=_FORMAT, colorize=True)
    logger.add(
        settings.logs_dir / "autoinput.log",
        level="DEBUG",
        format=_FORMAT,
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        # Never enqueue=True: it creates multiprocessing primitives that start a resource-tracker
        # process by re-executing sys.executable — in a packaged app that relaunches AutoInput
        # itself, endlessly. loguru sinks are already thread-safe without it.
        enqueue=False,
    )
    _configured = True


def get_logger(flow: Flow):
    return logger.bind(flow=flow)


def mask(value: str) -> str:
    return "•" * max(len(value) - 2, 0) + value[-2:] if value else ""
