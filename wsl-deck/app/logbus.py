"""把 logging 導向檔案與 UI。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class LogBus(QObject):
    message = Signal(str)


log_bus = LogBus()


class QtLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_bus.message.emit(self.format(record))
        except RuntimeError:
            pass


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(file_handler)

    ui_handler = QtLogHandler()
    ui_handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(ui_handler)
