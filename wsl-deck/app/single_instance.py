"""單一實例守衛：第二次啟動只喚醒既有視窗。"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QDir, QLockFile, QObject, QStandardPaths, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)


class SingleInstance(QObject):
    """以鎖檔判斷是否已有實例，首個實例再開本地管道接收喚醒請求。"""

    activated = Signal()

    def __init__(self, key: str, parent=None) -> None:
        super().__init__(parent)
        self._key = key
        self._lock = QLockFile(self._lock_path(key))
        self._server: QLocalServer | None = None

    @staticmethod
    def _lock_path(key: str) -> str:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.TempLocation
        )
        return QDir(base).filePath(f"{key}.lock")

    def acquire(self) -> bool:
        """搶鎖並開始監聽；已有實例時回傳 False。"""
        if not self._lock.tryLock(100):
            return False
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        if not self._server.listen(self._key):
            logger.warning("單一實例監聽失敗：%s", self._server.errorString())
        return True

    def activate_existing(self, timeout_ms: int = 300, attempts: int = 5) -> bool:
        """連上既有實例的管道以喚醒視窗；連不上回傳 False。"""
        for attempt in range(attempts):
            socket = QLocalSocket()
            socket.connectToServer(self._key)
            if socket.waitForConnected(timeout_ms):
                socket.disconnectFromServer()
                return True
            if attempt < attempts - 1:
                time.sleep(0.1)
        return False

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(self._key)
        self._lock.unlock()

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        logger.debug("單一實例：收到喚醒請求")
        self.activated.emit()
        socket.disconnectFromServer()
        socket.deleteLater()
