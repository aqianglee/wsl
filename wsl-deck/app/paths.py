"""可寫路徑：開發模式與 PyInstaller onedir 皆適用。"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """config.json 與 logs 的所在目錄；凍結後是 exe 所在資料夾。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
