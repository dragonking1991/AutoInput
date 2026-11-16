QSS = """
* { font-family: "Segoe UI", "-apple-system", "SF Pro Text", "Helvetica Neue", "Inter", sans-serif; font-size: 13px; }
QMainWindow, QWidget { background: #1e1e2e; color: #cdd6f4; }
QLabel#h1 { font-size: 18px; font-weight: 600; }
QLabel#hint { color: #a6adc8; }
QLabel#error { color: #f38ba8; }
QLabel#ok { color: #a6e3a1; }
QLabel#countdown { font-size: 48px; font-weight: 700; color: #f9e2af; }

QListWidget#nav { background: #181825; border: none; padding: 8px; }
QListWidget#nav::item { padding: 12px 10px; border-radius: 6px; margin: 2px 0; }
QListWidget#nav::item:selected { background: #313244; color: #89b4fa; }
QListWidget#nav::item:disabled { color: #585b70; }

QFrame#dropzone { border: 2px dashed #45475a; border-radius: 10px; background: #181825; }
QFrame#dropzone[hover="true"] { border-color: #89b4fa; background: #1f2335; }

QPushButton { background: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 7px 14px; }
QPushButton:hover { background: #45475a; }
QPushButton:disabled { color: #585b70; border-color: #313244; }
QPushButton#primary { background: #89b4fa; color: #1e1e2e; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #b4befe; }
QPushButton#danger { background: #f38ba8; color: #1e1e2e; border: none; font-weight: 600; }

QTableView, QTableWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #181825; border: 1px solid #313244; border-radius: 6px; padding: 4px;
    selection-background-color: #45475a;
}
QHeaderView::section { background: #313244; padding: 6px; border: none; font-weight: 600; }
QPlainTextEdit { font-family: "Cascadia Mono", "Consolas", "Menlo", "SF Mono", monospace; font-size: 12px; }
QGroupBox { border: 1px solid #313244; border-radius: 8px; margin-top: 14px; padding: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #89b4fa; }
QProgressBar { border: 1px solid #313244; border-radius: 6px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #89b4fa; border-radius: 6px; }
QStatusBar { background: #181825; color: #a6adc8; }
"""

STATUS_COLORS = {
    "pending": "#a6adc8",
    "invalid": "#fab387",
    "running": "#89b4fa",
    "done": "#a6e3a1",
    "failed": "#f38ba8",
    "skipped": "#6c7086",
}

STATUS_LABELS = {
    "pending": "Chờ",
    "invalid": "Dữ liệu lỗi",
    "running": "Đang nhập…",
    "done": "Xong",
    "failed": "Thất bại",
    "skipped": "Bỏ qua",
}
