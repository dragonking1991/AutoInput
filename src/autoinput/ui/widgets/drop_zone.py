from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout

from autoinput.sources import supported_extensions


class DropZone(QFrame):
    """Click to browse or drag & drop a supported file."""

    file_selected = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(120)

        exts = " ".join(supported_extensions())
        open_key = QKeySequence(QKeySequence.StandardKey.Open).toString(
            QKeySequence.SequenceFormat.NativeText
        )
        self.title = QLabel(f"Kéo thả file vào đây hoặc bấm để chọn  ({open_key})")
        self.title.setObjectName("h1")
        hint = QLabel(f"Hỗ trợ: {exts}")
        hint.setObjectName("hint")
        layout = QVBoxLayout(self)
        for w in (self.title, hint):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(w)

    def browse(self) -> None:
        patterns = " ".join(f"*{e}" for e in supported_extensions())
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file dữ liệu", "", f"Dữ liệu ({patterns})"
        )
        if path:
            self.file_selected.emit(Path(path))

    def show_file(self, path: Path) -> None:
        self.title.setText(f"📄 {path.name}")

    def _set_hover(self, on: bool) -> None:
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.browse()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and Path(urls[0].toLocalFile()).suffix.lower() in supported_extensions():
            event.acceptProposedAction()
            self._set_hover(True)

    def dragLeaveEvent(self, event: object) -> None:
        self._set_hover(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_hover(False)
        self.file_selected.emit(Path(event.mimeData().urls()[0].toLocalFile()))
