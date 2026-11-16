from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from autoinput import __version__
from autoinput.ui.log_bridge import LogBridge
from autoinput.ui.pages import MappingPage, RunPage, SourcePage, WizardPage
from autoinput.ui.state import AppState


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AutoInput {__version__}")
        self.resize(1280, 800)
        self.state = AppState()

        self.source_page = SourcePage(self.state)
        self.mapping_page = MappingPage(self.state)
        self.run_page = RunPage(self.state)
        self.pages: list[WizardPage] = [self.source_page, self.mapping_page, self.run_page]

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(220)
        self.stack = QStackedWidget()
        for page in self.pages:
            self.nav.addItem(QListWidgetItem(page.title))
            self.stack.addWidget(page)
            page.complete_changed.connect(self._refresh_nav)
        self.nav.currentRowChanged.connect(self._go)

        self.back_btn = QPushButton("← Quay lại")
        self.next_btn = QPushButton("Tiếp tục →")
        self.next_btn.setObjectName("primary")
        self.back_btn.clicked.connect(lambda: self.nav.setCurrentRow(self.stack.currentIndex() - 1))
        self.next_btn.clicked.connect(lambda: self.nav.setCurrentRow(self.stack.currentIndex() + 1))
        footer = QHBoxLayout()
        footer.addWidget(self.back_btn)
        footer.addStretch()
        footer.addWidget(self.next_btn)

        right = QVBoxLayout()
        right.addWidget(self.stack, 1)
        right.addLayout(footer)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 12, 12)
        body.addWidget(self.nav)
        body.addLayout(right, 1)
        central = QWidget()
        central.setLayout(body)
        self.setCentralWidget(central)

        self._setup_log_dock()
        QShortcut(QKeySequence.StandardKey.Open, self, self._open_file)
        self.state.source_changed.connect(self._refresh_nav)
        self.state.mapping_changed.connect(self._refresh_nav)
        self.nav.setCurrentRow(0)
        self._refresh_nav()

    def _setup_log_dock(self) -> None:
        view = QPlainTextEdit(readOnly=True)
        view.setMaximumBlockCount(5000)
        self._log_bridge = LogBridge()
        self._log_bridge.line.connect(view.appendPlainText)
        self._log_bridge.install()
        dock = QDockWidget("Nhật ký", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.menuBar().addMenu("&Xem").addAction(dock.toggleViewAction())

    def _open_file(self) -> None:
        self.nav.setCurrentRow(0)
        self.source_page.browse()

    def _reachable(self, index: int) -> bool:
        """A step is reachable only if all previous steps are complete."""
        return all(p.is_complete() for p in self.pages[:index])

    def _refresh_nav(self) -> None:
        running = self.run_page.is_running
        for i in range(self.nav.count()):
            enabled = self._reachable(i) and not running
            item = self.nav.item(i)
            flags = item.flags()
            item.setFlags(
                flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled
            )
        current = self.stack.currentIndex()
        self.back_btn.setEnabled(current > 0 and not running)
        has_next = current < len(self.pages) - 1
        self.next_btn.setVisible(has_next)
        self.next_btn.setEnabled(has_next and self.pages[current].is_complete())

    def _go(self, index: int) -> None:
        if index < 0 or not self._reachable(index):
            self.nav.setCurrentRow(self.stack.currentIndex())
            return
        self.stack.setCurrentIndex(index)
        self.pages[index].on_enter()
        self._refresh_nav()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.run_page.is_running:
            answer = QMessageBox.question(self, "Đang chạy", "Đang nhập liệu. Dừng và thoát?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.run_page.stop()
        event.accept()
