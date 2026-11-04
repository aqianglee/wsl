"""托盤圖標與右鍵選單。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.ui.app_icon import app_icon


class TrayController(QObject):
    show_requested = Signal()
    start_default_requested = Signal()
    shutdown_all_requested = Signal()
    reapply_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tray: QSystemTrayIcon | None = None
        self._start_action = None
        self._shutdown_action = None
        if not self._available:
            return

        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("WSL Deck")
        menu = QMenu()
        show_action = menu.addAction("顯示主視窗")
        show_action.triggered.connect(lambda: self.show_requested.emit())
        self._start_action = menu.addAction("啟動預設 instance")
        self._start_action.triggered.connect(
            lambda: self.start_default_requested.emit()
        )
        self._shutdown_action = menu.addAction("全部關機")
        self._shutdown_action.triggered.connect(
            lambda: self.shutdown_all_requested.emit()
        )
        reapply_action = menu.addAction("重新套用網路規則")
        reapply_action.triggered.connect(lambda: self.reapply_requested.emit())
        menu.addSeparator()
        quit_action = menu.addAction("結束")
        quit_action.triggered.connect(lambda: self.quit_requested.emit())

        self._menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._start_action.setEnabled(False)
        self._shutdown_action.setEnabled(False)
        self._tray.show()

    @property
    def available(self) -> bool:
        return self._available

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()

    def update_state(self, has_default: bool, default_running: bool, running: int) -> None:
        if self._tray is None:
            return
        self._start_action.setEnabled(has_default and not default_running)
        self._shutdown_action.setEnabled(running > 0)
        self._tray.setToolTip(f"WSL Deck｜執行中 {running} 個")

    def show_message(self, title: str, text: str) -> None:
        if self._tray is not None:
            self._tray.showMessage(title, text, app_icon(), 4000)

    def hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()
