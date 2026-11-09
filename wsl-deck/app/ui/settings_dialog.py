"""設定對話框：只收集值，寫入與套用由 MainWindow 負責。"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.autostart import is_supported
from app.config import Config
from app.proxy import ProxyConfig, detect_wsl_host_ip, test_connection
from app.ui.cursors import refresh_cursor
from app.ui.dialog_base import (
    DialogBase,
    FORM_CONTROL_HEIGHT,
    make_card,
)
from app.ui.icons import settings_icon
from app.ui.workers import TaskWorker
from app.workspace import SUBDIR_BACKUPS, SUBDIR_INSTANCES, SUBDIR_SNAPSHOTS

THEME_LABELS = (
    ("跟隨系統", "system"),
    ("深色", "dark"),
    ("淺色", "light"),
)


class SettingsDialog(DialogBase):
    def __init__(self, config: Config, parent=None):
        super().__init__("設定", parent, width=640)
        self.setWindowIcon(settings_icon())
        self.set_ok_text("儲存")
        self._workers: set[TaskWorker] = set()
        self._testing_proxy = False
        self._layout.removeItem(self._form)

        dirs_card, dirs_box = make_card(self, "目錄")
        dirs_form = QFormLayout()
        dirs_form.setSpacing(10)
        dirs_box.addLayout(dirs_form)

        self._workspace_edit = QLineEdit(str(config.get("workspace_root", "")))
        dirs_form.addRow(
            "工作目錄",
            self._row_with_button(
                self._workspace_edit, "瀏覽…",
                lambda: self._browse(self._workspace_edit),
            ),
        )
        self._skeleton_btn = QPushButton("套用工作目錄骨架", self)
        self._skeleton_btn.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._skeleton_btn.clicked.connect(self._apply_skeleton)
        refresh_cursor(self._skeleton_btn)
        dirs_form.addRow("", self._skeleton_btn)

        self._distro_edit = QLineEdit(str(config.get("distro_root", "")))
        dirs_form.addRow(
            "instance 目錄",
            self._row_with_button(
                self._distro_edit, "瀏覽…",
                lambda: self._browse(self._distro_edit),
            ),
        )
        self._backup_edit = QLineEdit(str(config.get("backup_root", "")))
        dirs_form.addRow(
            "備份目錄",
            self._row_with_button(
                self._backup_edit, "瀏覽…",
                lambda: self._browse(self._backup_edit),
            ),
        )
        self._snapshot_edit = QLineEdit(str(config.get("snapshot_root", "")))
        dirs_form.addRow(
            "快照目錄",
            self._row_with_button(
                self._snapshot_edit, "瀏覽…",
                lambda: self._browse(self._snapshot_edit),
            ),
        )

        keep = config.get("snapshot_keep", {}) or {}
        self._keep_spins: dict[str, QSpinBox] = {}
        keep_row = QHBoxLayout()
        keep_row.setContentsMargins(0, 0, 0, 0)
        keep_row.setSpacing(6)
        for key, label in (
            ("last", "最近"),
            ("daily", "每日"),
            ("weekly", "每週"),
            ("monthly", "每月"),
        ):
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(int(keep.get(key, 0) or 0))
            spin.setSuffix(" 份")
            spin.setFixedHeight(FORM_CONTROL_HEIGHT)
            self._keep_spins[key] = spin
            keep_row.addWidget(QLabel(label))
            keep_row.addWidget(spin)
        keep_row.addStretch(1)
        keep_widget = QWidget(self)
        keep_widget.setLayout(keep_row)
        dirs_form.addRow("保留策略", keep_widget)

        dirs_box.addWidget(self._info_label(
            dirs_card,
            "工作目錄下會自動建立 instances／backups／snapshots 三個子目錄；"
            "既有 instance 不會被搬移。"
        ))
        workspace = self._workspace_edit.text().strip()
        if workspace and self._distro_edit.text().strip() != str(
            Path(workspace) / SUBDIR_INSTANCES
        ):
            dirs_box.addWidget(self._info_label(
                dirs_card,
                "目前 instance 目錄不在 instances\\ 下；若它等於工作目錄，"
                "新增／複製會預設改用 instances\\，其餘自訂路徑則沿用。"
                "既有 instance 不會被搬移。"
            ))
        self._layout.addWidget(dirs_card)

        general_card, general_box = make_card(self, "一般")
        general_form = QFormLayout()
        general_form.setSpacing(10)
        general_box.addLayout(general_form)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(3, 600)
        self._poll_spin.setSuffix(" 秒")
        self._poll_spin.setValue(int(config.get("poll_interval", 10)))
        self._poll_spin.setFixedHeight(FORM_CONTROL_HEIGHT)
        general_form.addRow("狀態輪詢間隔", self._poll_spin)

        self._theme_combo = QComboBox()
        for label, value in THEME_LABELS:
            self._theme_combo.addItem(label, value)
        index = self._theme_combo.findData(config.get("theme", "system"))
        self._theme_combo.setCurrentIndex(max(0, index))
        self._theme_combo.setFixedHeight(FORM_CONTROL_HEIGHT)
        general_form.addRow("主題", self._theme_combo)

        self._tray_check = QCheckBox("關閉視窗時縮到托盤")
        self._tray_check.setChecked(bool(config.get("close_to_tray", True)))
        general_form.addRow("托盤", self._tray_check)

        self._autostart_check = QCheckBox("開機時自動啟動（啟動後進托盤）")
        self._autostart_check.setChecked(bool(config.get("autostart", False)))
        self._autostart_check.setEnabled(is_supported())
        general_form.addRow("開機自啟", self._autostart_check)
        if not is_supported():
            general_box.addWidget(self._info_label(
                general_card,
                "開機自啟只支援打包後的 exe；開發模式（.venv）下無法寫入登錄檔。",
            ))

        self._advanced_check = QCheckBox("在日誌顯示實際執行的命令")
        self._advanced_check.setChecked(bool(config.get("advanced_mode", False)))
        general_form.addRow("進階模式", self._advanced_check)

        self._system_edit = QLineEdit(
            ", ".join(config.get("system_instances", []))
        )
        self._system_edit.setFixedHeight(FORM_CONTROL_HEIGHT)
        general_form.addRow("系統 instance 清單", self._system_edit)
        general_box.addWidget(self._info_label(
            general_card,
            "以逗號分隔，採前綴比對；例如 docker-desktop 會涵蓋 docker-desktop-data。",
        ))
        self._layout.addWidget(general_card)

        proxy_card, proxy_box = make_card(self, "SOCKS5 代理")
        proxy_form = QFormLayout()
        proxy_form.setSpacing(10)
        proxy_box.addLayout(proxy_form)

        proxy = config.get("proxy", {}) or {}
        self._proxy_check = QCheckBox("啟用 SOCKS5 代理")
        self._proxy_check.setChecked(bool(proxy.get("enabled", False)))
        proxy_form.addRow("SOCKS5 代理", self._proxy_check)

        self._proxy_host = QLineEdit(str(proxy.get("host", "127.0.0.1")))
        self._proxy_host_row = self._row_with_button(
            self._proxy_host, "偵測 WSL 主機 IP", self._detect_host
        )
        proxy_form.addRow("代理主機", self._proxy_host_row)

        self._proxy_port = QSpinBox()
        self._proxy_port.setRange(1, 65535)
        self._proxy_port.setValue(int(proxy.get("port", 7890)))
        self._proxy_port.setFixedHeight(FORM_CONTROL_HEIGHT)
        proxy_form.addRow("代理埠", self._proxy_port)

        self._proxy_test_btn = QPushButton("測試連線", self)
        self._proxy_test_btn.setFixedHeight(FORM_CONTROL_HEIGHT)
        self._proxy_test_btn.clicked.connect(self._test_proxy)
        self._proxy_status = QLabel("", self)
        self._proxy_status.setStyleSheet("color: gray;")
        test_row = QHBoxLayout()
        test_row.setContentsMargins(0, 0, 0, 0)
        test_row.setSpacing(8)
        test_row.addWidget(self._proxy_test_btn)
        test_row.addWidget(self._proxy_status, 1)
        test_widget = QWidget(self)
        test_widget.setLayout(test_row)
        proxy_form.addRow("連線測試", test_widget)

        self._proxy_check.toggled.connect(self._on_proxy_toggled)
        self._on_proxy_toggled(self._proxy_check.isChecked())
        refresh_cursor(self._proxy_test_btn)
        proxy_box.addWidget(self._info_label(
            proxy_card,
            "SOCKS5 僅對 curl／git 等遵循環境變數的工具生效；NAT 模式下 WSL 內需"
            "使用 Windows 主機 IP，且代理需允許局域網。"
        ))
        self._layout.addWidget(proxy_card)

        self._ok_btn.clicked.connect(self._on_ok)

    @staticmethod
    def _info_label(parent: QWidget, text: str) -> QLabel:
        label = QLabel(text, parent)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray;")
        return label

    def _browse(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "選擇資料夾", edit.text())
        if path:
            edit.setText(path)

    def _apply_skeleton(self) -> None:
        workspace = self._workspace_edit.text().strip()
        if not workspace:
            self.show_error("工作目錄不可空白")
            return
        root = Path(workspace)
        self._distro_edit.setText(str(root / SUBDIR_INSTANCES))
        self._backup_edit.setText(str(root / SUBDIR_BACKUPS))
        self._snapshot_edit.setText(str(root / SUBDIR_SNAPSHOTS))
        self.show_error("")

    def _on_proxy_toggled(self, checked: bool) -> None:
        self._proxy_host_row.setEnabled(checked)
        self._proxy_port.setEnabled(checked)
        self._proxy_test_btn.setEnabled(checked and not self._testing_proxy)

    def _detect_host(self) -> None:
        ip = detect_wsl_host_ip()
        if not ip:
            self.show_error("找不到 WSL 虛擬網卡位址")
            return
        self._proxy_host.setText(ip)

    def _test_proxy(self) -> None:
        if self._testing_proxy:
            return
        config = ProxyConfig(
            True,
            self._proxy_host.text().strip(),
            int(self._proxy_port.value()),
        )
        self._testing_proxy = True
        self._proxy_test_btn.setEnabled(False)
        self._proxy_status.setText("測試中…")
        self._proxy_status.setStyleSheet("color: gray;")
        worker = TaskWorker(test_connection, config)
        self._workers.add(worker)
        worker.signals.finished.connect(self._on_proxy_test_done)
        worker.signals.failed.connect(self._on_proxy_test_error)
        QThreadPool.globalInstance().start(worker)

    def _on_proxy_test_done(self, result) -> None:
        self._testing_proxy = False
        self._proxy_test_btn.setEnabled(self._proxy_check.isChecked())
        ok, message = result
        self._proxy_status.setText(message)
        self._proxy_status.setStyleSheet(
            "color: #2e7d32;" if ok else "color: #c0392b;"
        )

    def _on_proxy_test_error(self, message: str) -> None:
        self._testing_proxy = False
        self._proxy_test_btn.setEnabled(self._proxy_check.isChecked())
        self._proxy_status.setText(f"測試失敗：{message}")
        self._proxy_status.setStyleSheet("color: #c0392b;")

    def values(self) -> dict:
        instances: list[str] = []
        for item in re.split(r"[,，]", self._system_edit.text()):
            name = item.strip()
            if name and name not in instances:
                instances.append(name)
        return {
            "workspace_root": self._workspace_edit.text().strip(),
            "distro_root": self._distro_edit.text().strip(),
            "backup_root": self._backup_edit.text().strip(),
            "snapshot_root": self._snapshot_edit.text().strip(),
            "snapshot_keep": {
                key: int(spin.value()) for key, spin in self._keep_spins.items()
            },
            "poll_interval": int(self._poll_spin.value()),
            "theme": str(self._theme_combo.currentData()),
            "close_to_tray": self._tray_check.isChecked(),
            "autostart": self._autostart_check.isChecked(),
            "advanced_mode": self._advanced_check.isChecked(),
            "system_instances": instances,
            "proxy": {
                "enabled": self._proxy_check.isChecked(),
                "host": self._proxy_host.text().strip(),
                "port": int(self._proxy_port.value()),
            },
        }

    def _on_ok(self) -> None:
        values = self.values()
        for key, label in (
            ("workspace_root", "工作目錄"),
            ("distro_root", "instance 目錄"),
            ("backup_root", "備份目錄"),
            ("snapshot_root", "快照目錄"),
        ):
            if not values[key]:
                self.show_error(f"{label}不可空白")
                return
        if not values["system_instances"]:
            self.show_error("系統 instance 清單不可空白；至少保留 docker-desktop")
            return
        if values["proxy"]["enabled"] and not values["proxy"]["host"]:
            self.show_error("啟用代理時，代理主機不可空白")
            return
        self.accept()
