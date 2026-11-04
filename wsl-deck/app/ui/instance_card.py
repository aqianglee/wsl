"""單一 instance 卡片。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
)

from app.ui.cursors import refresh_cursor
from app.ui.icons import (
    heart_pixmap,
    play_pixmap,
    prohibition_pixmap,
    stop_pixmap,
)
from app.wsl import Distro

ICON_BUTTON_SIZE = 26
ICON_SIZE = 14
ACTION_BUTTON_HEIGHT = 40
CARD_HEIGHT = 185

SYSTEM_REASON = "系統 instance，由上層工具（如 Docker Desktop）管理，不提供操作。"


class InstanceCard(QFrame):
    open_requested = Signal(object)
    start_requested = Signal(str)
    stop_requested = Signal(str)
    terminal_requested = Signal(str)
    linux_files_requested = Signal(str)
    install_dir_requested = Signal(str)

    def __init__(self, distro: Distro, is_system: bool, parent=None):
        super().__init__(parent)
        self._distro = distro
        self._system = is_system

        self.setObjectName("instanceCard")
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(CARD_HEIGHT)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            """
            QFrame#instanceCard {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 10px;
            }
            QFrame#instanceCard:hover {
                border: 1px solid #4a90e2;
            }
            QToolButton#cardIcon {
                border: 1px solid palette(mid);
                border-radius: 7px;
                background: palette(button);
            }
            QToolButton#cardIcon:hover {
                background: palette(midlight);
                border-color: #4a90e2;
            }
            QPushButton#cardAction {
                border: 1px solid palette(mid);
                border-radius: 7px;
                background: palette(button);
                padding: 4px 10px;
            }
            QPushButton#cardAction:hover {
                background: palette(midlight);
                border-color: #4a90e2;
            }
            QToolButton:disabled, QPushButton:disabled {
                color: #9aa0a6;
                background: palette(window);
                border-color: palette(dark);
            }
            """
        )
        self._build()
        self.update_distro(distro, is_system)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 12)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(6)

        self._star = QLabel(self)
        self._star.setPixmap(heart_pixmap())
        self._star.setFixedSize(18, 18)
        self._star.setToolTip("預設 instance")
        header.addWidget(self._star)

        self._system_icon = QLabel(self)
        self._system_icon.setPixmap(prohibition_pixmap())
        self._system_icon.setFixedSize(18, 18)
        self._system_icon.setToolTip(SYSTEM_REASON)
        header.addWidget(self._system_icon)
        header.addStretch(1)

        self._power_btn = QToolButton(self)
        self._power_btn.setObjectName("cardIcon")
        self._power_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._power_btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._power_btn.clicked.connect(self._on_power)
        header.addWidget(self._power_btn)

        self._terminal_btn = QToolButton(self)
        self._terminal_btn.setObjectName("cardIcon")
        self._terminal_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._terminal_btn.setText(">_")
        terminal_font = QFont("Consolas")
        terminal_font.setBold(True)
        terminal_font.setPointSize(8)
        self._terminal_btn.setFont(terminal_font)
        self._terminal_btn.setToolTip("開啟終端")
        self._terminal_btn.clicked.connect(
            lambda: self.terminal_requested.emit(self._distro.name)
        )
        header.addWidget(self._terminal_btn)

        layout.addLayout(header)
        layout.addSpacing(20)

        self._name = QLabel(self)
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        self._name.setFont(name_font)
        self._name.setAlignment(Qt.AlignCenter)
        self._name.setFixedHeight(26)
        layout.addWidget(self._name)

        layout.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch(1)

        self._linux_btn = QPushButton("Linux 檔案", self)
        self._linux_btn.setObjectName("cardAction")
        self._linux_btn.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self._linux_btn.setIconSize(QSize(16, 16))
        self._linux_btn.setFixedHeight(ACTION_BUTTON_HEIGHT)
        self._linux_btn.setMinimumWidth(120)
        self._linux_btn.clicked.connect(
            lambda: self.linux_files_requested.emit(self._distro.name)
        )
        footer.addWidget(self._linux_btn)

        self._install_btn = QPushButton("安裝目錄", self)
        self._install_btn.setObjectName("cardAction")
        self._install_btn.setIcon(self.style().standardIcon(QStyle.SP_DriveHDIcon))
        self._install_btn.setIconSize(QSize(16, 16))
        self._install_btn.setFixedHeight(ACTION_BUTTON_HEIGHT)
        self._install_btn.setMinimumWidth(120)
        self._install_btn.clicked.connect(
            lambda: self.install_dir_requested.emit(self._distro.base_path)
        )
        footer.addWidget(self._install_btn)

        footer.addStretch(1)
        layout.addLayout(footer)

        self._apply_shadow(self, blur=18, offset_y=3, alpha=55)
        for button in (
            self._power_btn,
            self._terminal_btn,
            self._linux_btn,
            self._install_btn,
        ):
            self._apply_shadow(button, blur=6, offset_y=2, alpha=40)

    @staticmethod
    def _apply_shadow(widget, blur: int, offset_y: int, alpha: int) -> None:
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, offset_y)
        effect.setColor(QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)

    def update_distro(self, distro: Distro, is_system: bool) -> None:
        self._distro = distro
        self._system = is_system

        self._name.setText(distro.name)
        name_font = self._name.font()
        name_font.setPointSize(18 if len(distro.name) <= 10 else 14)
        name_font.setBold(True)
        self._name.setFont(name_font)
        self._star.setVisible(distro.is_default)
        self._system_icon.setVisible(is_system)

        if distro.running:
            self._power_btn.setIcon(QIcon(stop_pixmap()))
            self._power_btn.setToolTip("執行中，點擊終止")
        else:
            self._power_btn.setIcon(QIcon(play_pixmap()))
            self._power_btn.setToolTip("已停止，點擊啟動")

        enabled = not is_system
        self._power_btn.setEnabled(enabled)
        self._terminal_btn.setEnabled(enabled)
        self._linux_btn.setEnabled(enabled)
        self._install_btn.setEnabled(enabled and bool(distro.base_path))
        for button in (
            self._power_btn,
            self._terminal_btn,
            self._linux_btn,
            self._install_btn,
        ):
            refresh_cursor(button)

        if is_system:
            for button in (
                self._power_btn,
                self._terminal_btn,
                self._linux_btn,
                self._install_btn,
            ):
                button.setToolTip(SYSTEM_REASON)
            self.setToolTip(SYSTEM_REASON)
        else:
            self._terminal_btn.setToolTip("開啟終端")
            self._linux_btn.setToolTip("開啟 Linux 檔案")
            self._install_btn.setToolTip(distro.base_path or "找不到安裝目錄")
            self.setToolTip(f"{distro.name}\n{distro.base_path}")

    def _on_power(self) -> None:
        if self._system:
            return
        if self._distro.running:
            self.stop_requested.emit(self._distro.name)
        else:
            self.start_requested.emit(self._distro.name)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self._distro)
        super().mousePressEvent(event)
