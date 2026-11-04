"""Instance 詳情頁。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.cursors import refresh_cursor
from app.ui.icons import settings_icon
from app.ui.network_panel import NetworkPanel
from app.wsl import Distro


class DetailPage(QWidget):
    back_requested = Signal()
    start_requested = Signal(str)
    stop_requested = Signal(str)
    terminal_requested = Signal(str)
    linux_files_requested = Signal(str)
    install_dir_requested = Signal(str)
    set_default_requested = Signal(str)
    backup_requested = Signal(str)
    restore_requested = Signal(str)
    snapshot_requested = Signal(str)
    clone_requested = Signal(str)
    delete_requested = Signal(str)
    network_add_requested = Signal()
    network_edit_requested = Signal(int)
    network_delete_requested = Signal(int)
    network_apply_requested = Signal()
    network_scan_requested = Signal()
    settings_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._distro: Distro | None = None
        self._system = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("← 返回", self)
        back.setFixedHeight(32)
        back.setMinimumWidth(88)
        back.clicked.connect(self.back_requested)
        refresh_cursor(back)
        top.addWidget(back)

        self._title = QLabel(self)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self._title.setFont(title_font)
        top.addWidget(self._title)

        self._system_badge = QLabel("系統 instance", self)
        self._system_badge.setStyleSheet(
            "color: #7f8c8d; border: 1px solid #bdc3c7; border-radius: 4px; padding: 2px 6px;"
        )
        top.addWidget(self._system_badge)
        top.addStretch(1)

        self._settings_btn = QPushButton("設定", self)
        self._settings_btn.setIcon(settings_icon())
        self._settings_btn.setIconSize(QSize(16, 16))
        self._settings_btn.setFixedHeight(32)
        self._settings_btn.setMinimumWidth(96)
        self._settings_btn.setToolTip("Instance 設定")
        self._settings_btn.clicked.connect(self._on_settings)
        refresh_cursor(self._settings_btn)
        top.addWidget(self._settings_btn)
        layout.addLayout(top)

        summary = QFrame(self)
        summary.setObjectName("summary")
        summary.setStyleSheet(
            "QFrame#summary { background: palette(base); border: 1px solid palette(mid); border-radius: 8px; }"
        )
        grid = QGridLayout(summary)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        self._values: dict[str, QLabel] = {}
        for column, stretch in ((0, 3), (1, 7), (2, 3), (3, 7)):
            grid.setColumnStretch(column, stretch)

        def add_field(row: int, column: int, key: str, span: int = 1) -> None:
            key_label = QLabel(key, summary)
            key_label.setStyleSheet("color: #7f8c8d;")
            value = QLabel("—", summary)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if key == "安裝路徑":
                value.setWordWrap(True)
            self._values[key] = value
            grid.addWidget(key_label, row, column, alignment=Qt.AlignTop)
            grid.addWidget(
                value,
                row,
                column + 1,
                1,
                span,
                alignment=Qt.AlignTop,
            )

        add_field(0, 0, "狀態")
        add_field(0, 2, "WSL 版本")
        add_field(1, 0, "磁盤大小")
        add_field(1, 2, "目前 IP")
        add_field(2, 0, "安裝路徑", span=3)

        layout.addWidget(summary)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._power_btn = QPushButton("啟動", self)
        self._terminal_btn = QPushButton("終端", self)
        self._linux_btn = QPushButton("Linux 檔案", self)
        self._install_btn = QPushButton("安裝目錄", self)
        self._default_btn = QPushButton("設為預設", self)
        self._backup_btn = QPushButton("備份", self)
        self._restore_btn = QPushButton("還原", self)
        self._snapshot_btn = QPushButton("快照", self)
        self._clone_btn = QPushButton("複製", self)
        self._delete_btn = QPushButton("刪除", self)

        self._action_buttons = (
            self._power_btn,
            self._terminal_btn,
            self._linux_btn,
            self._install_btn,
            self._default_btn,
            self._backup_btn,
            self._restore_btn,
            self._snapshot_btn,
            self._clone_btn,
            self._delete_btn,
        )
        for button in self._action_buttons:
            button.setFixedHeight(32)
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._power_btn.clicked.connect(self._on_power)
        self._terminal_btn.clicked.connect(
            lambda: self._emit_name(self.terminal_requested)
        )
        self._linux_btn.clicked.connect(
            lambda: self._emit_name(self.linux_files_requested)
        )
        self._install_btn.clicked.connect(self._on_install_dir)
        self._default_btn.clicked.connect(
            lambda: self._emit_name(self.set_default_requested)
        )
        self._backup_btn.clicked.connect(
            lambda: self._emit_name(self.backup_requested)
        )
        self._restore_btn.clicked.connect(
            lambda: self._emit_name(self.restore_requested)
        )
        self._snapshot_btn.clicked.connect(
            lambda: self._emit_name(self.snapshot_requested)
        )
        self._clone_btn.clicked.connect(
            lambda: self._emit_name(self.clone_requested)
        )
        self._delete_btn.clicked.connect(
            lambda: self._emit_name(self.delete_requested)
        )

        self.network_panel = NetworkPanel(self)
        self.network_panel.add_requested.connect(self.network_add_requested)
        self.network_panel.edit_requested.connect(self.network_edit_requested)
        self.network_panel.delete_requested.connect(self.network_delete_requested)
        self.network_panel.apply_requested.connect(self.network_apply_requested)
        self.network_panel.scan_requested.connect(self.network_scan_requested)
        layout.addWidget(self.network_panel)

        layout.addStretch(1)

    def set_distro(self, distro: Distro, is_system: bool) -> None:
        previous = self._distro
        self._distro = distro
        self._system = is_system

        self._title.setText(distro.name)
        self._system_badge.setVisible(is_system)
        self._values["狀態"].setText("執行中" if distro.running else "已停止")
        self._values["WSL 版本"].setText(str(distro.version))
        self._values["磁盤大小"].setText(f"{distro.size_gb:.2f} GB")
        self._values["安裝路徑"].setText(distro.base_path or "—")
        if (
            previous is None
            or previous.name != distro.name
            or not distro.running
            or not previous.running
        ):
            self._values["目前 IP"].setText("讀取中…" if distro.running else "未執行")

        self._power_btn.setText("終止" if distro.running else "啟動")
        self._default_btn.setEnabled(not is_system and not distro.is_default)
        self._install_btn.setEnabled(not is_system and bool(distro.base_path))

        if previous is None or previous.name != distro.name:
            self.network_panel.set_rules([], {})
        self.network_panel.set_context(distro.name, is_system, distro.running)

        enabled = not is_system
        for button in (self._power_btn, self._terminal_btn, self._linux_btn):
            button.setEnabled(enabled)
        if is_system:
            self._default_btn.setEnabled(False)
        self._settings_btn.setEnabled(not is_system)
        self._settings_btn.setToolTip(
            "系統 instance 由上層工具（如 Docker Desktop）管理，不提供設定"
            if is_system
            else "Instance 設定"
        )
        refresh_cursor(self._settings_btn)
        for button in (
            self._backup_btn,
            self._restore_btn,
            self._snapshot_btn,
            self._clone_btn,
            self._delete_btn,
        ):
            button.setEnabled(enabled)
        for button in self._action_buttons:
            refresh_cursor(button)

    def set_ip(self, ip: str) -> None:
        self._values["目前 IP"].setText(ip or "未取得")

    def set_network(self, rules: list[dict], statuses: dict[int, str]) -> None:
        self.network_panel.set_rules(rules, statuses)

    def _emit_name(self, signal: Signal) -> None:
        if self._distro is not None and not self._system:
            signal.emit(self._distro.name)

    def _on_power(self) -> None:
        if self._distro is None or self._system:
            return
        if self._distro.running:
            self.stop_requested.emit(self._distro.name)
        else:
            self.start_requested.emit(self._distro.name)

    def _on_install_dir(self) -> None:
        if self._distro is not None and not self._system:
            self.install_dir_requested.emit(self._distro.base_path)

    def _on_settings(self) -> None:
        if self._distro is not None and not self._system:
            self.settings_requested.emit(self._distro.name)
