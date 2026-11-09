"""共用對話框基底：可滾動內容＋白 footer、表單、錯誤訊息與底部按鈕。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.cursors import refresh_cursor
from app.ui.theme import PRIMARY_COLOR

FORM_CONTROL_HEIGHT = 32


class _ContentScrollArea(QScrollArea):
    """高度跟隨內容的滾動區：sizeHint 回報內容高度（受最大高度限制）。"""

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        widget = self.widget()
        if widget is not None:
            hint.setHeight(min(widget.sizeHint().height(), self.maximumHeight()))
        return hint

DIALOG_STYLE = f"""
QFrame#dialogFooter {{
    background: palette(base);
    border-top: 1px solid rgba(128, 128, 128, 45);
}}
QPushButton#dialogOk {{
    background: {PRIMARY_COLOR};
    border: 1px solid {PRIMARY_COLOR};
    border-radius: 7px;
    color: #FFFFFF;
}}
QPushButton#dialogOk:hover {{
    background: #1F66CC;
    border-color: #1F66CC;
}}
QPushButton#dialogOk:pressed {{
    background: #1F66CC;
    border-color: #1F66CC;
}}
QPushButton#dialogOk:disabled {{
    background: palette(midlight);
    border-color: palette(midlight);
    color: #9aa0a6;
}}
"""

CARD_STYLE = """
QFrame#sectionCard {
    background: palette(base);
    border: 1px solid rgba(128, 128, 128, 30);
    border-radius: 10px;
}
"""


def card_title_font() -> QFont:
    font = QFont()
    font.setPointSize(12)
    font.setBold(True)
    return font


def make_card(parent: QWidget, title: str) -> tuple[QFrame, QVBoxLayout]:
    """建立與詳情頁一致的圓角分組卡片，回傳（卡片, 內容 layout）。"""
    card = QFrame(parent)
    card.setObjectName("sectionCard")
    card.setStyleSheet(CARD_STYLE)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)
    title_label = QLabel(title, card)
    title_label.setFont(card_title_font())
    layout.addWidget(title_label)
    return card, layout


class DialogBase(QDialog):
    def __init__(self, title: str, parent=None, width: int = 560):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.setStyleSheet(DIALOG_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget(self)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(12)

        scroll = _ContentScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        content.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            scroll.setMaximumHeight(
                max(200, screen.availableGeometry().height() - 120)
            )
        root.addWidget(scroll, 1)

        self._form = QFormLayout()
        self._form.setSpacing(10)
        self._layout.addLayout(self._form)

        self._error = QLabel("", content)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        footer = QFrame(self)
        footer.setObjectName("dialogFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch(1)
        self._cancel_btn = QPushButton("取消", footer)
        self._ok_btn = QPushButton("確定", footer)
        self._ok_btn.setObjectName("dialogOk")
        for button in (self._cancel_btn, self._ok_btn):
            button.setMinimumHeight(32)
            button.setMinimumWidth(96)
            refresh_cursor(button)
        self._cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self._cancel_btn)
        footer_layout.addWidget(self._ok_btn)
        root.addWidget(footer)

    def set_ok_text(self, text: str) -> None:
        self._ok_btn.setText(text)

    def show_error(self, message: str) -> None:
        self._error.setText(message)

    def add_info(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray;")
        self._layout.insertWidget(self._layout.indexOf(self._error), label)
        return label

    def _row_with_button(self, edit: QLineEdit, text: str, slot) -> QWidget:
        edit.setFixedHeight(FORM_CONTROL_HEIGHT)
        button = QPushButton(text, self)
        button.setFixedHeight(FORM_CONTROL_HEIGHT)
        button.clicked.connect(slot)
        refresh_cursor(button)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(edit, 1)
        row.addWidget(button)
        widget = QWidget(self)
        widget.setLayout(row)
        return widget
