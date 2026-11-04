"""開機自啟：只支援打包後的 exe，避免指向會搬動的 .venv。"""

from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "WSL Deck"


def build_run_command(exe: str) -> str:
    return f'"{exe}" --silent'


def is_supported() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return str(value).strip() == build_run_command(sys.executable)


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        raise RuntimeError("開發模式不支援開機自啟，請使用打包後的 exe")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(
                key, VALUE_NAME, 0, winreg.REG_SZ,
                build_run_command(sys.executable),
            )
            return
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
