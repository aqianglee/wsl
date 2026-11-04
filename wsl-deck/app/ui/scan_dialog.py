"""掃描監聽端口後的勾選對話框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.network import validate_rule
from app.ui.cursors import refresh_cursor


class ScanDialog(QDialog):
    def __init__(
        self,
        distro: str,
        ports: list[int],
        rules: list[dict],
        parent=None,
    ):
        super().__init__(parent)
        self._distro = distro
        self._existing_rules = rules
        self.rules: list[dict] = []

        self.setWindowTitle("掃描監聽端口")
        self.setMinimumSize(600, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        heading = QLabel(
            f"{distro} 監聽中的 TCP 端口；勾選後按「加入規則」。",
            self,
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["選取", "distro 端口", "Windows 端口", "備註"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setMinimumHeight(260)
        layout.addWidget(self._table)

        existing_ports = {
            rule["distro_port"] for rule in rules if rule["distro"] == distro
        }
        for port in ports:
            row = self._table.rowCount()
            self._table.insertRow(row)

            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
            )
            already = port in existing_ports
            check_item.setCheckState(Qt.Unchecked if already else Qt.Checked)
            self._table.setItem(row, 0, check_item)

            port_item = QTableWidgetItem(str(port))
            port_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, port_item)

            spin = QSpinBox(self._table)
            spin.setRange(1, 65535)
            spin.setValue(port)
            self._table.setCellWidget(row, 2, spin)

            note_item = QTableWidgetItem("已有規則（distro 端口已使用）" if already else "")
            if already:
                note_item.setForeground(QBrush(QColor("gray")))
            self._table.setItem(row, 3, note_item)

        self._error = QLabel("", self)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消", self)
        self._ok_btn = QPushButton("加入規則", self)
        for button in (cancel, self._ok_btn):
            button.setMinimumHeight(32)
            button.setMinimumWidth(96)
            refresh_cursor(button)
        cancel.clicked.connect(self.reject)
        self._ok_btn.clicked.connect(self._on_accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self._ok_btn)
        layout.addLayout(buttons)

    def _on_accept(self) -> None:
        collected: list[dict] = []
        for row in range(self._table.rowCount()):
            check_item = self._table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.Checked:
                continue
            distro_port = int(self._table.item(row, 1).text())
            spin = self._table.cellWidget(row, 2)
            windows_port = spin.value()
            candidate = {
                "label": f"{windows_port} → {distro_port}",
                "distro": self._distro,
                "windows_port": windows_port,
                "distro_port": distro_port,
                "allow_lan": True,
                "enabled": True,
            }
            try:
                validate_rule(candidate, self._existing_rules + collected)
            except ValueError as exc:
                self._error.setText(str(exc))
                return
            collected.append(candidate)

        if not collected:
            self._error.setText("請至少勾選一個端口")
            return
        self.rules = collected
        super().accept()
