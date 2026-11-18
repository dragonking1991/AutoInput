from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from autoinput.domain import Record, RowStatus
from autoinput.ui.theme import STATUS_COLORS, STATUS_LABELS

_Index = QModelIndex | QPersistentModelIndex


class RecordsModel(QAbstractTableModel):
    """Virtualized table of records with an optional status column (handles 100k rows smoothly)."""

    def __init__(
        self,
        with_status: bool = False,
        status_overrides: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._with_status = with_status
        self._columns: list[str] = []
        self._headers: dict[str, str] = {}
        self._rows: list[Record] = []
        self._status: dict[int, tuple[RowStatus, str]] = {}
        self._pos: dict[int, int] = {}
        self._overrides = status_overrides or {}

    def set_data(
        self, columns: list[str], rows: list[Record], headers: dict[str, str] | None = None
    ) -> None:
        self.beginResetModel()
        self._columns, self._rows = columns, rows
        self._headers = headers or {}
        self._pos = {r.index: i for i, r in enumerate(rows)}
        self._status.clear()
        self.endResetModel()

    def set_status_overrides(self, overrides: dict[str, tuple[str, str]]) -> None:
        """Context-specific (label, color) per status, e.g. 'done' → 'Đã chạy thử' in dry-run."""
        self._overrides = overrides
        if self._rows and self._with_status:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0))

    def set_status(self, row_index: int, status: RowStatus, message: str = "") -> None:
        self._status[row_index] = (status, message)
        if (pos := self._pos.get(row_index)) is not None and self._with_status:
            self.dataChanged.emit(self.index(pos, 0), self.index(pos, 1))

    def position_of(self, row_index: int) -> int | None:
        return self._pos.get(row_index)

    # ── Qt model API ──
    def _offset(self) -> int:
        return 2 if self._with_status else 0

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._columns) + self._offset()

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(self._rows[section].index)
        if self._with_status and section < 2:
            return ("Trạng thái", "Ghi chú")[section]
        column = self._columns[section - self._offset()]
        return self._headers.get(column, column)

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        record = self._rows[index.row()]
        col = index.column()
        status, message = self._status.get(record.index, (RowStatus.PENDING, ""))
        if self._with_status and col < 2:
            label, color = self._overrides.get(
                status.value, (STATUS_LABELS[status.value], STATUS_COLORS[status.value])
            )
            if role == Qt.ItemDataRole.DisplayRole:
                return label if col == 0 else message
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(color)
            if role == Qt.ItemDataRole.ToolTipRole:
                return message or None
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return record.data.get(self._columns[col - self._offset()], "")
        return None
