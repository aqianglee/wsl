"""詳情頁的網路規則面板。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.ui.cursors import refresh_cursor

STATUS_COLORS = {
    "已套用": "#27ae60",
    "待套用": "#e67e22",
    "待啟動": "#7f8c8d",
    "已停用": "#7f8c8d",
}

CARD_STYLE = """
QFrame#sectionCard {
    background: palette(base);
    border: 1px solid rgba(128, 128, 128, 30);
    border-radius: 10px;
}
"""


def _title_font() -> QFont:
    font = QFont()
    font.setPointSize(12)
    font.setBold(True)
    return font


class NetworkPanel(QFrame):
    add_requested = Signal()
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    apply_requested = Signal()
    scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setStyleSheet(CARD_STYLE)
        self._name = ""
        self._system = False
        self._running = False
        self._rules: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("網路規則", self)
        title.setFont(_title_font())
        layout.addWidget(title)

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(
            ["Windows 端口", "distro 端口", "允許 LAN", "啟用", "狀態"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(150)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        self._table.cellDoubleClicked.connect(lambda _row, _col: self._emit_edit())
        layout.addWidget(self._table)

        self._empty = QLabel("尚無規則，按「新增規則」開始。", self)
        self._empty.setStyleSheet("color: gray;")
        layout.addWidget(self._empty)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._add_btn = self._make_button("新增規則", self.add_requested.emit)
        self._edit_btn = self._make_button("編輯", self._emit_edit)
        self._delete_btn = self._make_button("刪除", self._emit_delete)
        self._apply_btn = self._make_button("立即套用", self.apply_requested.emit)
        self._scan_btn = self._make_button(
            "掃描監聽端口", self.scan_requested.emit
        )
        for button in (
            self._add_btn,
            self._edit_btn,
            self._delete_btn,
            self._apply_btn,
            self._scan_btn,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        note = QLabel(
            "允許 LAN 僅對私人網路（profile=private）的本地子網開放；"
            "Public 網路會被防火牆阻擋。",
            self,
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

        self._update_buttons()

    def _make_button(self, text: str, slot) -> QPushButton:
        button = QPushButton(text, self)
        button.setMinimumHeight(32)
        button.clicked.connect(lambda _checked=False: slot())
        refresh_cursor(button)
        return button

    def set_context(self, name: str, is_system: bool, running: bool) -> None:
        self._name = name
        self._system = is_system
        self._running = running
        self._update_buttons()

    def set_rules(self, rules: list[dict], statuses: dict[int, str]) -> None:
        selected = self.selected_windows_port()
        self._rules = list(rules)
        self._table.setRowCount(0)

        for rule in rules:
            row = self._table.rowCount()
            self._table.insertRow(row)
            port_item = QTableWidgetItem(str(rule["windows_port"]))
            port_item.setData(Qt.UserRole, rule["windows_port"])
            port_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, port_item)

            distro_item = QTableWidgetItem(str(rule["distro_port"]))
            distro_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, distro_item)

            lan_item = QTableWidgetItem("是" if rule.get("allow_lan", True) else "否")
            lan_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 2, lan_item)

            enabled_item = QTableWidgetItem("是" if rule.get("enabled", True) else "否")
            enabled_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, enabled_item)

            status = statuses.get(rule["windows_port"], "待套用")
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            color = STATUS_COLORS.get(status)
            if color:
                status_item.setForeground(QBrush(QColor(color)))
            status_item.setToolTip(self._status_tooltip(status))
            self._table.setItem(row, 4, status_item)

        self._table.setVisible(bool(rules))
        self._empty.setVisible(not rules)

        if selected is not None:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == selected:
                    self._table.selectRow(row)
                    break
        self._update_buttons()

    @staticmethod
    def _status_tooltip(status: str) -> str:
        return {
            "已套用": "portproxy 已指向目前的 distro IP。",
            "待套用": "規則尚未生效，或需清理舊的端口轉發。",
            "待啟動": "instance 未執行，啟動後會自動重套。",
            "已停用": "規則已停用，套用時會移除對應轉發。",
        }.get(status, "")

    def selected_windows_port(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        return int(value) if value is not None else None

    def _emit_edit(self) -> None:
        port = self.selected_windows_port()
        if port is not None:
            self.edit_requested.emit(port)

    def _emit_delete(self) -> None:
        port = self.selected_windows_port()
        if port is not None:
            self.delete_requested.emit(port)

    def _update_buttons(self) -> None:
        selected = self.selected_windows_port()
        editable = not self._system
        self._add_btn.setEnabled(editable)
        self._scan_btn.setEnabled(editable)
        self._edit_btn.setEnabled(editable and selected is not None)
        self._delete_btn.setEnabled(editable and selected is not None)
        self._apply_btn.setEnabled(editable and bool(self._rules))
        for button in (
            self._add_btn,
            self._edit_btn,
            self._delete_btn,
            self._apply_btn,
            self._scan_btn,
        ):
            refresh_cursor(button)
