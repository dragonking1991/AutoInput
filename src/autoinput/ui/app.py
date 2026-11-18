import getpass
import os
import sys

from autoinput.infra.logging import get_logger, setup_logging
from autoinput.infra.settings import get_settings

_PARENT_ENV = "AUTOINPUT_GUI_PID"


def _spawned_by_running_gui() -> bool:
    """True when this process was started (directly or not) by a live AutoInput GUI.

    Child processes inherit the environment, so a GUI that somehow re-executes itself is
    detected here and refuses to open another window instead of multiplying.
    """
    parent = os.environ.get(_PARENT_ENV, "")
    if not parent.isdigit() or int(parent) == os.getpid():
        return False
    try:
        os.kill(int(parent), 0)
    except OSError:
        return False  # stale value from a process that has exited
    return True


def server_name() -> str:
    return f"autoinput-{getpass.getuser()}"


def main() -> None:
    if _spawned_by_running_gui():
        sys.exit(0)
    os.environ[_PARENT_ENV] = str(os.getpid())

    try:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.exit("PySide6 is not installed. Run: uv sync --extra gui")

    app = QApplication(sys.argv)
    app.setApplicationName("AutoInput")

    # Single instance: a second launch only brings the existing window to the front.
    probe = QLocalSocket()
    probe.connectToServer(server_name())
    if probe.waitForConnected(500):
        probe.write(b"show")
        probe.waitForBytesWritten(500)
        probe.disconnectFromServer()
        sys.exit(0)
    QLocalServer.removeServer(server_name())  # stale socket left by a crash
    server = QLocalServer()
    server.listen(server_name())

    from autoinput.ui.icons import app_icon
    from autoinput.ui.main_window import MainWindow
    from autoinput.ui.theme import apply_theme

    setup_logging()
    get_settings().seed_config()
    log = get_logger("ui")
    apply_theme(app)
    app.setWindowIcon(app_icon())

    def excepthook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        log.opt(exception=(exc_type, exc, tb)).error("Unhandled UI error")

    sys.excepthook = excepthook  # keep the app alive on slot errors; details go to the log
    window = MainWindow()

    def bring_to_front() -> None:
        while (conn := server.nextPendingConnection()) is not None:
            conn.disconnectFromServer()
        window.showNormal()
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(bring_to_front)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
