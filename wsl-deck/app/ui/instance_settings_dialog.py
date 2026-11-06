"""Instance 設定對話框：常用設定與進階維護。"""

from __future__ import annotations

import ipaddress

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import SERVICE_NAME_RE

from app.distro_settings import (
    InstanceSettings,
    detect_instance_host_ip,
    user_exists,
)
from app.ui.cursors import refresh_cursor
from app.ui.dialog_base import DialogBase, FORM_CONTROL_HEIGHT
from app.ui.icons import settings_icon
from app.wsl import Distro

MAINTENANCE_REASON = "需先終止 instance 才能執行此操作。"


class InstanceSettingsDialog(DialogBase):
    maintenance_requested = Signal(str, object)

    def __init__(
        self,
        distro: Distro,
        running: bool,
        settings: InstanceSettings | None,
        sparse_state: bool | None,
        parent=None,
        network: dict | None = None,
    ):
        super().__init__(f"Instance 設定 — {distro.name}", parent, width=640)
        self.setWindowIcon(settings_icon())
        self.set_ok_text("儲存")
        self._distro = distro
        self._running = running
        self._initial = settings
        self._network_initial = self._normalize_network(network)
        self._sparse_state = sparse_state

        self._build_info()
        self._build_common(settings)
        self._build_network(network)
        self._build_maintenance()

        self._ok_btn.setEnabled(True)
        if running:
            self.add_info("常用設定的變更需終止 instance 後重新啟動才生效。")
        else:
            self._ok_btn.setToolTip("instance 停止時仍可儲存網路隔離設定")
            self.add_info("instance 已停止：常用設定唯讀；網路隔離設定可先儲存，啟動時生效。")
        self._ok_btn.clicked.connect(self._on_ok)
        refresh_cursor(self._ok_btn)

    def _build_info(self) -> None:
        info = QLabel(
            f"安裝路徑：{self._distro.base_path or '—'}\n"
            f"VHD 大小：{self._distro.size_gb:.2f} GB"
            f"　｜　WSL 版本：{self._distro.version}",
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #7f8c8d;")
        self._layout.insertWidget(0, info)

    def _build_common(self, settings: InstanceSettings | None) -> None:
        group = QGroupBox("常用設定", self)
        form = QFormLayout(group)
        form.setSpacing(10)

        self._user_edit = QLineEdit(group)
        self._user_edit.setMinimumWidth(220)
        self._user_edit.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._user_edit.setPlaceholderText("例如 root、ubuntu")
        form.addRow("預設使用者", self._user_edit)

        self._systemd_check = QCheckBox("啟用 systemd（僅 WSL 2）", group)
        self._append_path_check = QCheckBox(
            "將 Windows PATH 追加到 Linux PATH", group
        )
        self._automount_check = QCheckBox(
            "自動掛載 Windows 磁碟（/mnt/c 等）", group
        )
        form.addRow("", self._systemd_check)
        form.addRow("", self._append_path_check)
        form.addRow("", self._automount_check)

        self._proxy_check = QCheckBox("啟用 SOCKS5 代理", group)
        form.addRow("", self._proxy_check)

        self._proxy_host = QLineEdit(group)
        self._proxy_host.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._proxy_host.setPlaceholderText("例如 192.168.160.1")
        self._proxy_detect_btn = QPushButton("偵測主機 IP", group)
        self._proxy_detect_btn.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._proxy_detect_btn.clicked.connect(self._detect_proxy_host)
        refresh_cursor(self._proxy_detect_btn)
        host_row = QHBoxLayout()
        host_row.setContentsMargins(0, 0, 0, 0)
        host_row.setSpacing(8)
        host_row.addWidget(self._proxy_host, 1)
        host_row.addWidget(self._proxy_detect_btn)
        self._proxy_host_widget = QWidget(group)
        self._proxy_host_widget.setLayout(host_row)
        form.addRow("代理主機", self._proxy_host_widget)

        self._proxy_port = QSpinBox(group)
        self._proxy_port.setRange(1, 65535)
        self._proxy_port.setValue(7890)
        self._proxy_port.setFixedHeight(FORM_CONTROL_HEIGHT)
        form.addRow("代理埠", self._proxy_port)

        proxy_note = QLabel(
            "寫入 /etc/profile.d，新登入 shell 生效；apt 不支援 SOCKS5。", group
        )
        proxy_note.setWordWrap(True)
        proxy_note.setStyleSheet("color: gray;")
        form.addRow("", proxy_note)

        if settings is not None:
            self._user_edit.setText(settings.default_user)
            self._systemd_check.setChecked(settings.systemd)
            self._append_path_check.setChecked(settings.append_windows_path)
            self._automount_check.setChecked(settings.automount)
            self._proxy_check.setChecked(settings.proxy_enabled)
            self._proxy_host.setText(settings.proxy_host)
            if settings.proxy_port:
                self._proxy_port.setValue(settings.proxy_port)
        else:
            self._append_path_check.setChecked(True)
            self._automount_check.setChecked(True)
            self._user_edit.setPlaceholderText("啟動後可讀取")

        editable = self._running and settings is not None
        for widget in (
            self._user_edit,
            self._systemd_check,
            self._append_path_check,
            self._automount_check,
            self._proxy_check,
            self._proxy_host_widget,
            self._proxy_port,
        ):
            widget.setEnabled(editable)
        if editable:
            self._proxy_check.toggled.connect(self._on_proxy_toggled)
            self._on_proxy_toggled(self._proxy_check.isChecked())
        if self._distro.version < 2:
            self._systemd_check.setEnabled(False)
            self._systemd_check.setToolTip("WSL 1 不支援 systemd")

        self._layout.insertWidget(1, group)

    def _on_proxy_toggled(self, checked: bool) -> None:
        self._proxy_host_widget.setEnabled(checked)
        self._proxy_port.setEnabled(checked)

    @staticmethod
    def _normalize_network(network: dict | None) -> dict:
        raw = network if isinstance(network, dict) else {}
        scope = raw.get("scope")
        if scope not in ("temporary", "permanent"):
            scope = "temporary"
        services = raw.get("services")
        services = (
            [str(item).strip() for item in services if str(item).strip()]
            if isinstance(services, list)
            else []
        )
        return {
            "enabled": bool(raw.get("enabled", False)),
            "scope": scope,
            "ip": str(raw.get("ip") or "").strip(),
            "services": services,
        }

    def _build_network(self, network: dict | None) -> None:
        group = QGroupBox("網路隔離（C 方案）", self)
        form = QFormLayout(group)
        form.setSpacing(10)

        self._net_enabled = QCheckBox("啟用 C 方案（獨立 netns）", group)
        form.addRow("", self._net_enabled)

        self._net_scope = QComboBox(group)
        self._net_scope.addItem("臨時：僅 WSL Deck 啟動生效", "temporary")
        self._net_scope.addItem("永久：WSL Deck 與 wt 啟動都生效", "permanent")
        self._net_scope.setFixedHeight(FORM_CONTROL_HEIGHT)
        form.addRow("啟用範圍", self._net_scope)

        self._net_ip = QLineEdit(group)
        self._net_ip.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._net_ip.setPlaceholderText("例如 192.168.163.241")
        form.addRow("隔離 IP", self._net_ip)

        self._net_services = QLineEdit(group)
        self._net_services.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._net_services.setPlaceholderText("例如 mysql，多個以逗號分隔")
        form.addRow("要搬入的服務", self._net_services)

        note = QLabel(
            "服務需為 systemd unit。臨時模式不寫入永久設定；永久模式會寫入 systemd unit "
            "與 drop-in，任何方式啟動都生效。變更服務會重啟該服務。",
            group,
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        form.addRow("", note)

        initial = self._normalize_network(network)
        self._net_enabled.setChecked(initial["enabled"])
        index = self._net_scope.findData(initial["scope"])
        self._net_scope.setCurrentIndex(max(0, index))
        self._net_ip.setText(initial["ip"])
        self._net_services.setText(", ".join(initial["services"]))

        self._net_enabled.toggled.connect(self._on_network_toggled)
        self._on_network_toggled(initial["enabled"])
        self._layout.insertWidget(2, group)

    def _on_network_toggled(self, checked: bool) -> None:
        for widget in (self._net_scope, self._net_ip, self._net_services):
            widget.setEnabled(checked)

    def network_values(self) -> dict:
        services = [
            item.strip()
            for item in self._net_services.text().replace("，", ",").split(",")
            if item.strip()
        ]
        return {
            "enabled": self._net_enabled.isChecked(),
            "scope": str(self._net_scope.currentData()),
            "ip": self._net_ip.text().strip(),
            "services": services,
        }

    def network_changed(self) -> bool:
        return self.network_values() != self._network_initial

    def _detect_proxy_host(self) -> None:
        ip = detect_instance_host_ip(self._distro.name)
        if not ip:
            self.show_error("找不到 Windows 主機位址，請手動輸入")
            return
        self._proxy_host.setText(ip)

    def _build_maintenance(self) -> None:
        group = QGroupBox("進階維護", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._version_combo = QComboBox(group)
        self._version_combo.addItem("WSL 1", 1)
        self._version_combo.addItem("WSL 2", 2)
        index = self._version_combo.findData(self._distro.version)
        self._version_combo.setCurrentIndex(max(0, index))
        self._version_combo.setFixedWidth(96)

        self._version_btn = QPushButton("套用版本", group)
        self._version_btn.setFixedHeight(32)
        self._version_btn.clicked.connect(self._on_apply_version)
        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("WSL 版本", group))
        version_row.addWidget(self._version_combo)
        version_row.addStretch(1)
        version_row.addWidget(self._version_btn)
        layout.addLayout(version_row)

        self._sparse_label = QLabel(self._sparse_text(), group)
        self._sparse_btn = QPushButton(
            "停用 Sparse VHD" if self._sparse_state is True else "啟用 Sparse VHD",
            group,
        )
        self._sparse_btn.setFixedHeight(32)
        self._sparse_btn.clicked.connect(self._on_toggle_sparse)
        sparse_row = QHBoxLayout()
        sparse_row.addWidget(QLabel("Sparse VHD", group))
        sparse_row.addWidget(self._sparse_label, 1)
        sparse_row.addWidget(self._sparse_btn)
        layout.addLayout(sparse_row)

        self._compact_btn = QPushButton("壓縮 VHD（回收未使用空間）", group)
        self._compact_btn.setFixedHeight(32)
        self._compact_btn.clicked.connect(self._on_compact)
        compact_row = QHBoxLayout()
        compact_row.addWidget(QLabel("磁碟壓縮", group))
        compact_row.addStretch(1)
        compact_row.addWidget(self._compact_btn)
        layout.addLayout(compact_row)

        maintenance_enabled = not self._running
        for button in (self._version_btn, self._sparse_btn, self._compact_btn):
            button.setEnabled(maintenance_enabled)
            if not maintenance_enabled:
                button.setToolTip(MAINTENANCE_REASON)
            refresh_cursor(button)

        if self._distro.version < 2:
            for button in (self._sparse_btn, self._compact_btn):
                button.setEnabled(False)
                button.setToolTip("僅 WSL 2 支援此操作")

        self._layout.insertWidget(3, group)

    def _sparse_text(self) -> str:
        if self._sparse_state is True:
            return "目前：已啟用"
        if self._sparse_state is False:
            return "目前：未啟用"
        return "目前：未知"

    def values(self) -> InstanceSettings:
        return InstanceSettings(
            default_user=self._user_edit.text().strip(),
            systemd=self._systemd_check.isChecked(),
            append_windows_path=self._append_path_check.isChecked(),
            automount=self._automount_check.isChecked(),
            proxy_enabled=self._proxy_check.isChecked(),
            proxy_host=self._proxy_host.text().strip(),
            proxy_port=int(self._proxy_port.value()),
        )

    def has_changes(self) -> bool:
        return self._initial is not None and self.values() != self._initial

    def _on_ok(self) -> None:
        network = self.network_values()
        if network["enabled"]:
            if not network["ip"]:
                self.show_error("啟用 C 方案時，隔離 IP 不可空白")
                return
            try:
                address = ipaddress.ip_address(network["ip"])
            except ValueError:
                self.show_error(f"隔離 IP 格式不正確：{network['ip']}")
                return
            if address.is_loopback or address.is_multicast or address.is_unspecified:
                self.show_error("隔離 IP 不可使用此位址")
                return
            if not network["services"]:
                self.show_error("請填寫要搬入 netns 的 systemd 服務")
                return
            for service in network["services"]:
                if not SERVICE_NAME_RE.match(service):
                    self.show_error(f"服務名稱不合法：{service}")
                    return
        if not self._running:
            self.accept()
            return
        user = self._user_edit.text().strip()
        if not user:
            self.show_error("使用者名稱不可空白")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            exists = user_exists(self._distro.name, user)
        finally:
            QApplication.restoreOverrideCursor()
        if not exists:
            self.show_error(f"instance 內找不到使用者 {user}")
            return
        if self._proxy_check.isChecked() and not self._proxy_host.text().strip():
            self.show_error("啟用代理時，代理主機不可空白")
            return
        self.accept()

    def _confirm(self, title: str, text: str) -> bool:
        return QMessageBox.warning(
            self,
            title,
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes

    def _on_apply_version(self) -> None:
        version = int(self._version_combo.currentData())
        if version == self._distro.version:
            QMessageBox.information(
                self, "WSL 版本", f"目前已是 WSL {version}。"
            )
            return
        if not self._confirm(
            "切換 WSL 版本",
            f"要將 {self._distro.name} 切換為 WSL {version} 嗎？\n\n"
            "轉換可能需要數分鐘；失敗可能導致 instance 無法啟動，建議先備份。",
        ):
            return
        self.maintenance_requested.emit("version", version)
        self.accept()

    def _on_toggle_sparse(self) -> None:
        enable = self._sparse_state is not True
        action = "啟用" if enable else "停用"
        if not self._confirm(
            f"{action} Sparse VHD",
            f"要{action} {self._distro.name} 的 Sparse VHD 嗎？\n\n"
            "此操作可能需要數分鐘。",
        ):
            return
        self.maintenance_requested.emit("sparse", enable)
        self.accept()

    def _on_compact(self) -> None:
        if not self._confirm(
            "壓縮 VHD",
            f"要壓縮 {self._distro.name} 的 VHD 嗎？\n\n"
            "此操作會回收未使用空間，可能需要數分鐘。",
        ):
            return
        self.maintenance_requested.emit("compact", None)
        self.accept()
