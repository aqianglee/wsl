"""主頁視圖切換：列表／卡片兩顆互斥圖標按鈕。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from app.ui.cursors import refresh_cursor
from app.ui.icons import grid_icon, list_icon
from app.ui.theme import PRIMARY_COLOR

BUTTON_SIZE = 32
ICON_SIZE = 16

VIEW_STYLE = """
QToolButton#viewToggleLeft, QToolButton#viewToggleRight {
    background: palette(button);
    border: 1px solid palette(mid);
}
QToolButton#viewToggleLeft {
    border-top-left-radius: 7px;
    border-bottom-left-radius: 7px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
}
QToolButton#viewToggleRight {
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: none;
}
QToolButton#viewToggleLeft:hover, QToolButton#viewToggleRight:hover {
    background: palette(midlight);
    border-color: #4a90e2;
}
QToolButton#viewToggleLeft:checked, QToolButton#viewToggleRight:checked {
    background: %s;
    border-color: %s;
}
QToolButton#viewToggleLeft:checked:hover, QToolButton#viewToggleRight:checked:hover {
    background: #1F66CC;
    border-color: #1F66CC;
}
""" % (PRIMARY_COLOR, PRIMARY_COLOR)


class ViewToggle(QWidget):
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(VIEW_STYLE)
        self._mode = "card"
        self._buttons: dict[str, QToolButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for mode, icon, tooltip in (
            ("card", grid_icon(), "卡片視圖"),
            ("list", list_icon(), "表格視圖"),
        ):
            button = QToolButton(self)
            button.setObjectName(
                "viewToggleLeft" if mode == "card" else "viewToggleRight"
            )
            button.setCheckable(True)
            button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
            button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            button.setIcon(icon)
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _checked=False, value=mode: self._on_clicked(value)
            )
            group.addButton(button)
            layout.addWidget(button)
            self._buttons[mode] = button
            refresh_cursor(button)

        self._buttons["card"].setChecked(True)

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in self._buttons:
            mode = "card"
        self._mode = mode
        self._buttons[mode].setChecked(True)

    def _on_clicked(self, mode: str) -> None:
        if mode == self._mode:
            self._buttons[mode].setChecked(True)
            return
        self._mode = mode
        self.mode_changed.emit(mode)
