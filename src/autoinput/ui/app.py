import sys

from autoinput.infra.logging import get_logger, setup_logging


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.exit("PySide6 is not installed. Run: uv sync --extra gui")

    from autoinput.ui.main_window import MainWindow
    from autoinput.ui.theme import QSS

    setup_logging()
    log = get_logger("ui")
    app = QApplication(sys.argv)
    app.setApplicationName("AutoInput")
    app.setStyleSheet(QSS)

    def excepthook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        log.opt(exception=(exc_type, exc, tb)).error("Unhandled UI error")

    sys.excepthook = excepthook  # keep the app alive on slot errors; details go to the log
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
