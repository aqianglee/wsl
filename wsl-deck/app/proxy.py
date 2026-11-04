"""SOCKS5 代理：App 全域環境變數、主機偵測與連線測試。"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PROXY_ENV_KEYS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
)
NO_PROXY_VALUE = "localhost,127.0.0.1,::1"
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool
    host: str
    port: int


_previous_env: dict[str, str | None] = {}
_applied = False
_current: ProxyConfig | None = None


def parse_config(data) -> ProxyConfig:
    if not isinstance(data, dict):
        return ProxyConfig(False, "127.0.0.1", 7890)
    host = str(data.get("host", "") or "").strip() or "127.0.0.1"
    port = data.get("port", 0)
    if not isinstance(port, int) or isinstance(port, bool):
        port = 0
    return ProxyConfig(bool(data.get("enabled", False)), host, port)


def proxy_url(config: ProxyConfig) -> str:
    return f"socks5h://{config.host}:{config.port}"


def current_proxy() -> ProxyConfig | None:
    return _current if _current is not None and _current.enabled else None


def apply_runtime(config: ProxyConfig) -> None:
    """把全域代理寫入目前程序環境；停用時還原先前值。"""
    global _previous_env, _applied, _current
    if not config.enabled or not config.host or not 1 <= config.port <= 65535:
        _restore()
        return

    if not _applied:
        _previous_env = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
        _applied = True
    _current = config

    url = proxy_url(config)
    for key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        os.environ[key] = url
    os.environ["NO_PROXY"] = NO_PROXY_VALUE
    os.environ["no_proxy"] = NO_PROXY_VALUE
    logger.info("已套用 SOCKS5 代理：%s", url)


def _restore() -> None:
    global _previous_env, _applied, _current
    if not _applied:
        _current = None
        return
    for key, value in _previous_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    _previous_env = {}
    _applied = False
    _current = None


def detect_wsl_host_ip() -> str:
    """Windows 端 WSL 虛擬網卡位址；失敗回傳空字串。"""
    command = (
        "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InterfaceAlias -like '*WSL*' } | "
        "Select-Object -First 1 -ExpandProperty IPAddress"
    )
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()


def test_connection(config: ProxyConfig) -> tuple[bool, str]:
    host = config.host.strip()
    if not host:
        return False, "代理主機不可空白"
    if not 1 <= config.port <= 65535:
        return False, "代理埠必須是 1-65535"
    args = [
        "curl.exe",
        "--socks5-hostname",
        f"{host}:{config.port}",
        "-I",
        "-L",
        "--max-time",
        "10",
        "https://github.com",
    ]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return False, "找不到 curl.exe，無法測試連線"
    except subprocess.TimeoutExpired:
        return False, "連線測試逾時"
    if proc.returncode == 0:
        return True, "連線成功"
    lines = (proc.stderr or proc.stdout or "").strip().splitlines()
    return False, lines[-1] if lines else f"curl 退出碼 {proc.returncode}"
