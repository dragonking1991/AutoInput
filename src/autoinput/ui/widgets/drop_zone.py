from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout

from autoinput.sources import supported_extensions
from autoinput.ui.icons import icon


class DropZone(QFrame):
    """Click to browse or drag & drop a supported file."""

    file_selected = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(170)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Chọn file dữ liệu")

        exts = " ".join(supported_extensions())
        open_key = QKeySequence(QKeySequence.StandardKey.Open).toString(
            QKeySequence.SequenceFormat.NativeText
        )
        illustration = QLabel()
        illustration.setPixmap(icon("file", "#2563eb").pixmap(36, 36))
        self.title = QLabel("Kéo thả hoặc bấm để chọn file")
        self.title.setStyleSheet("font-size: 16px; font-weight: 600;")
        hint = QLabel(f"CSV · Excel · JSON · XML\nMở file: {open_key}")
        hint.setToolTip(f"Định dạng hỗ trợ: {exts}")
        hint.setObjectName("hint")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        for w in (illustration, self.title, hint):
            w.setWordWrap(True)
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
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
        # Permit wrapping long filenames without changing the displayed filename.
        self.title.setText("\u200b".join(path.name))
        self.title.setToolTip(str(path))

    def _set_hover(self, on: bool) -> None:
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.browse()
        else:
            super().keyPressEvent(event)

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
