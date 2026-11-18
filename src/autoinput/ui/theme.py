from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

QSS = """
* { font-family: "Segoe UI", "Helvetica Neue", sans-serif; font-size: 13px; }
QWidget { color: #233148; }
QMainWindow, QStackedWidget, QScrollArea, QWidget#page { background: #f3f6fb; }
QLabel { background: transparent; }
QLabel#h1 { font-size: 23px; font-weight: 700; color: #14233b; }
QLabel#hint { color: #63748b; }
QLabel#error { color: #b42338; }
QLabel#ok { color: #147253; }
QLabel#countdown { font-size: 42px; font-weight: 700; color: #a46109; }
QFrame#sidebar { background: #15243b; border: none; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #ffffff; }
QLabel#sidebarHint { color: #b8c8de; }
QListWidget#nav { background: transparent; border: none; outline: none; }
QListWidget#nav::item { padding: 14px 10px; border-radius: 8px; margin: 4px 0; color: #c5d3e6; }
QListWidget#nav::item:selected { background: #284669; color: #ffffff; }
QListWidget#nav::item:disabled { color: #879ab4; }
QFrame#dropzone { border: 2px dashed #b6c8e2; border-radius: 12px; background: #ffffff; }
QFrame#dropzone[hover="true"] { border-color: #2563eb; background: #eaf1ff; }
QPushButton, QToolButton {
    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 7px;
    padding: 8px 12px; min-height: 20px; font-weight: 500;
}
QPushButton:hover, QToolButton:hover { background: #edf3ff; border-color: #93b3ee; }
QPushButton:focus, QToolButton:focus { border: 1px solid #2563eb; }
QPushButton:disabled { background: #edf1f6; color: #8290a3; border-color: #dce3ed; }
QPushButton#primary { background: #2563eb; color: #ffffff; border-color: #2563eb; font-weight: 600; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:disabled { background: #dce7fa; color: #647a9b; border-color: #dce7fa; }
QPushButton#danger { background: #fff1f2; color: #b42338; border-color: #fecdd3; }
QPushButton#danger:disabled { background: #edf1f6; color: #8290a3; border-color: #dce3ed; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;
    padding: 7px 8px; min-height: 20px;
    selection-background-color: #dbeafe; selection-color: #14233b;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QLineEdit:disabled, QComboBox:disabled { background: #edf1f6; color: #8290a3; }
QSpinBox#headerRow::up-button, QSpinBox#headerRow::down-button {
    width: 0px; height: 0px; border: none;
}
QComboBox { padding-right: 26px; }
QComboBox::drop-down { width: 24px; border: none; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #dbeafe; }
QTableView, QTableWidget, QPlainTextEdit {
    background: #ffffff; alternate-background-color: #f8fafd;
    border: 1px solid #dce3ed; border-radius: 8px; gridline-color: #e8edf5;
    selection-background-color: #dbeafe; selection-color: #14233b;
}
QTableView::item { padding: 5px 8px; }
QHeaderView::section {
    background: #eaf0f8; padding: 9px 10px; border: none;
    border-bottom: 1px solid #dce3ed; font-weight: 600; color: #405570;
}
QPlainTextEdit { font-family: "Menlo", "Consolas", monospace; font-size: 12px; padding: 8px; }
QGroupBox {
    background: #ffffff; border: 1px solid #dce3ed; border-radius: 9px;
    margin-top: 12px; padding: 16px 12px 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #405570; font-weight: 600; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QProgressBar { background: #e5ecf5; border: none; border-radius: 6px; text-align: center; min-height: 22px; }
QProgressBar::chunk { background: #86b0f9; border-radius: 6px; }
QDockWidget { color: #405570; }
QDockWidget::title { background: #eaf0f8; padding: 8px; }
QScrollArea { border: none; }
QSplitter::handle { background: #e0e7f1; height: 6px; }
QToolTip { background: #15243b; color: #ffffff; border: none; padding: 7px; }
"""


def apply_theme(app: QApplication) -> None:
    # Fusion and an explicit palette keep native dark-mode controls from mixing with the theme.
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f3f6fb",
        QPalette.ColorRole.WindowText: "#233148",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f8fafd",
        QPalette.ColorRole.Text: "#233148",
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: "#233148",
        QPalette.ColorRole.Highlight: "#dbeafe",
        QPalette.ColorRole.HighlightedText: "#14233b",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(QSS)


STATUS_COLORS = {
    "pending": "#63748b",
    "invalid": "#9a5706",
    "running": "#1d4ed8",
    "done": "#147253",
    "failed": "#b42338",
    "needs_review": "#9a5706",
    "skipped": "#63748b",
}

STATUS_LABELS = {
    "pending": "Chờ",
    "invalid": "Dữ liệu lỗi",
    "running": "Đang nhập…",
    "done": "Xong",
    "failed": "Thất bại",
    "needs_review": "Cần đối soát",
    "skipped": "Bỏ qua",
}
