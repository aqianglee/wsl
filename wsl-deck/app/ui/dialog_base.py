"""共用對話框基底：表單、錯誤訊息與底部按鈕。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.cursors import refresh_cursor

FORM_CONTROL_HEIGHT = 32


class DialogBase(QDialog):
    def __init__(self, title: str, parent=None, width: int = 560):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 16)
        self._layout.setSpacing(10)

        self._form = QFormLayout()
        self._form.setSpacing(10)
        self._layout.addLayout(self._form)

        self._error = QLabel("", self)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_btn = QPushButton("取消", self)
        self._ok_btn = QPushButton("確定", self)
        for button in (self._cancel_btn, self._ok_btn):
            button.setMinimumHeight(32)
            button.setMinimumWidth(96)
            refresh_cursor(button)
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)
        buttons.addWidget(self._ok_btn)
        self._layout.addLayout(buttons)

    def set_ok_text(self, text: str) -> None:
        self._ok_btn.setText(text)

    def show_error(self, message: str) -> None:
        self._error.setText(message)

    def add_info(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray;")
        self._layout.insertWidget(self._layout.count() - 1, label)
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
