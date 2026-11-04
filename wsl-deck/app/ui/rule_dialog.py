"""新增／編輯網路規則對話框。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.network import validate_rule
from app.ui.cursors import refresh_cursor


class RuleDialog(QDialog):
    def __init__(
        self,
        distro: str,
        rules: list[dict],
        rule: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._distro = distro
        self._rules = rules
        self._old_windows_port = rule.get("windows_port") if rule else None
        self.rule: dict | None = None

        self.setWindowTitle("編輯網路規則" if rule else "新增網路規則")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        self._windows_port = QSpinBox(self)
        self._windows_port.setRange(1, 65535)
        self._windows_port.setValue(rule["windows_port"] if rule else 8080)
        form.addRow("Windows 端口", self._windows_port)

        self._distro_port = QSpinBox(self)
        self._distro_port.setRange(1, 65535)
        self._distro_port.setValue(rule["distro_port"] if rule else 80)
        form.addRow("distro 端口", self._distro_port)

        self._allow_lan = QCheckBox("允許區網其他裝置存取", self)
        self._allow_lan.setChecked(rule.get("allow_lan", True) if rule else True)
        form.addRow("", self._allow_lan)

        self._enabled = QCheckBox("啟用此規則", self)
        self._enabled.setChecked(rule.get("enabled", True) if rule else True)
        form.addRow("", self._enabled)

        layout.addLayout(form)

        info = QLabel(
            "允許 LAN 時會建立 private + localsubnet 的防火牆入站規則；"
            "套用時需要管理員授權。",
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        self._error = QLabel("", self)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消", self)
        self._ok_btn = QPushButton("儲存" if rule else "新增規則", self)
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
        windows_port = self._windows_port.value()
        distro_port = self._distro_port.value()
        candidate = {
            "label": f"{windows_port} → {distro_port}",
            "distro": self._distro,
            "windows_port": windows_port,
            "distro_port": distro_port,
            "allow_lan": self._allow_lan.isChecked(),
            "enabled": self._enabled.isChecked(),
        }
        try:
            validate_rule(
                candidate,
                self._rules,
                ignore_windows_port=self._old_windows_port,
            )
        except ValueError as exc:
            self._error.setText(str(exc))
            return
        self.rule = candidate
        super().accept()
