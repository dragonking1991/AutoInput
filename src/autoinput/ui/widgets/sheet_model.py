"""Table model that renders an Excel sheet with its original look plus import-role markers."""

import re
from functools import cache
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTableView

from autoinput.sources.excel_format import CellStyle
from autoinput.sources.excel_source import ExcelPreview

_Index = QModelIndex | QPersistentModelIndex
BORDER_ROLE = Qt.ItemDataRole.UserRole + 1
WRAP_ROLE = Qt.ItemDataRole.UserRole + 2
_NUMBER = re.compile(r"^[-+(]?[\d.,\s%()]*\d[\d.,\s%()]*$")

ROLE_STYLE = {  # role -> (color, label)
    "header": ("#2563eb", "Dòng tiêu đề (tên cột)"),
    "data": ("#16a34a", "Dòng dữ liệu sẽ nhập"),
    "skip": ("#f59e0b", "Bỏ qua"),
    "title": ("#94a3b8", "Phía trên tiêu đề"),
}
_HORIZONTAL = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignHCenter,
    "right": Qt.AlignmentFlag.AlignRight,
}
_VERTICAL = {
    "top": Qt.AlignmentFlag.AlignTop,
    "center": Qt.AlignmentFlag.AlignVCenter,
    "bottom": Qt.AlignmentFlag.AlignBottom,
}
_WASH = QColor("#eef1f5")


@cache
def role_icon(role: str) -> QIcon:
    color = ROLE_STYLE.get(role, ROLE_STYLE["title"])[0]
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(4, 4, 16, 16, 5, 5)
    painter.end()
    return QIcon(pixmap)


def _blend(color: QColor, other: QColor, amount: float) -> QColor:
    return QColor(
        round(color.red() + (other.red() - color.red()) * amount),
        round(color.green() + (other.green() - color.green()) * amount),
        round(color.blue() + (other.blue() - color.blue()) * amount),
    )


@cache
def _font(style: CellStyle) -> QFont:
    font = QFont()
    if style.font:
        font.setFamilies([style.font, "Arial"])
    if style.size:
        font.setPixelSize(max(8, round(style.size * 96 / 72)))
    font.setBold(style.bold)
    font.setItalic(style.italic)
    font.setUnderline(style.underline)
    return font


class SheetModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.preview: ExcelPreview | None = None

    def set_preview(self, preview: ExcelPreview | None) -> None:
        self.beginResetModel()
        self.preview = preview
        self.endResetModel()

    def role_of(self, row: int) -> tuple[str, str]:
        if not self.preview or not self.preview.layout:
            return ("data", "")
        index = self.preview.rows[row].index
        return self.preview.layout.roles.get(index, ("skip", ""))

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() or not self.preview else len(self.preview.rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() or not self.preview else len(self.preview.columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not self.preview:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                return self.preview.columns[section]
            return None
        row_role, reason = self.role_of(section)
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self.preview.rows[section].index)
        if role == Qt.ItemDataRole.DecorationRole:
            return role_icon(row_role)
        if role == Qt.ItemDataRole.ToolTipRole:
            label = ROLE_STYLE.get(row_role, ROLE_STYLE["title"])[1]
            return f"Dòng {self.preview.rows[section].index}: {label}" + (
                f" – {reason}" if reason else ""
            )
        return None

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not self.preview:
            return None
        record = self.preview.rows[index.row()]
        column = self.preview.columns[index.column()]
        style = self.preview.styles.cells.get((index.row(), index.column()))
        row_role = self.role_of(index.row())[0]
        muted = row_role in {"skip", "title"}
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            text = record.data.get(column, "")
            return text if role == Qt.ItemDataRole.DisplayRole or len(text) > 12 else None
        if role == Qt.ItemDataRole.FontRole:
            return _font(style) if style else None
        if role == Qt.ItemDataRole.ForegroundRole:
            color = QColor(style.color) if style and style.color else QColor("#111827")
            return _blend(color, QColor("#ffffff"), 0.45) if muted else color
        if role == Qt.ItemDataRole.BackgroundRole:
            if style and style.background:
                color = QColor(style.background)
                return _blend(color, _WASH, 0.6) if muted else color
            return _WASH if muted else QColor("#ffffff")
        if role == Qt.ItemDataRole.TextAlignmentRole:
            text = record.data.get(column, "")
            horizontal = _HORIZONTAL.get(style.horizontal or "") if style else None
            if horizontal is None:
                numeric = (
                    bool(text) and text.replace(".", "").replace(",", "").lstrip("-").isdigit()
                )
                horizontal = Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
            vertical = (
                _VERTICAL.get(style.vertical or "", Qt.AlignmentFlag.AlignBottom)
                if style
                else Qt.AlignmentFlag.AlignVCenter
            )
            return int(horizontal | vertical)
        if role == BORDER_ROLE:
            return style.borders if style else None
        if role == WRAP_ROLE:
            return bool(style and style.wrap)
        return None


class SheetDelegate(QStyledItemDelegate):
    """Draws Excel borders and honours per-cell wrapping."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: _Index) -> None:
        super().initStyleOption(option, index)
        if index.data(WRAP_ROLE):
            option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        else:
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.WrapText
            option.textElideMode = Qt.TextElideMode.ElideNone

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: _Index) -> None:
        super().paint(painter, option, index)
        borders = index.data(BORDER_ROLE)
        if not borders or not any(borders):
            return
        rect: QRect = option.rect
        painter.save()
        painter.setPen(QPen(QColor("#4b5563"), 1))
        top, right, bottom, left = borders
        if top:
            painter.drawLine(rect.topLeft(), rect.topRight())
        if right:
            painter.drawLine(rect.topRight(), rect.bottomRight())
        if bottom:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if left:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        painter.restore()


def apply_sheet_geometry(table: QTableView, preview: ExcelPreview) -> None:
    """Excel column widths, row heights, hidden rows/columns and merged cells."""
    styles = preview.styles
    horizontal, vertical = table.horizontalHeader(), table.verticalHeader()
    horizontal.setStretchLastSection(False)
    horizontal.setMinimumSectionSize(4)
    vertical.setMinimumSectionSize(12)
    widths = [
        styles.column_widths.get(c, styles.default_width) or 64 for c in range(len(preview.columns))
    ]
    heights = [
        max(18, styles.row_heights.get(r, styles.default_height)) for r in range(len(preview.rows))
    ]
    covered = {
        (r, c)
        for top, left, height, width in preview.spans
        for r in range(top, top + height)
        for c in range(left, left + width)
    }
    base = table.font()
    for r, record in enumerate(preview.rows):
        for c, column in enumerate(preview.columns):
            text = record.data.get(column, "")
            style = styles.cells.get((r, c))
            font = _font(style) if style else base
            if style and style.size and r not in styles.row_heights:
                # Excel grows rows without a fixed height to fit bigger fonts.
                heights[r] = max(heights[r], QFontMetrics(font).height() + 4)
            if text and (r, c) not in covered and _NUMBER.match(text):
                # Excel would show ##### here; widen instead so numbers are never cut.
                widths[c] = max(widths[c], QFontMetrics(font).horizontalAdvance(text) + 10)
    for col, width in enumerate(widths):
        table.setColumnWidth(col, width)
        table.setColumnHidden(col, col in styles.hidden_columns)
    for row, height in enumerate(heights):
        table.setRowHeight(row, height)
        table.setRowHidden(row, row in styles.hidden_rows)
    for top, left, height, width in preview.spans:
        table.setSpan(top, left, height, width)
