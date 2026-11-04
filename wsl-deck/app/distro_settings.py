"""Instance 設定：`/etc/wsl.conf` 讀寫、使用者校驗與 VHD 維護。"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass

from app.proxy import detect_wsl_host_ip
from app.wsl import WslError, run_wsl

logger = logging.getLogger(__name__)

CONF_PATH = "/etc/wsl.conf"
CONF_TEMP = "/etc/wsl.conf.wsl-deck.tmp"
CONF_BACKUP = "/etc/wsl.conf.wsl-deck.bak"
WRITE_SCRIPT = (
    f"cp -n {CONF_PATH} {CONF_BACKUP} 2>/dev/null; "
    f"cat > {CONF_TEMP} && chmod 644 {CONF_TEMP} && mv {CONF_TEMP} {CONF_PATH}"
)

PROXY_PATH = "/etc/profile.d/99-wsl-deck-proxy.sh"
PROXY_TEMP = "/etc/profile.d/99-wsl-deck-proxy.sh.tmp"

_SECTION_RE = re.compile(r"^\s*\[\s*(.*?)\s*\]\s*$")
_ITEM_RE = re.compile(r"^(\s*)([^=;#]+?)\s*=\s*(.*)$")


@dataclass(frozen=True)
class InstanceSettings:
    default_user: str
    systemd: bool
    append_windows_path: bool
    automount: bool
    proxy_enabled: bool = False
    proxy_host: str = ""
    proxy_port: int = 0


def parse_conf(text: str) -> dict[str, dict[str, str]]:
    """把 wsl.conf 解析成 section -> key -> value（皆為小寫）。"""
    result: dict[str, dict[str, str]] = {}
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        header = _SECTION_RE.match(line)
        if header is not None:
            section = header.group(1).strip().lower()
            result.setdefault(section, {})
            continue
        item = _ITEM_RE.match(line)
        if item is None:
            continue
        result.setdefault(section, {})[item.group(2).strip().lower()] = (
            item.group(3).strip()
        )
    return result


def conf_value(
    conf: dict[str, dict[str, str]], section: str, key: str, default: str
) -> str:
    return conf.get(section, {}).get(key, default)


def conf_bool(
    conf: dict[str, dict[str, str]], section: str, key: str, default: bool
) -> bool:
    raw = conf_value(conf, section, key, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _set_one(text: str, section: str, key: str, value: str) -> str:
    """在保留註解與未知鍵的前提下，設定單一 section/key。"""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()

    wanted_section = section.strip().lower()
    wanted_key = key.strip().lower()

    header_index = -1
    for index, line in enumerate(lines):
        header = _SECTION_RE.match(line)
        if header is not None and header.group(1).strip().lower() == wanted_section:
            header_index = index
            break

    if header_index < 0:
        if lines:
            lines.append("")
        lines.extend([f"[{section}]", f"{key}={value}"])
    else:
        end = len(lines)
        for index in range(header_index + 1, len(lines)):
            if _SECTION_RE.match(lines[index]) is not None:
                end = index
                break
        replaced = False
        for index in range(header_index + 1, end):
            item = _ITEM_RE.match(lines[index])
            if item is not None and item.group(2).strip().lower() == wanted_key:
                lines[index] = f"{item.group(1)}{key}={value}"
                replaced = True
        if not replaced:
            insert_at = header_index + 1
            for index in range(header_index + 1, end):
                if lines[index].strip():
                    insert_at = index + 1
            lines.insert(insert_at, f"{key}={value}")

    return newline.join(lines) + newline


def set_conf_values(text: str, updates: dict[tuple[str, str], str]) -> str:
    """依序套用多個 section/key 更新；輸出可直接寫回檔案。"""
    result = text
    for (section, key), value in updates.items():
        result = _set_one(result, section, key, str(value))
    return result


def build_proxy_script(host: str, port: int) -> str:
    url = f"socks5h://{host}:{port}"
    return (
        "# Managed by WSL Deck. Do not edit.\n"
        f'export ALL_PROXY="{url}"\n'
        'export all_proxy="$ALL_PROXY"\n'
        'export HTTP_PROXY="$ALL_PROXY"\n'
        'export http_proxy="$ALL_PROXY"\n'
        'export HTTPS_PROXY="$ALL_PROXY"\n'
        'export https_proxy="$ALL_PROXY"\n'
        'export NO_PROXY="localhost,127.0.0.1,::1"\n'
        'export no_proxy="$NO_PROXY"\n'
    )


def parse_proxy_script(text: str) -> tuple[bool, str, int]:
    match = re.search(r"socks5h://([A-Za-z0-9._:-]+):(\d+)", text)
    if match is None:
        return False, "", 0
    return True, match.group(1), int(match.group(2))


def read_proxy(name: str) -> tuple[bool, str, int]:
    text = run_wsl(
        [
            "-d",
            name,
            "-u",
            "root",
            "--",
            "sh",
            "-c",
            f"cat {PROXY_PATH} 2>/dev/null || true",
        ],
        timeout=30,
    )
    return parse_proxy_script(text)


def write_proxy(name: str, enabled: bool, host: str, port: int) -> None:
    if not enabled:
        run_wsl(
            [
                "-d",
                name,
                "-u",
                "root",
                "--",
                "sh",
                "-c",
                f"rm -f {PROXY_PATH}; test ! -f {PROXY_PATH}",
            ],
            timeout=30,
        )
        logger.info("已移除 %s 的代理腳本", name)
        return
    run_wsl(
        [
            "-d",
            name,
            "-u",
            "root",
            "--",
            "sh",
            "-c",
            f"mkdir -p /etc/profile.d; cat > {PROXY_TEMP} "
            f"&& chmod 644 {PROXY_TEMP} && mv {PROXY_TEMP} {PROXY_PATH}",
        ],
        timeout=60,
        stdin_text=build_proxy_script(host, port),
    )


def detect_instance_host_ip(name: str) -> str:
    try:
        output = run_wsl(
            ["-d", name, "--", "sh", "-c", "ip route show default"], timeout=30
        )
    except WslError:
        return detect_wsl_host_ip()
    tokens = output.split()
    if "via" in tokens:
        index = tokens.index("via")
        if index + 1 < len(tokens):
            return tokens[index + 1]
    return detect_wsl_host_ip()


def read_settings(name: str) -> InstanceSettings:
    """讀取執行中 instance 的常用設定。"""
    text = run_wsl(
        [
            "-d",
            name,
            "-u",
            "root",
            "--",
            "sh",
            "-c",
            f"cat {CONF_PATH} 2>/dev/null || true",
        ],
        timeout=30,
    )
    conf = parse_conf(text)
    user = conf_value(conf, "user", "default", "")
    if not user:
        user = run_wsl(["-d", name, "--", "whoami"], timeout=30).strip()
    proxy_enabled, proxy_host, proxy_port = read_proxy(name)
    return InstanceSettings(
        default_user=user,
        systemd=conf_bool(conf, "boot", "systemd", False),
        append_windows_path=conf_bool(conf, "interop", "appendwindowspath", True),
        automount=conf_bool(conf, "automount", "enabled", True),
        proxy_enabled=proxy_enabled,
        proxy_host=proxy_host,
        proxy_port=proxy_port,
    )


def user_exists(name: str, user: str) -> bool:
    """確認使用者存在於 distro 內（含 root）。"""
    user = user.strip()
    if not user:
        return False
    try:
        run_wsl(["-d", name, "-u", "root", "--", "id", "-u", user], timeout=30)
    except WslError:
        return False
    return True


def apply_settings(
    name: str, version: int, settings: InstanceSettings
) -> None:
    """寫入 wsl.conf；需 instance 執行中。"""
    user = settings.default_user.strip()
    if not user:
        raise WslError("使用者名稱不可空白")
    if not user_exists(name, user):
        raise WslError(f"instance 內找不到使用者 {user}")
    if settings.proxy_enabled:
        proxy_host = settings.proxy_host.strip()
        if not proxy_host:
            raise WslError("代理主機不可空白")
        if not re.match(r"^[A-Za-z0-9._:-]+$", proxy_host):
            raise WslError("代理主機包含不合法字元")
        if not 1 <= settings.proxy_port <= 65535:
            raise WslError("代理埠必須是 1-65535")

    updates: dict[tuple[str, str], str] = {
        ("user", "default"): user,
        ("interop", "appendWindowsPath"): (
            "true" if settings.append_windows_path else "false"
        ),
        ("automount", "enabled"): "true" if settings.automount else "false",
    }
    if version >= 2:
        updates[("boot", "systemd")] = "true" if settings.systemd else "false"

    current = run_wsl(
        [
            "-d",
            name,
            "-u",
            "root",
            "--",
            "sh",
            "-c",
            f"cat {CONF_PATH} 2>/dev/null || true",
        ],
        timeout=30,
    )
    new_text = set_conf_values(current, updates)
    run_wsl(
        ["-d", name, "-u", "root", "--", "sh", "-c", WRITE_SCRIPT],
        timeout=60,
        stdin_text=new_text,
    )

    written = parse_conf(
        run_wsl(
            [
                "-d",
                name,
                "-u",
                "root",
                "--",
                "sh",
                "-c",
                f"cat {CONF_PATH} 2>/dev/null || true",
            ],
            timeout=30,
        )
    )
    for (section, key), value in updates.items():
        if conf_value(written, section.lower(), key.lower(), "") != value:
            raise WslError(f"設定寫入後驗證失敗：{section}/{key}")

    write_proxy(
        name,
        settings.proxy_enabled,
        settings.proxy_host.strip(),
        settings.proxy_port,
    )
    if settings.proxy_enabled:
        enabled, host, port = read_proxy(name)
        if not enabled or host != settings.proxy_host.strip() or port != settings.proxy_port:
            raise WslError("代理設定寫入後驗證失敗")

    logger.info("已寫入 %s 的設定：%s", name, ", ".join(
        f"{section}/{key}" for section, key in updates
    ))


def is_sparse(vhdx_path: str) -> bool | None:
    """以 fsutil 判斷 VHDX 是否為稀疏檔；無法判斷時回傳 None。"""
    if not vhdx_path:
        return None
    try:
        proc = subprocess.run(
            ["fsutil", "sparse", "queryflag", vhdx_path],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (proc.stdout or "").strip().lower()
    if proc.returncode != 0 or not output:
        return None
    if "not set as sparse" in output or "未设置" in output or "不是稀疏" in output:
        return False
    if "set as sparse" in output or "已设置" in output or "是稀疏" in output:
        return True
    return None


def set_sparse(name: str, enabled: bool) -> None:
    run_wsl(
        ["--manage", name, "--set-sparse", "true" if enabled else "false"],
        timeout=600,
    )


def _file_size(path: str) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def compact_vhd(name: str, vhdx_path: str) -> int:
    """壓縮 VHD 並回傳回收的位元組數。"""
    before = _file_size(vhdx_path)
    run_wsl(["--manage", name, "--compact"], timeout=600)
    after = _file_size(vhdx_path)
    return max(0, before - after)


def set_version(name: str, version: int) -> None:
    run_wsl(["--set-version", name, str(version)], timeout=600)
