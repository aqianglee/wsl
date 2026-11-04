"""App 圖標：優先載入 assets 內的 ICO，缺失時回退到內建繪製。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from app.paths import app_dir

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
ASSET_NAME = "wsl-deck-icon.ico"


def asset_path() -> Path:
    """開發態在 app_dir()；凍結後 PyInstaller 把資源放在 _internal（sys._MEIPASS）。"""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / "assets" / ASSET_NAME


def app_pixmap(size: int) -> QPixmap:
    """繪製單一尺寸的 App 圖標，僅在資產缺失時作為回退。"""
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
    """優先使用 assets 內的 ICO；缺失時回退到內建繪製。"""
    path = asset_path()
    if path.is_file():
        return QIcon(str(path))
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(app_pixmap(size))
    return icon
