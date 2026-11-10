"""主視窗：Instance 卡片牆、詳情頁、日誌抽屜與全域動作。"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from functools import partial

from PySide6.QtCore import QEvent, QSize, QThreadPool, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.autostart import is_supported, set_enabled as set_autostart
from app.config import Config, ConfigError
from app.distro_ops import (
    backup_instance,
    clone_instance,
    create_instance,
    delete_instance,
    restore_instance,
)
from app.distro_settings import (
    apply_settings,
    compact_vhd,
    is_sparse,
    read_settings,
    set_sparse,
    set_version,
)
from app.logbus import log_bus
from app.netns import (
    cleanup_all as cleanup_netns,
    cleanup_temporary,
    effective_ip,
    ensure_after_start,
    netns_name,
)
from app.network import apply_rules, rule_status, scan_tcp_ports, show_portproxy
from app.proxy import apply_runtime, parse_config
from app.shell import open_path, open_terminal, terminal_user
from app.ui.app_icon import app_icon
from app.ui.backup_dialogs import BackupDialog, CloneDialog, DeleteDialog, RestoreDialog
from app.ui.card_wall import CardWall
from app.ui.cursors import refresh_cursor
from app.ui.detail_page import DetailPage
from app.ui.icons import (
    add_icon,
    back_icon,
    settings_themed_icon,
)
from app.ui.instance_settings_dialog import InstanceSettingsDialog
from app.ui.instance_table import InstanceTable
from app.ui.progress import OperationDialog
from app.ui.rule_dialog import RuleDialog
from app.ui.scan_dialog import ScanDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.snapshot_dialog import SnapshotDialog
from app.ui.theme import apply_theme, PRIMARY_COLOR
from app.ui.tray import TrayController
from app.ui.view_toggle import ViewToggle
from app.ui.wizard import NewInstanceWizard
from app.ui.workers import TaskWorker
from app.wsl import (
    Distro,
    is_system_distro,
    list_distros,
    set_default_distro,
    shutdown_all,
    start_distro,
    terminate_distro,
)
from app.workspace import ensure_workspace

logger = logging.getLogger(__name__)

TOP_BAR_HEIGHT = 56
BOTTOM_BAR_HEIGHT = 48
CONTENT_MARGIN = 24
SIDE_SLOT_WIDTH = 120
LOG_PANEL_HEIGHT = 150

TOP_BAR_STYLE = """
QWidget#topBar {
    background: palette(base);
    border: none;
    border-bottom: 1px solid rgba(128, 128, 128, 70);
}
QLabel#appTitle {
    color: palette(windowtext);
}
QFrame#topBarDivider {
    background: rgba(128, 128, 128, 50);
}
QPushButton#secondaryAction {
    background: transparent;
    color: palette(windowtext);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 0 14px;
}
QPushButton#secondaryAction:hover {
    background: palette(midlight);
}
QPushButton#secondaryAction:pressed {
    background: palette(mid);
}
QPushButton#secondaryAction:disabled {
    color: #9aa0a6;
}
"""

PRIMARY_ACTION_STYLE = f"""
QPushButton#primaryAction {{
    background: {PRIMARY_COLOR};
    color: #FFFFFF;
    border: 1px solid {PRIMARY_COLOR};
    border-radius: 6px;
    padding: 0 14px;
}}
QPushButton#primaryAction:hover {{
    background: #1F66CC;
    border-color: #1F66CC;
}}
QPushButton#primaryAction:pressed {{
    background: #1A5BB3;
    border-color: #1A5BB3;
}}
QPushButton#primaryAction:disabled {{
    background: #A9C7F5;
    border-color: #A9C7F5;
    color: #FFFFFF;
}}
"""

BOTTOM_BAR_STYLE = """
QWidget#bottomBar {
    background: palette(base);
    border: none;
    border-top: 1px solid rgba(128, 128, 128, 70);
}
QToolButton#logToggle {
    border: none;
    background: transparent;
    color: palette(windowtext);
    padding: 4px 8px;
    border-radius: 6px;
}
QToolButton#logToggle:hover {
    background: palette(midlight);
}
QToolButton#bottomSettings {
    border: none;
    background: transparent;
    border-radius: 6px;
}
QToolButton#bottomSettings:hover {
    background: palette(midlight);
}
"""

LOG_PANEL_STYLE = """
QPlainTextEdit#logView {
    background: palette(base);
    border: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 16px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._workers: set[TaskWorker] = set()
        self._distros: list[Distro] = []
        self._refresh_busy = False
        self._current: Distro | None = None
        self._last_summary = ""
        self._open_after_refresh = ""
        self._network_busy = False
        self._network_dirty = False
        self._scan_after_start = ""
        self._apply_after_start = ""
        self._pending_cleanup: dict[str, set[int]] = {}
        self._auto_apply_done = False
        self._quitting = False
        self._tray_hint_shown = False

        self.setWindowTitle("WSL Deck")
        self.setWindowIcon(app_icon())
        self.resize(1000, 680)

        self._top_bar = self._build_top_bar()
        self._stack = QStackedWidget(self)
        self._main_page = self._build_main_page()
        self._detail_page = DetailPage(self)
        self._stack.addWidget(self._main_page)
        self._stack.addWidget(self._detail_page)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._top_bar)
        layout.addWidget(self._stack, 1)
        layout.addWidget(self._build_log_panel())
        layout.addWidget(self._build_bottom_bar())
        self.setCentralWidget(central)

        self._tray = TrayController(self)
        if self._tray.available:
            app = QApplication.instance()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
            self._connect_tray_signals()

        log_bus.message.connect(self._append_log)
        self._connect_signals()

        interval = max(3, int(config.get("poll_interval", 10))) * 1000
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(interval)

        self._watch_color_scheme()
        QTimer.singleShot(0, self.refresh)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("topBar")
        bar.setFixedHeight(TOP_BAR_HEIGHT)
        bar.setStyleSheet(TOP_BAR_STYLE + PRIMARY_ACTION_STYLE)

        outer = QVBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._top_stack = QStackedWidget(bar)
        self._top_stack.addWidget(self._build_home_bar())
        self._top_stack.addWidget(self._build_detail_bar())
        outer.addWidget(self._top_stack)
        return bar

    def _build_home_bar(self) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(CONTENT_MARGIN, 8, CONTENT_MARGIN, 8)
        layout.setSpacing(8)

        title = QLabel("WSL Deck", row)
        title.setObjectName("appTitle")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        layout.addStretch(1)

        self._new_btn = QPushButton("新增 Instance", row)
        self._new_btn.setObjectName("primaryAction")
        self._new_btn.setIcon(add_icon())
        self._new_btn.setIconSize(QSize(14, 14))
        self._new_btn.setFixedHeight(32)
        refresh_cursor(self._new_btn)
        self._new_btn.clicked.connect(self._new_instance)
        layout.addWidget(self._new_btn)

        self._shutdown_btn = QPushButton("全部關機", row)
        self._shutdown_btn.setObjectName("secondaryAction")
        self._shutdown_btn.setEnabled(False)
        self._shutdown_btn.setFixedHeight(32)
        refresh_cursor(self._shutdown_btn)
        self._shutdown_btn.clicked.connect(self._shutdown_all)
        layout.addWidget(self._shutdown_btn)

        layout.addSpacing(2)
        layout.addWidget(self._build_bar_divider(row), 0, Qt.AlignVCenter)
        layout.addSpacing(2)

        self.view_toggle = ViewToggle(row)
        self.view_toggle.mode_changed.connect(self._on_view_mode)
        layout.addWidget(self.view_toggle)
        return row

    def _build_bar_divider(self, parent: QWidget) -> QFrame:
        divider = QFrame(parent)
        divider.setObjectName("topBarDivider")
        divider.setFixedSize(1, 32)
        return divider

    def _build_detail_bar(self) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(CONTENT_MARGIN, 8, CONTENT_MARGIN, 8)
        layout.setSpacing(8)

        self._back_btn = QPushButton("返回", row)
        self._back_btn.setObjectName("secondaryAction")
        self._back_btn.setIcon(back_icon())
        self._back_btn.setIconSize(QSize(16, 16))
        self._back_btn.setFixedHeight(32)
        self._back_btn.setMinimumWidth(72)
        refresh_cursor(self._back_btn)
        self._back_btn.clicked.connect(self._show_main)
        layout.addWidget(self._back_btn)
        layout.addStretch(1)
        return row

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(BOTTOM_BAR_HEIGHT)
        bar.setStyleSheet(BOTTOM_BAR_STYLE)

        grid = QGridLayout(bar)
        grid.setContentsMargins(CONTENT_MARGIN, 6, CONTENT_MARGIN, 6)
        grid.setHorizontalSpacing(8)
        grid.setColumnMinimumWidth(0, SIDE_SLOT_WIDTH)
        grid.setColumnMinimumWidth(2, SIDE_SLOT_WIDTH)
        grid.setColumnStretch(1, 1)

        self._log_toggle = QToolButton(bar)
        self._log_toggle.setObjectName("logToggle")
        self._log_toggle.setText("日誌")
        self._log_toggle.setCheckable(True)
        self._log_toggle.setChecked(False)
        self._log_toggle.setAutoRaise(True)
        self._log_toggle.setArrowType(Qt.RightArrow)
        self._log_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._log_toggle.setFixedHeight(30)
        refresh_cursor(self._log_toggle)
        self._log_toggle.toggled.connect(self._on_log_toggled)
        grid.addWidget(self._log_toggle, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self._status_label = QLabel("載入中…", bar)
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #7f8c8d;")
        grid.addWidget(self._status_label, 0, 1)

        self._settings_btn = QToolButton(bar)
        self._settings_btn.setObjectName("bottomSettings")
        self._settings_btn.setToolTip("設定")
        self._settings_btn.setFixedSize(32, 32)
        self._settings_btn.setIcon(settings_themed_icon())
        self._settings_btn.setIconSize(QSize(20, 20))
        self._settings_btn.clicked.connect(self._open_settings)
        refresh_cursor(self._settings_btn)
        grid.addWidget(self._settings_btn, 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        return bar

    def _build_main_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        self._wall_stack = QStackedWidget(page)

        card_scroll = QScrollArea(page)
        card_scroll.setWidgetResizable(True)
        card_scroll.setFrameShape(QFrame.NoFrame)
        card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_wall = CardWall(card_scroll)
        card_scroll.setWidget(self.card_wall)
        self.card_wall.attach_scroll(card_scroll)
        self._wall_stack.addWidget(card_scroll)

        table_scroll = QScrollArea(page)
        table_scroll.setWidgetResizable(True)
        table_scroll.setFrameShape(QFrame.NoFrame)
        table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.instance_table = InstanceTable(table_scroll)
        table_scroll.setWidget(self.instance_table)
        self._wall_stack.addWidget(table_scroll)

        layout.addWidget(self._wall_stack, 1)
        self._apply_view_mode(str(self.config.get("view_mode", "card")), save=False)
        return page

    def _on_view_mode(self, mode: str) -> None:
        self._apply_view_mode(mode)

    def _apply_view_mode(self, mode: str, save: bool = True) -> None:
        if mode not in ("card", "list"):
            mode = "card"
        previous = str(self.config.get("view_mode", "card"))
        if save:
            self.config.data["view_mode"] = mode
            try:
                self.config.save()
            except ConfigError as exc:
                self.config.data["view_mode"] = previous
                self.view_toggle.set_mode(previous)
                self._wall_stack.setCurrentIndex(0 if previous == "card" else 1)
                QMessageBox.warning(self, "視圖設定未儲存", str(exc))
                return
            logger.info("視圖模式已切換為 %s", mode)
        elif previous not in ("card", "list"):
            self.config.data["view_mode"] = mode

        self.view_toggle.set_mode(mode)
        self._wall_stack.setCurrentIndex(0 if mode == "card" else 1)

    def _build_log_panel(self) -> QWidget:
        container = QWidget(self)
        container.setStyleSheet(LOG_PANEL_STYLE)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(CONTENT_MARGIN, 8, CONTENT_MARGIN, 0)
        layout.setSpacing(0)

        self._log_view = QPlainTextEdit(container)
        self._log_view.setObjectName("logView")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(2000)
        self._log_view.setFixedHeight(LOG_PANEL_HEIGHT)
        self._log_view.setVisible(False)
        log_font = QFont("Consolas")
        log_font.setStyleHint(QFont.Monospace)
        self._log_view.setFont(log_font)
        layout.addWidget(self._log_view)
        return container

    def _connect_signals(self) -> None:
        self.card_wall.open_requested.connect(self._show_detail)
        self.card_wall.start_requested.connect(self._start)
        self.card_wall.stop_requested.connect(self._stop)
        self.card_wall.terminal_requested.connect(self._open_terminal)
        self.card_wall.linux_files_requested.connect(self._open_linux_files)
        self.card_wall.install_dir_requested.connect(self._open_install_dir)

        self.instance_table.open_requested.connect(self._show_detail)
        self.instance_table.start_requested.connect(self._start)
        self.instance_table.stop_requested.connect(self._stop)
        self.instance_table.terminal_requested.connect(self._open_terminal)
        self.instance_table.linux_files_requested.connect(self._open_linux_files)
        self.instance_table.install_dir_requested.connect(self._open_install_dir)

        self._detail_page.start_requested.connect(self._start)
        self._detail_page.stop_requested.connect(self._stop)
        self._detail_page.terminal_requested.connect(self._open_terminal)
        self._detail_page.linux_files_requested.connect(self._open_linux_files)
        self._detail_page.install_dir_requested.connect(self._open_install_dir)
        self._detail_page.set_default_requested.connect(self._set_default)
        self._detail_page.backup_requested.connect(self._backup)
        self._detail_page.restore_requested.connect(self._restore)
        self._detail_page.snapshot_requested.connect(self._snapshots)
        self._detail_page.clone_requested.connect(self._clone)
        self._detail_page.delete_requested.connect(self._delete)
        self._detail_page.settings_requested.connect(self._open_instance_settings)
        self._detail_page.network_add_requested.connect(self._network_add)
        self._detail_page.network_edit_requested.connect(self._network_edit)
        self._detail_page.network_delete_requested.connect(self._network_delete)
        self._detail_page.network_apply_requested.connect(self._network_apply)
        self._detail_page.network_scan_requested.connect(self._network_scan)

    def refresh(self) -> None:
        if self._refresh_busy:
            return
        self._refresh_busy = True
        self._run_task(list_distros, self._on_distros, self._on_refresh_error)

    def _on_distros(self, distros: list[Distro]) -> None:
        self._refresh_busy = False
        self._distros = distros
        system_prefixes = self.config.get("system_instances", [])
        system_check = lambda name: is_system_distro(name, system_prefixes)
        self.card_wall.set_distros(distros, system_check)
        self.instance_table.set_distros(distros, system_check)

        running = sum(1 for distro in distros if distro.running)
        stamp = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(
            f"共 {len(distros)} 個 instance，執行中 {running} 個｜更新於 {stamp}"
        )
        self._shutdown_btn.setEnabled(running > 0)
        refresh_cursor(self._shutdown_btn)

        default = next(
            (
                item for item in distros
                if item.is_default and not self._is_system(item.name)
            ),
            None,
        )
        self._tray.update_state(
            has_default=default is not None,
            default_running=bool(default and default.running),
            running=running,
        )

        summary = f"{len(distros)}/{running}"
        if summary != self._last_summary:
            logger.info("載入 %d 個 instance（執行中 %d）", len(distros), running)
            self._last_summary = summary

        if self._current is not None:
            current = next(
                (distro for distro in distros if distro.name == self._current.name),
                None,
            )
            if current is None:
                self._show_main()
            else:
                self._current = current
                self._detail_page.set_distro(
                    current,
                    self._is_system(current.name),
                )
                if current.running:
                    self._load_ip(current.name)
                self._refresh_network(current.name)

        if self._open_after_refresh:
            name = self._open_after_refresh
            self._open_after_refresh = ""
            target = next((distro for distro in distros if distro.name == name), None)
            if target is not None:
                self._show_detail(target)

        if not self._auto_apply_done:
            self._auto_apply_done = True
            has_rules = any(
                distro.running
                and self.config.port_forwards_for(distro.name)
                for distro in distros
                if not self._is_system(distro.name)
            )
            if has_rules:
                QTimer.singleShot(0, self._auto_apply_all)

        self._load_homepage_ips(distros)

    def _load_homepage_ips(self, distros: list[Distro]) -> None:
        """對所有 running 的 instance 非同步查 IP，回填到首頁卡片與列表。"""
        for distro in distros:
            if not distro.running or self._is_system(distro.name):
                continue
            self._run_task(
                partial(self._ip_for, distro.name),
                partial(self._on_homepage_ip, distro.name),
                partial(self._on_homepage_ip_error, distro.name),
            )

    def _on_homepage_ip(self, name: str, ip: str) -> None:
        for i, distro in enumerate(self._distros):
            if distro.name == name:
                self._distros[i] = replace(distro, ip=ip)
                system_prefixes = self.config.get("system_instances", [])
                is_system = is_system_distro(name, system_prefixes)
                self.card_wall.update_distro_info(name, self._distros[i], is_system)
                self.instance_table.update_distro_info(name, self._distros[i], is_system)
                if (
                    self._current is not None
                    and self._current.name == name
                    and self._stack.currentWidget() is self._detail_page
                ):
                    self._detail_page.set_ip(ip)
                break

    def _on_homepage_ip_error(self, name: str, message: str) -> None:
        logger.warning("取得 %s 的 IP 失敗：%s", name, message)

    def _on_refresh_error(self, message: str) -> None:
        self._refresh_busy = False
        logger.error("讀取 WSL 狀態失敗：%s", message)
        self._status_label.setText("無法讀取 WSL 狀態（請查看日誌）")

    # ---------- 托盤與關窗 ----------

    @property
    def tray_available(self) -> bool:
        return self._tray.available

    def _connect_tray_signals(self) -> None:
        self._tray.show_requested.connect(self.show_window)
        self._tray.start_default_requested.connect(self._tray_start_default)
        self._tray.shutdown_all_requested.connect(self._tray_shutdown_all)
        self._tray.reapply_requested.connect(self._tray_reapply)
        self._tray.quit_requested.connect(self._quit_app)

    def show_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_start_default(self) -> None:
        distro = next(
            (
                item for item in self._distros
                if item.is_default and not self._is_system(item.name)
            ),
            None,
        )
        if distro is None:
            self.show_window()
            QMessageBox.information(
                self, "啟動預設 instance", "找不到可啟動的預設 instance。"
            )
            return
        if distro.running:
            self.show_window()
            self._show_detail(distro)
            return
        self._start(distro.name)

    def _tray_shutdown_all(self) -> None:
        self.show_window()
        self._shutdown_all()

    def _tray_reapply(self) -> None:
        self.show_window()
        if not self._auto_apply_all(silent_empty=True):
            self._tray.show_message(
                "重新套用網路規則", "目前沒有需要重套的規則。"
            )

    def _quit_app(self) -> None:
        self._quitting = True
        self._tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if (
            self._quitting
            or not self.config.get("close_to_tray", True)
            or not self._tray.available
        ):
            self._quitting = True
            try:
                cleanup_netns(self.config.data, restart=True)
            except Exception:  # noqa: BLE001 - 結束時盡量還原
                logger.warning("結束前還原臨時 netns 失敗")
            self._tray.hide()
            event.accept()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self._tray.show_message(
                "WSL Deck 仍在背景執行",
                "可從托盤圖標重新開啟，或選擇「結束」離開。",
            )

    # ---------- 設定 ----------

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        old = {key: self.config.get(key) for key in values}
        autostart_changed = bool(values["autostart"]) != bool(
            self.config.get("autostart", False)
        )
        if is_supported() and autostart_changed:
            try:
                set_autostart(bool(values["autostart"]))
            except (OSError, RuntimeError) as exc:
                QMessageBox.warning(self, "開機自啟設定失敗", str(exc))
                return

        self.config.data.update(values)
        try:
            self.config.save()
        except ConfigError as exc:
            self.config.data.update(old)
            if is_supported() and autostart_changed:
                try:
                    set_autostart(bool(old["autostart"]))
                except (OSError, RuntimeError):
                    logger.warning("回復開機自啟設定失敗")
            QMessageBox.warning(self, "設定未儲存", str(exc))
            return

        self._apply_settings()

    def _apply_settings(self) -> None:
        apply_runtime(parse_config(self.config.get("proxy")))
        try:
            ensure_workspace(self.config.workspace())
        except OSError as exc:
            logger.warning("建立工作目錄骨架失敗：%s", exc)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, str(self.config.get("theme", "system")))
            self._back_btn.setIcon(back_icon())
            self._settings_btn.setIcon(settings_themed_icon())
        interval = max(3, int(self.config.get("poll_interval", 10))) * 1000
        self._timer.start(interval)
        logger.info("設定已更新")
        self.refresh()

    def _watch_color_scheme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)

    def _on_color_scheme_changed(self, _scheme) -> None:
        if self.config.get("theme", "system") == "system":
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, "system")
                self._back_btn.setIcon(back_icon())
                self._settings_btn.setIcon(settings_themed_icon())

    def _run_task(self, fn, on_done, on_error=None, *args, **kwargs) -> None:
        worker = TaskWorker(fn, *args, **kwargs)
        self._workers.add(worker)
        worker.signals.finished.connect(partial(self._on_task_finished, worker, on_done))
        worker.signals.failed.connect(partial(self._on_task_failed, worker, on_error))
        QThreadPool.globalInstance().start(worker)

    def _on_task_finished(self, worker: TaskWorker, callback, result) -> None:
        self._workers.discard(worker)
        callback(result)

    def _on_task_failed(self, worker: TaskWorker, callback, message: str) -> None:
        self._workers.discard(worker)
        if callback is not None:
            callback(message)

    def _is_system(self, name: str) -> bool:
        return is_system_distro(name, self.config.get("system_instances", []))

    def _find(self, name: str) -> Distro | None:
        return next((distro for distro in self._distros if distro.name == name), None)

    def _show_detail(self, distro: Distro) -> None:
        self._current = distro
        self._detail_page.set_distro(distro, self._is_system(distro.name))
        self._top_stack.setCurrentIndex(1)
        self._stack.setCurrentWidget(self._detail_page)
        if distro.running:
            self._load_ip(distro.name)
        self._refresh_network(distro.name)

    def _show_main(self) -> None:
        self._current = None
        self._stack.setCurrentWidget(self._main_page)
        self._top_stack.setCurrentIndex(0)

    def _load_ip(self, name: str) -> None:
        self._run_task(
            partial(self._ip_for, name),
            partial(self._on_ip, name),
            partial(self._on_ip_error, name),
        )

    def _ip_for(self, name: str) -> str:
        return effective_ip(name, self.config.instance_network(name))

    def _on_ip(self, name: str, ip: str) -> None:
        if (
            self._current is not None
            and self._current.name == name
            and self._stack.currentWidget() is self._detail_page
        ):
            self._detail_page.set_ip(ip)

    def _on_ip_error(self, name: str, message: str) -> None:
        logger.warning("取得 %s 的 IP 失敗：%s", name, message)
        if self._current is not None and self._current.name == name:
            self._detail_page.set_ip("未取得")

    def _start(self, name: str) -> None:
        if self._is_system(name):
            return
        logger.info("啟動 %s…", name)
        network = self.config.instance_network(name)

        def task():
            start_distro(name)
            return ensure_after_start(name, network)

        self._run_task(
            task,
            partial(self._after_started, name),
            partial(self._on_start_error, name),
        )

    def _on_start_error(self, name: str, message: str) -> None:
        if self._scan_after_start == name:
            self._scan_after_start = ""
        if self._apply_after_start == name:
            self._apply_after_start = ""
        self._on_action_error(f"啟動 {name}", message)

    def _stop(self, name: str) -> None:
        if self._is_system(name):
            return
        logger.info("終止 %s…", name)
        network = self.config.instance_network(name)

        def task():
            if network.get("enabled") and network.get("scope") != "permanent":
                cleanup_temporary(
                    name,
                    network.get("services", []),
                    str(network.get("ip") or ""),
                    restart=False,
                )
            terminate_distro(name)

        self._run_task(
            task,
            lambda _result: self._after_action(f"已終止 {name}"),
            partial(self._on_action_error, f"終止 {name}"),
        )

    def _set_default(self, name: str) -> None:
        if self._is_system(name):
            return
        logger.info("設定預設 instance：%s…", name)
        self._run_task(
            partial(set_default_distro, name),
            lambda _result: self._after_action(f"已將 {name} 設為預設"),
            partial(self._on_action_error, f"設定 {name} 為預設"),
        )

    def _shutdown_all(self) -> None:
        running = [distro for distro in self._distros if distro.running]
        if not running:
            QMessageBox.information(self, "全部關機", "目前沒有執行中的 instance。")
            return
        names = "\n".join(f"• {distro.name}" for distro in running)
        text = (
            f"以下 instance 將被終止：\n\n{names}\n\n"
            "注意：docker-desktop 也會一併終止，Docker Desktop 會停止運作。\n\n"
            "確定要全部關機嗎？"
        )
        answer = QMessageBox.warning(
            self,
            "全部關機",
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        logger.info("全部關機…")

        def task():
            cleanup_netns(self.config.data, restart=False)
            shutdown_all()

        self._run_task(
            task,
            lambda _result: self._after_action("已全部關機"),
            partial(self._on_action_error, "全部關機"),
        )

    def _run_operation(self, title, fn, on_success, on_error=None) -> None:
        self._timer.stop()
        dialog = OperationDialog(title, self)
        worker = TaskWorker(fn, with_stage=True)
        self._workers.add(worker)
        outcome: dict[str, object] = {}

        def finish(result) -> None:
            outcome["result"] = result
            dialog.accept()

        def fail(message: str) -> None:
            outcome["error"] = message
            dialog.reject()

        worker.signals.stage.connect(dialog.set_stage)
        worker.signals.finished.connect(finish)
        worker.signals.failed.connect(fail)
        QThreadPool.globalInstance().start(worker)
        dialog.exec()
        self._workers.discard(worker)
        self._timer.start(max(3, int(self.config.get("poll_interval", 10))) * 1000)

        if "error" in outcome:
            message = str(outcome["error"])
            logger.error("%s失敗：%s", title, message)
            QMessageBox.warning(
                self, f"{title}失敗", f"{message}\n\n詳細步驟請見日誌。"
            )
            if on_error is not None:
                on_error(message)
            return
        on_success(outcome.get("result"))

    def _new_instance(self) -> None:
        wizard = NewInstanceWizard(
            self.config.instance_root(),
            [distro.name for distro in self._distros],
            self,
        )
        if wizard.exec() != QDialog.Accepted or wizard.plan is None:
            return
        plan = wizard.plan
        logger.info("新增 instance：%s（來源：%s）", plan.name, plan.source)
        self._run_operation(
            "新增 Instance",
            partial(create_instance, plan),
            lambda _result: self._after_created(plan.name),
            lambda _message: self.refresh(),
        )

    def _after_created(self, name: str) -> None:
        logger.info("已新增 %s", name)
        self._open_after_refresh = name
        self.refresh()

    def _backup(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        dialog = BackupDialog(distro, self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._run_operation(
            f"備份 {name}",
            partial(backup_instance, distro, dialog.file_path, dialog.vhd),
            lambda _result: self._after_action(f"已備份 {name} 到 {dialog.file_path}"),
            lambda _message: self.refresh(),
        )

    def _restore(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        dialog = RestoreDialog(distro, self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._run_operation(
            f"還原 {name}",
            partial(
                restore_instance,
                distro,
                dialog.file_path,
                dialog.keep_current,
                self.config.resolve_path(self.config.get("backup_root", "backups")),
            ),
            lambda _result: self._after_action(f"已還原 {name}"),
            lambda _message: self.refresh(),
        )

    def _snapshots(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        SnapshotDialog(distro, self.config, self).exec()

    def _clone(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        dialog = CloneDialog(
            distro, self.config, [item.name for item in self._distros], self
        )
        if dialog.exec() != QDialog.Accepted:
            return
        backup_root = self.config.resolve_path(self.config.get("backup_root", "backups"))
        self._run_operation(
            f"複製 {name}",
            partial(
                clone_instance,
                distro,
                dialog.new_name,
                dialog.target_dir,
                backup_root / "_tmp",
            ),
            lambda _result: self._after_created(dialog.new_name),
            lambda _message: self.refresh(),
        )

    def _delete(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        dialog = DeleteDialog(distro, self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        rules = list(self.config.port_forwards_for(name))
        ports = [rule["windows_port"] for rule in rules]

        def removed(_result) -> None:
            count = self.config.remove_port_forwards(name)
            if count:
                logger.info("已移除 %s 的 %d 條端口規則", name, count)
            self.config.remove_instance_network(name)
            if self._current is not None and self._current.name == name:
                self._show_main()
            self._after_action(f"已刪除 {name}")
            if ports:
                self._run_operation(
                    "移除網路規則",
                    partial(
                        apply_rules,
                        [],
                        [(name, port) for port in ports],
                        ip_resolver=self._ip_for,
                    ),
                    self._on_delete_cleanup_done,
                    lambda _message: None,
                )

        self._run_operation(
            f"刪除 {name}",
            partial(delete_instance, distro, dialog.backup_file),
            removed,
            lambda _message: self.refresh(),
        )

    def _on_delete_cleanup_done(self, result) -> None:
        if result.denied or result.errors:
            logger.warning(
                "刪除 instance 後網路規則未清除：%s",
                "；".join(result.errors) or "已取消管理員授權",
            )
            QMessageBox.warning(
                self,
                "網路規則未清除",
                "instance 已刪除，但 portproxy／防火牆規則未移除。\n"
                "可稍後以系統管理員手動清理，或重新啟動 App 後再試。",
            )
        else:
            logger.info("已清除刪除 instance 的網路規則")

    def _after_action(self, message: str) -> None:
        logger.info("%s", message)
        self.refresh()

    # ---------- Instance 設定 ----------

    def _open_instance_settings(self, name: str) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        sparse = is_sparse(distro.vhdx_path)
        if not distro.running:
            self._show_instance_settings(distro, False, None, sparse)
            return
        self._run_task(
            partial(read_settings, name),
            partial(self._on_instance_settings, distro, sparse),
            partial(self._on_settings_read_error, distro),
        )

    def _on_instance_settings(self, distro: Distro, sparse, settings) -> None:
        current = self._find(distro.name)
        if current is None:
            return
        self._show_instance_settings(current, True, settings, sparse)

    def _on_settings_read_error(self, distro: Distro, message: str) -> None:
        logger.warning("讀取 %s 的 instance 設定失敗：%s", distro.name, message)
        QMessageBox.warning(
            self,
            "讀取設定失敗",
            f"無法讀取 {distro.name} 的 /etc/wsl.conf：{message}",
        )

    def _show_instance_settings(
        self,
        distro: Distro,
        running: bool,
        settings,
        sparse: bool | None,
    ) -> None:
        dialog = InstanceSettingsDialog(
            distro,
            running,
            settings,
            sparse,
            self,
            network=self.config.instance_network(distro.name),
        )
        dialog.maintenance_requested.connect(
            partial(self._run_instance_maintenance, distro.name)
        )
        if dialog.exec() != QDialog.Accepted:
            return
        network = dialog.network_values()
        network_changed = dialog.network_changed()
        settings_changed = running and dialog.has_changes()
        if not network_changed and not settings_changed:
            return

        if network_changed:
            try:
                self.config.set_instance_network(distro.name, network)
            except ConfigError as exc:
                QMessageBox.warning(self, "網路隔離設定未儲存", str(exc))
                return

        if not running:
            logger.info("已儲存 %s 的設定，啟動時生效", distro.name)
            QMessageBox.information(
                self,
                "設定已儲存",
                "instance 目前停止；網路隔離設定將在下次啟動時套用。",
            )
            self.refresh()
            return

        values = dialog.values() if settings_changed else None

        def task():
            if values is not None:
                apply_settings(distro.name, distro.version, values)
            if network_changed:
                return ensure_after_start(distro.name, network, force=True)
            return []

        def done(warnings) -> None:
            if values is not None:
                logger.info("已更新 %s 的 instance 設定", distro.name)
            if warnings:
                logger.warning("；".join(warnings))
                QMessageBox.warning(
                    self, "網路隔離未完全套用", "\n".join(warnings)
                )
            self.refresh()

        self._run_operation(
            f"套用 {distro.name} 設定",
            task,
            done,
            lambda _message: self.refresh(),
        )

    def _run_instance_maintenance(self, name: str, kind: str, value) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        if kind == "version":
            self._run_operation(
                f"切換 {name} 為 WSL {value}",
                partial(set_version, name, int(value)),
                lambda _result: self._after_maintenance(
                    name, f"已切換為 WSL {value}，instance 目前為停止狀態。"
                ),
                lambda _message: self.refresh(),
            )
            return
        if kind == "sparse":
            action = "啟用" if value else "停用"
            self._run_operation(
                f"{action} {name} 的 Sparse VHD",
                partial(set_sparse, name, bool(value)),
                lambda _result: self._after_maintenance(
                    name, f"已{action} Sparse VHD。"
                ),
                lambda _message: self.refresh(),
            )
            return
        if kind == "compact":
            self._run_operation(
                f"壓縮 {name} 的 VHD",
                partial(compact_vhd, name, distro.vhdx_path),
                partial(self._after_compact, name),
                lambda _message: self.refresh(),
            )

    def _after_maintenance(self, name: str, message: str) -> None:
        logger.info("%s：%s", name, message)
        QMessageBox.information(self, "維護完成", message)
        self.refresh()

    def _after_compact(self, name: str, freed: int) -> None:
        freed_gb = freed / 1024 ** 3
        message = f"已壓縮 {name} 的 VHD，回收 {freed_gb:.2f} GB。"
        logger.info("%s", message)
        QMessageBox.information(self, "壓縮完成", message)
        self.refresh()

    # ---------- 網路規則 ----------

    def _current_distro(self) -> Distro | None:
        if self._current is None:
            return None
        return self._find(self._current.name)

    def _refresh_network(self, name: str, rules: list[dict] | None = None) -> None:
        if self._current is None or self._current.name != name:
            return
        if self._stack.currentWidget() is not self._detail_page:
            return
        if self._network_busy:
            self._network_dirty = True
            return
        distro = self._find(name)
        if distro is None:
            return
        if rules is None:
            rules = self.config.port_forwards_for(name)
        self._network_busy = True
        self._network_dirty = False
        self._run_task(
            partial(self._network_snapshot, name, distro.running),
            partial(self._on_network_snapshot, name, rules),
            partial(self._on_network_error, name, rules),
        )

    def _network_snapshot(self, name: str, running: bool):
        entries = show_portproxy()
        ip = self._ip_for(name) if running else ""
        return ip, entries

    def _on_network_snapshot(self, name: str, rules: list[dict], snapshot) -> None:
        self._network_busy = False
        distro = self._find(name)
        if (
            distro is not None
            and self._current is not None
            and self._current.name == name
            and self._stack.currentWidget() is self._detail_page
        ):
            ip, entries = snapshot
            statuses = {
                rule["windows_port"]: rule_status(rule, distro.running, ip, entries)
                for rule in rules
            }
            self._detail_page.set_network(rules, statuses)
        self._after_network_refresh(name)

    def _on_network_error(self, name: str, rules: list[dict], message: str) -> None:
        self._network_busy = False
        logger.warning("讀取網路狀態失敗：%s", message)
        distro = self._find(name)
        running = bool(distro and distro.running)
        statuses = {
            rule["windows_port"]: (
                "待啟動" if not running
                else ("已停用" if not rule.get("enabled", True) else "待套用")
            )
            for rule in rules
        }
        if self._current is not None and self._current.name == name:
            self._detail_page.set_network(rules, statuses)
        self._after_network_refresh(name)

    def _after_network_refresh(self, name: str) -> None:
        if self._network_dirty:
            self._network_dirty = False
            QTimer.singleShot(0, partial(self._refresh_network, name))

    def _network_add(self) -> None:
        distro = self._current_distro()
        if distro is None or self._is_system(distro.name):
            return
        dialog = RuleDialog(
            distro.name, self.config.data["port_forwards"], None, self
        )
        if dialog.exec() != QDialog.Accepted or dialog.rule is None:
            return
        self.config.data["port_forwards"].append(dialog.rule)
        try:
            self.config.save()
        except ConfigError as exc:
            self.config.data["port_forwards"].pop()
            QMessageBox.warning(self, "規則錯誤", str(exc))
            return
        self._after_rule_change(distro.name)

    def _network_edit(self, windows_port: int) -> None:
        distro = self._current_distro()
        if distro is None or self._is_system(distro.name):
            return
        rule = next(
            (
                item for item in self.config.data["port_forwards"]
                if item["distro"] == distro.name
                and item["windows_port"] == windows_port
            ),
            None,
        )
        if rule is None:
            return
        dialog = RuleDialog(
            distro.name, self.config.data["port_forwards"], rule, self
        )
        if dialog.exec() != QDialog.Accepted or dialog.rule is None:
            return
        index = self.config.data["port_forwards"].index(rule)
        old = dict(rule)
        self.config.data["port_forwards"][index] = dialog.rule
        try:
            self.config.save()
        except ConfigError as exc:
            self.config.data["port_forwards"][index] = old
            QMessageBox.warning(self, "規則錯誤", str(exc))
            return
        cleanup = (
            [old["windows_port"]]
            if old["windows_port"] != dialog.rule["windows_port"]
            else []
        )
        self._after_rule_change(distro.name, cleanup)

    def _network_delete(self, windows_port: int) -> None:
        distro = self._current_distro()
        if distro is None or self._is_system(distro.name):
            return
        rule = next(
            (
                item for item in self.config.data["port_forwards"]
                if item["distro"] == distro.name
                and item["windows_port"] == windows_port
            ),
            None,
        )
        if rule is None:
            return
        answer = QMessageBox.question(
            self,
            "刪除網路規則",
            f"刪除規則 {rule['windows_port']} → {rule['distro_port']}？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        index = self.config.data["port_forwards"].index(rule)
        self.config.data["port_forwards"].pop(index)
        try:
            self.config.save()
        except ConfigError as exc:
            self.config.data["port_forwards"].insert(index, rule)
            QMessageBox.warning(self, "規則錯誤", str(exc))
            return
        self._after_rule_change(distro.name, [windows_port])

    def _after_rule_change(self, name: str, cleanup: list[int] | None = None) -> None:
        distro = self._find(name)
        self._refresh_network(name)
        if distro is None:
            return
        pending = self._pending_cleanup.setdefault(name, set())
        pending.update(cleanup or [])
        used = {
            rule["windows_port"] for rule in self.config.data["port_forwards"]
        }
        self._pending_cleanup[name] = {
            port for port in pending if port not in used
        }
        if distro.running:
            answer = QMessageBox.question(
                self,
                "規則已變更",
                "要立即套用變更嗎？\n未套用前，舊的端口轉發可能仍然有效。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._apply_instance(name)
                return
        logger.info("網路規則變更待套用：%s", name)

    def _network_apply(self) -> None:
        distro = self._current_distro()
        if distro is None or self._is_system(distro.name):
            return
        self._apply_instance(distro.name)

    def _apply_instance(self, name: str, cleanup_ports: list[int] | None = None) -> None:
        distro = self._find(name)
        if distro is None or self._is_system(name):
            return
        if not distro.running:
            answer = QMessageBox.question(
                self,
                "套用網路規則",
                "instance 未執行，要先啟動再套用嗎？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._apply_after_start = name
                self._start(name)
            return

        pending = set(self._pending_cleanup.get(name, set()))
        pending.update(cleanup_ports or [])
        used = {
            rule["windows_port"] for rule in self.config.data["port_forwards"]
        }
        cleanup = [
            (name, port) for port in sorted(pending) if port not in used
        ]
        rules = self.config.port_forwards_for(name)
        self._run_operation(
            "套用網路規則",
            partial(apply_rules, [(name, rules)], cleanup, ip_resolver=self._ip_for),
            partial(self._on_apply_done, name),
            lambda _message: self._refresh_network(name),
        )

    def _on_apply_done(self, name: str, result) -> None:
        if result.ok:
            self._pending_cleanup.pop(name, None)
        for command in result.commands:
            logger.info("管理員命令：%s", command)
        if result.denied:
            QMessageBox.warning(
                self, "需要管理員權限", "已取消管理員授權，規則維持待套用。"
            )
        elif result.errors:
            QMessageBox.warning(self, "套用失敗", "\n".join(result.errors))
        if result.warnings:
            logger.warning("；".join(result.warnings))
            skipped = [
                warning for warning in result.warnings
                if "已被其他程式佔用" in warning
            ]
            if skipped:
                QMessageBox.information(
                    self, "部分規則未套用", "\n".join(skipped)
                )
        if result.ok and not result.denied:
            logger.info("已套用 %s 的網路規則", name)
        else:
            logger.warning("套用 %s 的網路規則未完成", name)
        self._refresh_network(name)
        self.refresh()

    def _network_scan(self) -> None:
        distro = self._current_distro()
        if distro is None or self._is_system(distro.name):
            return
        if not distro.running:
            answer = QMessageBox.question(
                self,
                "掃描監聽端口",
                "instance 未執行，要先啟動再掃描嗎？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            self._scan_after_start = distro.name
            self._start(distro.name)
            return
        self._scan_ports(distro.name)

    def _scan_ports(self, name: str) -> None:
        network = self.config.instance_network(name)
        namespace = netns_name(name) if network.get("enabled") else None
        self._run_operation(
            "掃描監聽端口",
            partial(scan_tcp_ports, name, namespace),
            partial(self._show_scan_result, name),
            lambda _message: None,
        )

    def _show_scan_result(self, name: str, ports: list[int]) -> None:
        if not ports:
            QMessageBox.information(
                self, "掃描監聽端口", "沒有找到監聽中的 TCP 端口。"
            )
            return
        dialog = ScanDialog(
            name, ports, self.config.data["port_forwards"], self
        )
        if dialog.exec() != QDialog.Accepted or not dialog.rules:
            return
        before = len(self.config.data["port_forwards"])
        self.config.data["port_forwards"].extend(dialog.rules)
        try:
            self.config.save()
        except ConfigError as exc:
            del self.config.data["port_forwards"][before:]
            QMessageBox.warning(self, "規則錯誤", str(exc))
            return
        self._after_rule_change(name)

    def _after_started(self, name: str, messages=None) -> None:
        logger.info("已啟動 %s", name)
        self._mark_running(name)
        if messages:
            logger.warning("；".join(messages))
            QMessageBox.warning(
                self, "網路隔離未完全套用", "\n".join(messages)
            )
        if self._scan_after_start == name:
            self._scan_after_start = ""
            self._scan_ports(name)
            return
        if self._apply_after_start == name:
            self._apply_after_start = ""
            self._apply_instance(name)
            return
        rules = self.config.port_forwards_for(name)
        if rules or name in self._pending_cleanup:
            self._apply_instance(name)
        else:
            self.refresh()

    def _mark_running(self, name: str) -> None:
        for index, distro in enumerate(self._distros):
            if distro.name == name:
                updated = replace(distro, state="Running")
                self._distros[index] = updated
                if self._current is not None and self._current.name == name:
                    self._current = updated
                break

    def _auto_apply_all(self, silent_empty: bool = False) -> bool:
        targets: list[tuple[str, list[dict]]] = []
        for distro in self._distros:
            if not distro.running or self._is_system(distro.name):
                continue
            rules = self.config.port_forwards_for(distro.name)
            if rules:
                targets.append((distro.name, rules))
        if not targets:
            if not silent_empty:
                logger.info("沒有需要重套的網路規則")
            return False
        logger.info("重新套用 %d 個 instance 的網路規則…", len(targets))
        self._run_operation(
            "重新套用網路規則",
            partial(apply_rules, targets, ip_resolver=self._ip_for),
            self._on_auto_apply_done,
            lambda _message: self.refresh(),
        )
        return True

    def _on_auto_apply_done(self, result) -> None:
        for command in result.commands:
            logger.info("管理員命令：%s", command)
        if result.denied:
            logger.warning("已取消管理員授權，網路規則維持待套用")
            QMessageBox.warning(
                self,
                "網路規則未套用",
                "已取消管理員授權；可在詳情頁按「立即套用」重試。",
            )
        if result.errors:
            logger.warning("自動套用失敗：%s", "；".join(result.errors))
            QMessageBox.warning(
                self, "自動套用失敗", "\n".join(result.errors)
            )
        if result.warnings:
            logger.warning("；".join(result.warnings))
        if self._current is not None:
            self._refresh_network(self._current.name)
        self.refresh()

    def _on_action_error(self, action: str, message: str) -> None:
        logger.error("%s失敗：%s", action, message)
        QMessageBox.warning(self, f"{action}失敗", message)

    def _open_terminal(self, name: str) -> None:
        if self._is_system(name):
            return
        self._run_task(
            partial(terminal_user, name),
            partial(self._launch_terminal, name),
        )

    def _launch_terminal(self, name: str, user: str) -> None:
        try:
            open_terminal(name, user)
        except Exception as exc:  # noqa: BLE001 - 顯示給使用者
            self._show_error(f"開啟終端失敗：{exc}")

    def _open_linux_files(self, name: str) -> None:
        if self._is_system(name):
            return
        try:
            open_path(f"\\\\wsl$\\{name}\\")
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"開啟 Linux 檔案失敗：{exc}")

    def _open_install_dir(self, path: str) -> None:
        try:
            open_path(path)
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"開啟安裝目錄失敗：{exc}")

    def _show_error(self, message: str) -> None:
        logger.error("%s", message)
        QMessageBox.warning(self, "操作失敗", message)

    def _append_log(self, message: str) -> None:
        if (
            not self.config.get("advanced_mode", False)
            and "管理員命令：" in message
        ):
            return
        self._log_view.appendPlainText(message)
        if "ERROR" in message:
            self._log_toggle.setChecked(True)

    def _on_log_toggled(self, checked: bool) -> None:
        self._log_view.setVisible(checked)
        self._log_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.refresh()
