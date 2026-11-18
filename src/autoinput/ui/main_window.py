from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from autoinput import __version__
from autoinput.infra.settings import get_settings
from autoinput.ui.icons import IconName, icon
from autoinput.ui.log_bridge import LogBridge
from autoinput.ui.pages import MappingPage, RunPage, SourcePage, WizardPage
from autoinput.ui.state import AppState


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AutoInput {__version__}")
        self.resize(1280, 800)
        self.setMinimumSize(900, 640)
        self.state = AppState()
        self._closing = False
        self._close_scheduled = False

        self.source_page = SourcePage(self.state)
        self.mapping_page = MappingPage(self.state)
        self.run_page = RunPage(self.state)
        self.pages: list[WizardPage] = [self.source_page, self.mapping_page, self.run_page]
        self.mapping_page.source_options_requested.connect(self.source_page.apply_options)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setWordWrap(True)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setIconSize(QSize(22, 22))
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(242)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 24, 16, 20)
        brand = QLabel("AutoInput")
        brand.setObjectName("brand")
        tagline = QLabel("Nhập liệu tự động")
        tagline.setObjectName("sidebarHint")
        side_layout.addWidget(brand)
        side_layout.addWidget(tagline)
        side_layout.addSpacing(24)
        side_layout.addWidget(self.nav, 1)
        side_hint = QLabel("Chọn dữ liệu → kiểm tra\n→ chạy an toàn")
        side_hint.setObjectName("sidebarHint")
        side_hint.setWordWrap(True)
        side_layout.addWidget(side_hint)
        steps: list[tuple[str, IconName]] = [
            ("1. Nguồn dữ liệu", "file"),
            ("2. Ánh xạ & kiểm tra", "mapping"),
            ("3. Chạy nhập liệu", "play"),
        ]
        self.stack = QStackedWidget()
        self._nav_icons = [icon(symbol, "#c5d3e6") for _label, symbol in steps]
        self._done_icon = icon("check", "#6ee7b7")
        for page, (label, symbol) in zip(self.pages, steps, strict=True):
            item = QListWidgetItem(icon(symbol, "#c5d3e6"), label)
            item.setToolTip(page.title)
            self.nav.addItem(item)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            page.complete_changed.connect(self._refresh_nav)
            page.complete_changed.connect(self._finish_close)
        self.nav.currentRowChanged.connect(self._go)

        self.back_btn = QPushButton("Quay lại")
        self.back_btn.setIcon(icon("back"))
        self.next_btn = QPushButton("Tiếp tục")
        self.next_btn.setIcon(icon("next", "#ffffff"))
        self.next_btn.setObjectName("primary")
        self.back_btn.clicked.connect(lambda: self.nav.setCurrentRow(self.stack.currentIndex() - 1))
        self.next_btn.clicked.connect(lambda: self.nav.setCurrentRow(self.stack.currentIndex() + 1))
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 0, 20, 8)
        footer.setSpacing(10)
        footer.addWidget(self.back_btn)
        self.step_label = QLabel()
        self.step_label.setObjectName("hint")
        footer.addWidget(self.step_label)
        footer.addStretch()
        self.log_btn = QPushButton("Nhật ký")
        self.log_btn.setIcon(icon("log"))
        self.log_btn.setCheckable(True)
        footer.addWidget(self.log_btn)
        footer.addWidget(self.next_btn)

        right = QVBoxLayout()
        right.addWidget(self.stack, 1)
        right.addLayout(footer)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 8)
        body.setSpacing(0)
        body.addWidget(sidebar)
        body.addLayout(right, 1)
        central = QWidget()
        central.setLayout(body)
        self.setCentralWidget(central)

        self._setup_log_dock()
        self.log_btn.toggled.connect(self.log_dock.setVisible)
        self.log_dock.visibilityChanged.connect(self.log_btn.setChecked)
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
        self._log_sink: int | None = self._log_bridge.install()
        dock = QDockWidget("Nhật ký hoạt động", self)
        self.log_dock = dock
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        view_menu = self.menuBar().addMenu("&Xem")
        view_menu.addAction(dock.toggleViewAction())
        view_menu.addAction("Mở thư mục cấu hình && nhật ký", self._open_data_dir)
        self.resizeDocks([dock], [170], Qt.Orientation.Vertical)
        dock.hide()

    def _open_data_dir(self) -> None:
        directory = get_settings().data_dir
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def _open_file(self) -> None:
        if self.run_page.is_running or self._closing:
            return
        self.nav.setCurrentRow(0)
        self.source_page.browse()

    def _reachable(self, index: int) -> bool:
        """A step is reachable only if all previous steps are complete."""
        return all(p.is_complete() for p in self.pages[:index])

    def _refresh_nav(self) -> None:
        running = self.run_page.is_running
        self.source_page.setEnabled(not running and not self._closing)
        self.mapping_page.setEnabled(not running and not self._closing)
        self.run_page.setEnabled(not self._closing)
        for i in range(self.nav.count()):
            enabled = self._reachable(i) and not running and not self._closing
            item = self.nav.item(i)
            flags = item.flags()
            item.setFlags(
                flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled
            )
            # The last step has no "done" state of its own; earlier steps show a check when ready.
            done = i < len(self.pages) - 1 and self.pages[i].is_complete()
            item.setIcon(self._done_icon if done else self._nav_icons[i])
        current = self.stack.currentIndex()
        self.step_label.setText(f"Bước {current + 1} / {len(self.pages)}")
        self.back_btn.setEnabled(current > 0 and not running and not self._closing)
        has_next = current < len(self.pages) - 1
        self.next_btn.setVisible(has_next)
        self.next_btn.setEnabled(
            has_next and self.pages[current].is_complete() and not running and not self._closing
        )

    def _go(self, index: int) -> None:
        if self.stack.currentIndex() == 1 and index == 2:
            self.mapping_page.flush_edits()
        if index < 0 or not self._reachable(index) or self.run_page.is_running or self._closing:
            self.nav.setCurrentRow(self.stack.currentIndex())
            return
        self.stack.setCurrentIndex(index)
        self.pages[index].on_enter()
        self._refresh_nav()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.run_page.is_running and not self._closing:
            answer = QMessageBox.question(self, "Đang chạy", "Đang nhập liệu. Dừng và thoát?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if self.run_page.is_running or self.source_page.is_busy or self.mapping_page.is_busy:
            event.ignore()
            self._closing = True
            self.source_page.cancel()
            self.mapping_page.cancel()
            self.run_page.stop()
            self._refresh_nav()
            return
        self.source_page.cancel()
        self.mapping_page.cancel()
        if self._log_sink is not None:
            from loguru import logger

            logger.remove(self._log_sink)
            self._log_sink = None
        event.accept()

    def _finish_close(self) -> None:
        if (
            self._closing
            and not self._close_scheduled
            and not (
                self.run_page.is_running or self.source_page.is_busy or self.mapping_page.is_busy
            )
        ):
            self._close_scheduled = True
            QTimer.singleShot(0, self.close)
