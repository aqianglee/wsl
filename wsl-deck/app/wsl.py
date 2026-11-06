"""WSL instance 資料層：註冊表 + wsl.exe 輸出。"""

from __future__ import annotations

import logging
import os
import subprocess
import winreg
from dataclasses import dataclass, replace
from pathlib import Path

from app.proxy import current_proxy, proxy_url

logger = logging.getLogger(__name__)

LXSS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
NO_PROXY_VALUE = "localhost,127.0.0.1,::1"


class WslError(Exception):
    """wsl.exe 執行失敗。"""


@dataclass(frozen=True)
class Distro:
    name: str
    state: str
    version: int
    is_default: bool
    guid: str
    base_path: str
    vhdx_path: str
    vhdx_size: int
    ip: str = ""

    @property
    def size_gb(self) -> float:
        return self.vhdx_size / 1024 ** 3

    @property
    def running(self) -> bool:
        if "running" in self.state.lower():
            return True
        return any(word in self.state for word in ("运行中", "執行中", "运行", "執行"))


def _clean_output(text: str | None) -> str:
    return (text or "").replace("\x00", "").strip()


def _with_proxy(args: list[str]) -> list[str]:
    """對 `wsl -d <name> -- <cmd>` 形式注入 SOCKS5 環境變數。"""
    config = current_proxy()
    if config is None or "--" not in args:
        return args
    index = args.index("--")
    url = proxy_url(config)
    overrides = [
        f"ALL_PROXY={url}",
        f"all_proxy={url}",
        f"HTTP_PROXY={url}",
        f"http_proxy={url}",
        f"HTTPS_PROXY={url}",
        f"https_proxy={url}",
        f"NO_PROXY={NO_PROXY_VALUE}",
        f"no_proxy={NO_PROXY_VALUE}",
    ]
    return [*args[: index + 1], "env", *overrides, *args[index + 1:]]


def run_wsl_process(
    args: list[str],
    timeout: int = 60,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    """執行 wsl.exe 並回傳（退出碼, stdout, stderr）；非零退出碼不拋錯。"""
    args = _with_proxy(list(args))
    env = os.environ.copy()
    env["WSL_UTF8"] = "1"
    try:
        proc = subprocess.run(
            ["wsl.exe", *args],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise WslError("找不到 wsl.exe，請確認已啟用 WSL") from exc
    except subprocess.TimeoutExpired as exc:
        raise WslError(f"wsl.exe 逾時（{timeout} 秒）") from exc
    return proc.returncode, _clean_output(proc.stdout), _clean_output(proc.stderr)


def run_wsl(args: list[str], timeout: int = 60, stdin_text: str | None = None) -> str:
    code, stdout, stderr = run_wsl_process(args, timeout=timeout, stdin_text=stdin_text)
    if code != 0:
        message = stderr or stdout or f"wsl.exe 退出碼 {code}"
        raise WslError(message)
    return stdout


def parse_list_output(text: str) -> list[tuple[str, str, int, bool]]:
    """解析 wsl.exe --list --verbose 的輸出。"""
    rows: list[tuple[str, str, int, bool]] = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\x00", "").strip()
        if not line:
            continue
        is_default = line.startswith("*")
        if is_default:
            line = line[1:].strip()
        tokens = line.split()
        if len(tokens) < 3 or not tokens[-1].isdigit():
            continue
        rows.append((tokens[0], " ".join(tokens[1:-1]), int(tokens[-1]), is_default))
    return rows


def _normalize_path(path: str) -> str:
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _read_registry() -> tuple[dict[str, dict], str]:
    """回傳（名稱 -> 註冊表資訊, 預設 distro 的 GUID）。"""
    entries: dict[str, dict] = {}
    default_guid = ""
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, LXSS_KEY)
    except FileNotFoundError:
        logger.info("找不到 WSL 註冊表，視為尚未安裝任何 distro")
        return entries, default_guid

    with root:
        try:
            default_guid = str(winreg.QueryValueEx(root, "DefaultDistribution")[0])
        except FileNotFoundError:
            pass

        index = 0
        while True:
            try:
                guid = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(root, guid) as key:
                    name = _query_value(key, "DistributionName")
                    if not name:
                        continue
                    base_path = _normalize_path(_query_value(key, "BasePath") or "")
                    version = _query_value(key, "Version", 2)
                    entries[str(name)] = {
                        "guid": guid,
                        "base_path": base_path,
                        "version": int(version or 2),
                    }
            except OSError:
                logger.warning("讀取註冊表項目失敗：%s", guid)
    return entries, default_guid


def _query_value(key: winreg.HKEYType, name: str, default: object = None) -> object:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return default


def _locate_vhdx(base_path: str) -> tuple[str, int]:
    if not base_path:
        return "", 0
    folder = Path(base_path)
    try:
        candidates = sorted(folder.glob("*.vhdx"))
    except OSError:
        candidates = []
    vhdx = candidates[0] if candidates else folder / "ext4.vhdx"
    try:
        size = vhdx.stat().st_size
    except OSError:
        size = 0
    return str(vhdx), size


def list_distros() -> list[Distro]:
    """以註冊表為主、CLI 狀態為輔，回傳所有 distro。"""
    registry, default_guid = _read_registry()
    cli_rows = parse_list_output(run_wsl(["--list", "--verbose"]))

    result: list[Distro] = []
    seen: set[str] = set()
    for name, state, cli_version, cli_default in cli_rows:
        info = registry.get(name, {})
        base_path = str(info.get("base_path", ""))
        vhdx_path, vhdx_size = _locate_vhdx(base_path)
        guid = str(info.get("guid", ""))
        result.append(
            Distro(
                name=name,
                state=state,
                version=int(info.get("version") or cli_version),
                is_default=cli_default or guid == default_guid,
                guid=guid,
                base_path=base_path,
                vhdx_path=vhdx_path,
                vhdx_size=vhdx_size,
            )
        )
        seen.add(name)

    for name, info in registry.items():
        if name in seen:
            continue
        base_path = str(info.get("base_path", ""))
        vhdx_path, vhdx_size = _locate_vhdx(base_path)
        guid = str(info.get("guid", ""))
        result.append(
            Distro(
                name=name,
                state="Unknown",
                version=int(info.get("version") or 2),
                is_default=guid == default_guid,
                guid=guid,
                base_path=base_path,
                vhdx_path=vhdx_path,
                vhdx_size=vhdx_size,
            )
        )

    result.sort(key=lambda distro: (not distro.is_default, distro.name.lower()))
    return result


SYSTEM_DEFAULT_PREFIXES = ("docker-desktop",)


def is_system_distro(name: str, extra_prefixes: list[str] | None = None) -> bool:
    prefixes = list(SYSTEM_DEFAULT_PREFIXES) + list(extra_prefixes or [])
    return any(name == prefix or name.startswith(prefix + "-") for prefix in prefixes)


def first_ipv4(text: str) -> str:
    for token in text.split():
        parts = token.split(".")
        if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            if not token.startswith("127."):
                return token
    return ""


def start_distro(name: str) -> None:
    run_wsl(["-d", name, "--", "true"], timeout=180)


def terminate_distro(name: str) -> None:
    run_wsl(["--terminate", name], timeout=60)


def shutdown_all() -> None:
    run_wsl(["--shutdown"], timeout=120)


def set_default_distro(name: str) -> None:
    run_wsl(["--set-default", name], timeout=60)


def get_distro_ip(name: str) -> str:
    return first_ipv4(run_wsl(["-d", name, "--", "hostname", "-I"], timeout=60))
