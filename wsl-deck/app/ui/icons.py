"""以 QPainter 產生的 Instance 圖標，供卡片與表格共用。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

ICON_SIZE = 14
ACTIVE_ICON_COLOR = "#ffffff"
INACTIVE_ICON_COLOR = "#5f6368"
SETTINGS_ICON_COLOR = "#2D7FF9"


def play_pixmap(size: int = ICON_SIZE, color: str = "#2ecc71") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(size * 0.26, size * 0.14),
                QPointF(size * 0.86, size * 0.5),
                QPointF(size * 0.26, size * 0.86),
            ]
        )
    )
    painter.end()
    return pixmap


def stop_pixmap(size: int = ICON_SIZE, color: str = "#e74c3c") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(
        QRectF(size * 0.2, size * 0.2, size * 0.6, size * 0.6),
        2,
        2,
    )
    painter.end()
    return pixmap


def heart_pixmap(size: int = 18, color: str = "#e74c3c") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(size * 0.5, size * 0.9)
    path.cubicTo(size * 0.12, size * 0.62, size * 0.02, size * 0.32, size * 0.2, size * 0.18)
    path.cubicTo(size * 0.33, size * 0.08, size * 0.45, size * 0.12, size * 0.5, size * 0.28)
    path.cubicTo(size * 0.55, size * 0.12, size * 0.67, size * 0.08, size * 0.8, size * 0.18)
    path.cubicTo(size * 0.98, size * 0.32, size * 0.88, size * 0.62, size * 0.5, size * 0.9)
    painter.drawPath(path)
    painter.end()
    return pixmap


def prohibition_pixmap(size: int = 18) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#e74c3c"))
    pen.setWidth(2)
    painter.setPen(pen)
    margin = 1
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.drawLine(margin + 2, size - margin - 2, size - margin - 2, margin + 2)
    painter.end()
    return pixmap


def list_pixmap(size: int = 16, color: str = INACTIVE_ICON_COLOR) -> QPixmap:
    """列表圖標：左側方點 + 三條橫線。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    row_height = size / 4
    for index in range(3):
        top = size * 0.2 + index * row_height
        painter.drawRoundedRect(
            QRectF(size * 0.1, top, size * 0.12, size * 0.12), 1, 1
        )
        painter.drawRoundedRect(
            QRectF(size * 0.32, top + size * 0.02, size * 0.56, size * 0.08), 1, 1
        )
    painter.end()
    return pixmap


def grid_pixmap(size: int = 16, color: str = INACTIVE_ICON_COLOR) -> QPixmap:
    """卡片圖標：2×2 圓角方塊。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    block = size * 0.38
    gap = size * 0.1
    for row in range(2):
        for column in range(2):
            painter.drawRoundedRect(
                QRectF(
                    size * 0.06 + column * (block + gap),
                    size * 0.06 + row * (block + gap),
                    block,
                    block,
                ),
                2,
                2,
            )
    painter.end()
    return pixmap


def settings_pixmap(
    size: int = 16, color: str = SETTINGS_ICON_COLOR, scale: float = 1.0
) -> QPixmap:
    """齒輪圖標：圓環 + 六個圓角齒，不依賴字體。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    center = size / 2
    unit = size * scale
    ring_outer = unit * 0.3
    ring_inner = unit * 0.18
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    path.addEllipse(QPointF(center, center), ring_outer, ring_outer)
    path.addEllipse(QPointF(center, center), ring_inner, ring_inner)
    painter.drawPath(path)

    tooth_width = unit * 0.16
    tooth_height = unit * 0.16
    radius = unit * 0.04
    for angle in range(0, 360, 60):
        painter.save()
        painter.translate(center, center)
        painter.rotate(angle)
        painter.drawRoundedRect(
            QRectF(-tooth_width / 2, -unit * 0.42, tooth_width, tooth_height),
            radius,
            radius,
        )
        painter.restore()
    painter.end()
    return pixmap


def settings_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        icon.addPixmap(settings_pixmap(size))
    return icon


def settings_fab_icon() -> QIcon:
    """右下角 FAB 專用：28px 畫布，齒輪本體約 20px。"""
    icon = QIcon()
    for size in (28, 56):
        icon.addPixmap(settings_pixmap(size, scale=0.85))
    return icon


def _two_state_icon(
    off_pixmap: QPixmap,
    on_pixmap: QPixmap,
) -> QIcon:
    icon = QIcon()
    icon.addPixmap(off_pixmap, QIcon.Normal, QIcon.Off)
    icon.addPixmap(on_pixmap, QIcon.Normal, QIcon.On)
    return icon


def list_icon() -> QIcon:
    return _two_state_icon(
        list_pixmap(color=INACTIVE_ICON_COLOR),
        list_pixmap(color=ACTIVE_ICON_COLOR),
    )


def grid_icon() -> QIcon:
    return _two_state_icon(
        grid_pixmap(color=INACTIVE_ICON_COLOR),
        grid_pixmap(color=ACTIVE_ICON_COLOR),
    )
