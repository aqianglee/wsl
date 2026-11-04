"""以 QPainter 產生圖標，不依賴外部圖檔。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def app_pixmap(size: int) -> QPixmap:
    """繪製單一尺寸的 App 圖標，供視窗圖標與打包用 ICO 共用。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2d7ff9"))
    painter.drawRoundedRect(
        1, 1, size - 2, size - 2, size * 0.22, size * 0.22
    )
    font = QFont("Segoe UI")
    font.setBold(True)
    font.setPixelSize(max(6, int(size * 0.58)))
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(app_pixmap(size))
    return icon
