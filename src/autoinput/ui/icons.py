from typing import Literal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

IconName = Literal[
    "file", "mapping", "play", "back", "next", "log", "save", "check", "pause", "stop", "retry"
]


def app_icon_image(size: int = 1024) -> QImage:
    """App/installer icon: a form sheet with a 'fill' arrow on a blue tile. QImage only, so it
    can be rendered by the build script without a running QApplication."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 100, size / 100)
    gradient = QLinearGradient(0, 0, 100, 100)
    gradient.setColorAt(0, QColor("#3b82f6"))
    gradient.setColorAt(1, QColor("#1e3a8a"))
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(6, 6, 88, 88), 20, 20)
    p.fillPath(tile, gradient)
    sheet = QPainterPath()
    sheet.addRoundedRect(QRectF(27, 20, 46, 60), 6, 6)
    p.fillPath(sheet, QColor("#ffffff"))
    p.setPen(QPen(QColor("#93c5fd"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for y, end in ((34, 64), (46, 58)):
        p.drawLine(QPointF(35, y), QPointF(end, y))
    p.setPen(
        QPen(
            QColor("#2563eb"),
            5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    p.drawLine(QPointF(35, 62), QPointF(62, 62))
    p.drawPolyline([QPointF(55, 55), QPointF(62, 62), QPointF(55, 69)])
    p.end()
    return image


def app_icon() -> QIcon:
    result = QIcon()
    for size in (16, 32, 64, 128, 256, 512):
        result.addPixmap(QPixmap.fromImage(app_icon_image(size)))
    return result


def icon(name: IconName, color: str = "#405570") -> QIcon:
    """Draw resolution-independent line icons without font or image dependencies."""
    result = QIcon()
    for size in (20, 40, 60):
        image = QPixmap(size, size)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 24, size / 24)
        painter.setPen(
            QPen(
                QColor(color),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        paths = {
            "file": [(14, 3), (6, 3), (6, 21), (19, 21), (19, 8), (14, 3), (14, 8), (19, 8)],
            "mapping": [(5, 6), (19, 6), (15, 2), (19, 6), (15, 10)],
            "play": [(8, 4), (20, 12), (8, 20), (8, 4)],
            "back": [(14, 5), (7, 12), (14, 19)],
            "next": [(10, 5), (17, 12), (10, 19)],
            "log": [(8, 6), (21, 6)],
            "save": [
                (4, 3),
                (17, 3),
                (21, 7),
                (21, 21),
                (4, 21),
                (4, 3),
                (8, 3),
                (8, 9),
                (16, 9),
                (16, 3),
            ],
            "check": [(4, 12), (9, 17), (20, 6)],
            "pause": [(8, 5), (8, 19)],
            "stop": [(5, 5), (19, 5), (19, 19), (5, 19), (5, 5)],
            "retry": [(5, 8), (5, 3), (2, 6), (5, 8), (10, 8)],
        }
        path = QPainterPath()
        points = paths[name]
        path.moveTo(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)
        if name == "file":
            painter.drawLine(9, 13, 16, 13)
            painter.drawLine(9, 17, 14, 17)
        elif name == "mapping":
            painter.drawLine(19, 18, 5, 18)
            painter.drawLine(5, 18, 9, 14)
            painter.drawLine(5, 18, 9, 22)
        elif name == "log":
            for y in (6, 12, 18):
                painter.drawPoint(3, y)
                painter.drawLine(8, y, 21, y)
        elif name == "pause":
            painter.drawLine(16, 5, 16, 19)
        elif name == "save":
            painter.drawRect(8, 14, 9, 7)
        elif name == "retry":
            painter.drawArc(4, 4, 16, 16, -100 * 16, 280 * 16)
        painter.end()
        result.addPixmap(image)
    return result
