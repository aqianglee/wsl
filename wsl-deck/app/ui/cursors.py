"""統一的按鈕滑鼠游標。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def refresh_cursor(widget: QWidget) -> None:
    widget.setCursor(
        Qt.PointingHandCursor if widget.isEnabled() else Qt.ForbiddenCursor
    )
