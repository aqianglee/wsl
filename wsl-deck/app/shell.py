"""開啟終端與資料夾等外部程式。"""

from __future__ import annotations

import os
import shutil
import subprocess

CREATE_NEW_CONSOLE = 0x00000010


def open_terminal(distro_name: str) -> None:
    if shutil.which("wt.exe"):
        subprocess.Popen(["wt.exe", "wsl.exe", "-d", distro_name])
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
