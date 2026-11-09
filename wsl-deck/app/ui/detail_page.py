"""Instance 詳情頁。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
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
from app.ui.icons import (
    backup_icon,
    copy_icon,
    delete_icon,
    forbidden_icon,
    heart_icon,
    heart_outline_icon,
    install_dir_icon,
    linux_archive_icon,
    power_start_icon,
    power_stop_icon,
    restore_icon,
    settings_themed_icon,
    snapshot_icon,
    terminal_icon,
)
from app.ui.instance_card import SYSTEM_REASON
from app.ui.network_panel import NetworkPanel
from app.wsl import Distro

CARD_STYLE = """
QFrame#sectionCard {
    background: palette(base);
    border: 1px solid rgba(128, 128, 128, 30);
    border-radius: 10px;
}
QFrame#sectionDivider {
    background: rgba(128, 128, 128, 45);
}
QFrame#opsDivider {
    background: rgba(128, 128, 128, 32);
}
"""

ICON_SIZE = 16
BUTTON_HEIGHT = 32
OPS_DIVIDER_HEIGHT = 22


def _title_font() -> QFont:
    font = QFont()
    font.setPointSize(12)
    font.setBold(True)
    return font


def _spaced_icon(icon: QIcon, pad: int = 4) -> QIcon:
    """在圖標右側補透明像素，加大與文字之間的視覺間距。"""
    source = icon.pixmap(QSize(ICON_SIZE, ICON_SIZE))
    canvas = QPixmap(ICON_SIZE + pad, ICON_SIZE)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(0, 0, source)
    painter.end()
    return QIcon(canvas)


def _section_divider(parent: QWidget) -> QFrame:
    divider = QFrame(parent)
    divider.setObjectName("sectionDivider")
    divider.setFixedHeight(1)
    return divider


def _ops_divider(parent: QWidget) -> QFrame:
    divider = QFrame(parent)
    divider.setObjectName("opsDivider")
    divider.setFixedSize(1, OPS_DIVIDER_HEIGHT)
    return divider


class DetailPage(QWidget):
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
    settings_requested = Signal(str)
    network_add_requested = Signal()
    network_edit_requested = Signal(int)
    network_delete_requested = Signal(int)
    network_apply_requested = Signal()
    network_scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._distro: Distro | None = None
        self._system = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 16)
        layout.setSpacing(12)

        summary = QFrame(self)
        summary.setObjectName("sectionCard")
        summary.setStyleSheet(CARD_STYLE)
        card = QVBoxLayout(summary)
        card.setContentsMargins(16, 16, 16, 16)
        card.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._name = QLabel(summary)
        self._name.setFont(_title_font())
        title_row.addWidget(self._name, 0, Qt.AlignVCenter)
        self._badge = QLabel(summary)
        self._badge.setFixedSize(18, 18)
        title_row.addWidget(self._badge, 0, Qt.AlignVCenter)
        title_row.addStretch(1)
        card.addLayout(title_row)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
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

        card.addLayout(grid)
        card.addWidget(_section_divider(summary))

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._power_btn = self._make_action("啟動", power_start_icon(), summary)
        self._terminal_btn = self._make_action("終端", terminal_icon(), summary)
        self._linux_btn = self._make_action("Linux 檔案", linux_archive_icon(), summary)
        self._install_btn = self._make_action("安裝目錄", install_dir_icon(), summary)
        self._default_btn = self._make_action("設為預設", heart_outline_icon(), summary)
        self._backup_btn = self._make_action("備份", backup_icon(), summary)
        self._restore_btn = self._make_action("還原", restore_icon(), summary)
        self._snapshot_btn = self._make_action("快照", snapshot_icon(), summary)
        self._clone_btn = self._make_action("複製", copy_icon(), summary)
        self._settings_btn = self._make_action("設定", settings_themed_icon(), summary)
        self._delete_btn = self._make_action("刪除", delete_icon(), summary)

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
            self._settings_btn,
            self._delete_btn,
        )
        for index, group in enumerate(
            (
                (self._power_btn, self._terminal_btn),
                (self._linux_btn, self._install_btn),
                (self._default_btn,),
                (self._backup_btn, self._restore_btn, self._snapshot_btn, self._clone_btn),
            )
        ):
            for button in group:
                actions.addWidget(button)
            if index < 3:
                actions.addWidget(_ops_divider(summary), 0, Qt.AlignVCenter)
        actions.addStretch(1)
        actions.addWidget(self._settings_btn)
        actions.addWidget(self._delete_btn)
        card.addLayout(actions)

        layout.addWidget(summary)

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
        self._settings_btn.clicked.connect(
            lambda: self._emit_name(self.settings_requested)
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

    def _make_action(self, text: str, icon, parent: QWidget) -> QPushButton:
        button = QPushButton(text, parent)
        button.setIcon(_spaced_icon(icon))
        button.setIconSize(QSize(ICON_SIZE + 4, ICON_SIZE))
        button.setFixedHeight(BUTTON_HEIGHT)
        return button

    def set_distro(self, distro: Distro, is_system: bool) -> None:
        previous = self._distro
        self._distro = distro
        self._system = is_system

        self._name.setText(distro.name)
        if is_system:
            self._badge.setPixmap(forbidden_icon().pixmap(QSize(18, 18)))
            self._badge.setToolTip(SYSTEM_REASON)
        elif distro.is_default:
            self._badge.setPixmap(heart_icon().pixmap(QSize(18, 18)))
            self._badge.setToolTip("預設 instance")
        else:
            self._badge.setPixmap(heart_outline_icon().pixmap(QSize(18, 18)))
            self._badge.setToolTip("普通 instance")

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
        self._power_btn.setIcon(
            _spaced_icon(power_stop_icon() if distro.running else power_start_icon())
        )
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
        for button in (
            self._backup_btn,
            self._restore_btn,
            self._snapshot_btn,
            self._clone_btn,
            self._settings_btn,
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
