from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableView, QVBoxLayout, QWidget

from autoinput.ui.state import AppState


class WizardPage(QWidget):
    """Base for wizard steps. Emit `complete_changed` whenever `is_complete()` may change."""

    title = ""
    description = ""
    complete_changed = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(20, 16, 20, 16)
        self.root.setSpacing(12)
        heading = QLabel(self.title)
        heading.setObjectName("h1")
        heading.setWordWrap(True)
        self.root.addWidget(heading)
        if self.description:
            description = message_label()
            description.setText(self.description)
            self.root.addWidget(description)

    def is_complete(self) -> bool:
        return True

    def on_enter(self) -> None:
        """Called when the page becomes visible."""


def message_label(object_name: str = "hint") -> QLabel:
    label = QLabel()
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def configure_table(table: QTableView) -> None:
    table.setAlternatingRowColors(True)
    table.setMinimumHeight(170)
    table.setWordWrap(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setDefaultSectionSize(44)
    table.horizontalHeader().setMinimumSectionSize(120)
    table.horizontalHeader().setDefaultSectionSize(180)
    table.horizontalHeader().setStretchLastSection(True)


def set_message(label: QLabel, text: str, kind: str = "hint") -> None:
    label.setObjectName(kind)
    label.setText(text)
    label.style().unpolish(label)
    label.style().polish(label)
