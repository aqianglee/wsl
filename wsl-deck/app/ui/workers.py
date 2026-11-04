"""可重用的背景工作。"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


def _accepts_stage(fn: Callable) -> bool:
    """判斷可呼叫物件是否接受 stage 關鍵字參數。"""
    try:
        parameters = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "stage" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    stage = Signal(str)


class TaskWorker(QRunnable):
    def __init__(self, fn: Callable, *args, with_stage: bool = False, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.with_stage = with_stage
        self.signals = TaskSignals()

    def run(self) -> None:
        if self.with_stage and _accepts_stage(self.fn):
            self.kwargs.setdefault("stage", self._emit_stage)
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - 錯誤需回報到 UI
            logger.exception("背景工作失敗")
            self._emit(self.signals.failed, str(exc))
        else:
            self._emit(self.signals.finished, result)

    def _emit_stage(self, message: str) -> None:
        self._emit(self.signals.stage, message)

    @staticmethod
    def _emit(signal, value) -> None:
        try:
            signal.emit(value)
        except RuntimeError:
            logger.debug("UI 已關閉，丟棄背景工作結果")
