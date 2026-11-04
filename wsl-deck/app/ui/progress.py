"""不可取消的模態進度框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont, QKeyEvent
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout


class OperationDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        heading = QLabel(title, self)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        self.stage_label = QLabel("準備中…", self)
        self.stage_label.setWordWrap(True)
        layout.addWidget(self.stage_label)

        bar = QProgressBar(self)
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        layout.addWidget(bar)

        note = QLabel("操作進行中，請勿關閉此視窗。", self)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

    def set_stage(self, text: str) -> None:
        self.stage_label.setText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
