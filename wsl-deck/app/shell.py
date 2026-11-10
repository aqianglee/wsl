"""開啟終端與資料夾等外部程式。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from app.wsl import WslError, run_wsl

logger = logging.getLogger(__name__)

CREATE_NEW_CONSOLE = 0x00000010


def terminal_user(distro_name: str) -> str:
    """回傳 instance 的預設登入使用者；查不到時回傳空字串。"""
    try:
        return run_wsl(["-d", distro_name, "--", "whoami"], timeout=60).strip()
    except WslError as exc:
        logger.warning(
            "查詢 %s 的登入使用者失敗，終端標題只顯示 instance 名稱：%s",
            distro_name,
            exc,
        )
        return ""


def terminal_args(distro_name: str, user: str = "") -> list[str]:
    """組出 Windows Terminal 指令；標題固定為「使用者@實例名」。"""
    title = f"{user}@{distro_name}" if user else distro_name
    return [
        "wt.exe",
        "new-tab",
        "--title",
        title,
        "--suppressApplicationTitle",
        "wsl.exe",
        "-d",
        distro_name,
    ]


def open_terminal(distro_name: str, user: str = "") -> None:
    if shutil.which("wt.exe"):
        subprocess.Popen(terminal_args(distro_name, user))
        return
    subprocess.Popen(
        ["wsl.exe", "-d", distro_name],
        creationflags=CREATE_NEW_CONSOLE,
    )


def open_path(path: str) -> None:
    if not path:
        raise ValueError("路徑為空")
    if not path.startswith("\\\\") and not os.path.exists(path):
        raise FileNotFoundError(f"找不到路徑：{path}")
    subprocess.Popen(["explorer.exe", path])
