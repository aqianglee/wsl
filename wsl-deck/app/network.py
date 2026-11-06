"""網路規則：驗證、掃描、portproxy 狀態與套用編排。"""

from __future__ import annotations

import logging
import shlex
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from app.wsl import WslError, get_distro_ip, run_wsl

logger = logging.getLogger(__name__)

Stage = Callable[[str], None]
CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class PortProxyEntry:
    listen_port: int
    connect_address: str
    connect_port: int


@dataclass
class ApplyResult:
    ok: bool
    denied: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


def parse_portproxy(text: str) -> list[PortProxyEntry]:
    entries: list[PortProxyEntry] = []
    for raw in text.splitlines():
        tokens = raw.replace("\x00", "").split()
        if len(tokens) < 4:
            continue
        if not tokens[1].isdigit() or not tokens[3].isdigit():
            continue
        entries.append(PortProxyEntry(int(tokens[1]), tokens[2], int(tokens[3])))
    return entries


def show_portproxy() -> list[PortProxyEntry]:
    try:
        proc = subprocess.run(
            ["netsh", "interface", "portproxy", "show", "v4tov4"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("找不到 netsh") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("讀取 portproxy 逾時") from exc
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "讀取 portproxy 失敗")
    return parse_portproxy(proc.stdout)


def parse_listen_ports(text: str) -> list[int]:
    ports: set[int] = set()
    for raw in text.splitlines():
        line = raw.replace("\x00", "").strip()
        if not line or "LISTEN" not in line.upper():
            continue
        for token in line.split():
            if ":" not in token:
                continue
            tail = token.rsplit(":", 1)[-1]
            if tail.isdigit():
                port = int(tail)
                if 0 < port <= 65535:
                    ports.add(port)
                break
    return sorted(ports)


def scan_tcp_ports(name: str, netns: str | None = None) -> list[int]:
    command = "ss -tln 2>/dev/null || netstat -tln"
    if netns:
        command = f"ip netns exec {shlex.quote(netns)} sh -c {shlex.quote(command)}"
    output = run_wsl(["-d", name, "--", "sh", "-c", command], timeout=120)
    return parse_listen_ports(output)


def firewall_rule_name(distro: str, windows_port: int) -> str:
    return f"WSL Deck {distro} {windows_port}"


def validate_rule(
    rule: dict,
    rules: list[dict],
    ignore_windows_port: int | None = None,
) -> None:
    label = str(rule.get("label", "")).strip()
    if not label:
        raise ValueError("規則標籤不可空白")
    windows_port = rule.get("windows_port")
    distro_port = rule.get("distro_port")
    for key, port in (("Windows 端口", windows_port), ("distro 端口", distro_port)):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"{key}必須是 1-65535")
    for other in rules:
        if other.get("windows_port") == windows_port and windows_port != ignore_windows_port:
            raise ValueError(
                f"Windows 端口 {windows_port} 已被 {other.get('distro', '')} 的規則使用"
            )


def rule_status(
    rule: dict,
    running: bool,
    ip: str,
    entries: list[PortProxyEntry],
) -> str:
    if not rule.get("enabled", True):
        if any(entry.listen_port == rule["windows_port"] for entry in entries):
            return "待套用"
        return "已停用"
    if not running:
        return "待啟動"
    if ip and any(
        entry.listen_port == rule["windows_port"]
        and entry.connect_address == ip
        and entry.connect_port == rule["distro_port"]
        for entry in entries
    ):
        return "已套用"
    return "待套用"


def port_occupied(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return True
    return False


def build_admin_job(
    targets: list[tuple[str, str, list[dict]]],
    cleanup: list[tuple[str, int]] | None = None,
) -> dict:
    delete_ports: set[int] = set()
    firewall_delete: dict[tuple[str, int], dict] = {}
    portproxy_add: list[dict] = []
    firewall_add: list[dict] = []

    for name, ip, rules in targets:
        for rule in rules:
            port = rule["windows_port"]
            delete_ports.add(port)
            firewall_delete[(name, port)] = {
                "distro": name,
                "windows_port": port,
                "name": firewall_rule_name(name, port),
            }
            if rule.get("enabled", True):
                if rule.get("allow_lan", True):
                    firewall_add.append({
                        "distro": name,
                        "windows_port": port,
                        "name": firewall_rule_name(name, port),
                    })
                portproxy_add.append({
                    "windows_port": port,
                    "connect_address": ip,
                    "connect_port": rule["distro_port"],
                })
    for name, port in cleanup or []:
        delete_ports.add(port)
        firewall_delete[(name, port)] = {
            "distro": name,
            "windows_port": port,
            "name": firewall_rule_name(name, port),
        }

    return {
        "portproxy_delete": sorted(delete_ports),
        "portproxy_add": portproxy_add,
        "firewall_delete": list(firewall_delete.values()),
        "firewall_add": firewall_add,
    }


def apply_rules(
    targets: list[tuple[str, list[dict]]],
    cleanup: list[tuple[str, int]] | None = None,
    stage: Stage | None = None,
    ip_resolver: Callable[[str], str] | None = None,
) -> ApplyResult:
    from app.admin import run_admin_job

    resolve_ip = ip_resolver or get_distro_ip
    result = ApplyResult(ok=True)
    resolved: list[tuple[str, str, list[dict]]] = []
    try:
        entries = show_portproxy()
    except RuntimeError as exc:
        return ApplyResult(ok=False, errors=[str(exc)])
    portproxy_ports = {entry.listen_port for entry in entries}

    for name, rules in targets:
        enabled = [rule for rule in rules if rule.get("enabled", True)]
        ip = ""
        if enabled:
            if stage:
                stage(f"正在取得 {name} 的 IP…")
            try:
                ip = resolve_ip(name)
            except WslError as exc:
                result.ok = False
                result.errors.append(f"{name}：取得 IP 失敗（{exc}）")
                continue
            if not ip:
                result.ok = False
                result.errors.append(f"{name}：未取得 IPv4 位址")
                continue
        kept: list[dict] = []
        for rule in rules:
            if not rule.get("enabled", True):
                kept.append(rule)
                continue
            port = rule["windows_port"]
            if port not in portproxy_ports and port_occupied(port):
                warning = f"Windows 端口 {port} 已被其他程式佔用，已略過"
                logger.warning(warning)
                result.warnings.append(warning)
                continue
            kept.append(rule)
        resolved.append((name, ip, kept))

    job = build_admin_job(resolved, cleanup)
    has_work = bool(
        job["portproxy_add"] or job["portproxy_delete"]
        or job["firewall_add"] or job["firewall_delete"]
    )
    if not has_work:
        return result

    if stage:
        stage("等待管理員授權…")
    admin = run_admin_job(job)
    result.ok = result.ok and admin.ok
    result.denied = admin.denied
    result.errors.extend(admin.errors)
    result.warnings.extend(admin.warnings)
    result.commands.extend(admin.commands)
    return result
