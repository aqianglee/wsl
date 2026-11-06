"""C 方案：為單一 instance 建立獨立 network namespace（netns）。

兩種模式：
- temporary：只在 WSL Deck 啟動時於執行期建立，不寫任何永久檔案；
- permanent：寫入 systemd oneshot unit 與服務 drop-in，任何方式啟動都生效。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import shlex
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.wsl import WslError, get_distro_ip, run_wsl

logger = logging.getLogger(__name__)

LIB_DIR = "/usr/local/lib/wsl-deck"
UP_SCRIPT = f"{LIB_DIR}/netns-up.sh"
DOWN_SCRIPT = f"{LIB_DIR}/netns-down.sh"
UNIT_FILE = "/etc/systemd/system/wsl-deck-netns.service"
UNIT_NAME = "wsl-deck-netns.service"
STATE_FILE = "/etc/wsl-deck/network.state"
DROPIN_NAME = "10-wsl-deck-netns.conf"

_SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@:-]+$")
_ARGV_RE = re.compile(r"argv\[\]=(.*?)\s*;", re.S)


@dataclass(frozen=True)
class NetworkConfig:
    """instance 的 C 方案設定。"""

    ip: str
    scope: str
    services: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_raw(cls, raw: Any) -> "NetworkConfig | None":
        if not isinstance(raw, dict) or not raw.get("enabled", False):
            return None
        ip = str(raw.get("ip") or "").strip()
        scope = str(raw.get("scope") or "temporary").strip()
        services = tuple(
            str(item).strip() for item in raw.get("services", []) if str(item).strip()
        )
        if not ip or scope not in ("temporary", "permanent") or not services:
            return None
        return cls(ip=ip, scope=scope, services=services)

    @property
    def permanent(self) -> bool:
        return self.scope == "permanent"

    def state_text(self) -> str:
        return self.ip + "\n" + "\n".join(sorted(self.services)) + "\n"


def _digest(distro: str) -> str:
    return hashlib.sha1(distro.encode("utf-8")).hexdigest()


def instance_id(distro: str) -> str:
    return _digest(distro)[:8]


def netns_name(distro: str) -> str:
    return f"wsl-deck-{instance_id(distro)}"


def host_if(distro: str) -> str:
    return f"vd{instance_id(distro)[:5]}a"


def peer_if(distro: str) -> str:
    return f"vd{instance_id(distro)[:5]}b"


def uplink_ip(distro: str) -> str:
    """veth 主機端位址；用 link-local，避免與使用者指定 IP 衝突。"""
    octet = (int(_digest(distro)[8:10], 16) % 250) + 2
    return f"169.254.{octet}.1"


def uplink_net(distro: str) -> str:
    return f"169.254.{(int(_digest(distro)[8:10], 16) % 250) + 2}.0/24"


def normalize_service(raw: str) -> str:
    name = raw.strip()
    return name if "." in name else f"{name}.service"


def transient_unit(distro: str, unit: str) -> str:
    base = unit.rsplit(".", 1)[0]
    base = re.sub(r"[^A-Za-z0-9_.@-]", "-", base)
    return f"wsl-deck-{instance_id(distro)}-{base}"


def transient_prefix(distro: str) -> str:
    return f"wsl-deck-{instance_id(distro)}-"


def service_from_transient(distro: str, unit: str) -> str:
    """由 transient unit 名稱還原原始 service 名稱。"""
    prefix = transient_prefix(distro)
    if not unit.startswith(prefix):
        return ""
    name = unit[len(prefix):]
    if not name:
        return ""
    return name if "." in name else f"{name}.service"


def is_valid_service_name(raw: str) -> bool:
    return bool(_SERVICE_RE.match(raw.strip()))


def build_up_script(distro: str, ip: str, *, idempotent: bool) -> str:
    ns = netns_name(distro)
    host = host_if(distro)
    peer = peer_if(distro)
    up = uplink_ip(distro)
    net = uplink_net(distro)
    lines = [
        "#!/bin/sh",
        "set -eu",
        f"NS={shlex.quote(ns)}",
        f"HOST_IF={shlex.quote(host)}",
        f"PEER_IF={shlex.quote(peer)}",
        f"IP={shlex.quote(ip)}",
        f"UP={shlex.quote(up)}",
        f"NET={shlex.quote(net)}",
    ]
    if idempotent:
        lines += [
            'if ip netns list 2>/dev/null | grep -qx "$NS"; then exit 0; fi',
        ]
    lines += [
        'ip link del "$HOST_IF" 2>/dev/null || true',
        'ip route del "$IP/32" 2>/dev/null || true',
        'ip netns del "$NS" 2>/dev/null || true',
        'ip netns add "$NS"',
        'ip link add "$HOST_IF" type veth peer name "$PEER_IF"',
        'ip link set "$PEER_IF" netns "$NS"',
        'ip addr add "$UP/24" dev "$HOST_IF"',
        'ip link set "$HOST_IF" up',
        'ip netns exec "$NS" ip link set lo up',
        'ip netns exec "$NS" ip link set "$PEER_IF" up',
        'ip netns exec "$NS" ip addr add "$IP/32" dev "$PEER_IF"',
        'ip netns exec "$NS" ip route add "$NET" dev "$PEER_IF" 2>/dev/null || true',
        'ip netns exec "$NS" ip route add default via "$UP" dev "$PEER_IF" 2>/dev/null || true',
        'ip route add "$IP/32" dev "$HOST_IF" 2>/dev/null || true',
        "sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true",
        "sysctl -w net.ipv4.conf.eth0.proxy_arp=1 >/dev/null 2>&1 || true",
        "sysctl -w net.ipv4.conf.all.proxy_arp=1 >/dev/null 2>&1 || true",
        "sysctl -w net.ipv4.conf.eth0.rp_filter=2 >/dev/null 2>&1 || true",
        "sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null 2>&1 || true",
        "",
    ]
    return "\n".join(lines)


def build_down_script(distro: str, ip: str) -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            f"NS={shlex.quote(netns_name(distro))}",
            f"HOST_IF={shlex.quote(host_if(distro))}",
            f"IP={shlex.quote(ip)}",
            'ip route del "$IP/32" dev "$HOST_IF" 2>/dev/null || true',
            'ip link del "$HOST_IF" 2>/dev/null || true',
            'ip netns del "$NS" 2>/dev/null || true',
            "exit 0",
            "",
        ]
    )


def build_unit(services: Iterable[str]) -> str:
    before = " ".join(normalize_service(item) for item in services)
    lines = [
        "[Unit]",
        "Description=WSL Deck isolated network namespace",
    ]
    if before:
        lines.append(f"Before={before}")
    lines += [
        "",
        "[Service]",
        "Type=oneshot",
        "RemainAfterExit=yes",
        f"ExecStart={UP_SCRIPT}",
        f"ExecStop=-{DOWN_SCRIPT}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]
    return "\n".join(lines)


def build_dropin(distro: str) -> str:
    return "\n".join(
        [
            "[Unit]",
            f"After={UNIT_NAME}",
            "",
            "[Service]",
            f"NetworkNamespacePath=/run/netns/{netns_name(distro)}",
            "",
        ]
    )


def _root(name: str, script: str, timeout: int = 120) -> str:
    # wsl.exe 會把含換行的單一參數壓成空白，改用 base64 傳遞腳本。
    payload = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return run_wsl(
        [
            "-d",
            name,
            "-u",
            "root",
            "--",
            "sh",
            "-c",
            f"echo {payload} | base64 -d | sh",
        ],
        timeout=timeout,
    )


def _write_file(name: str, path: str, content: str, executable: bool = False) -> None:
    quoted = shlex.quote(path)
    payload = base64.b64encode(
        content.replace("\r\n", "\n").encode("utf-8")
    ).decode("ascii")
    script = (
        f"set -eu; mkdir -p \"$(dirname {quoted})\"; "
        f"echo {payload} | base64 -d > {quoted}"
    )
    if executable:
        script += f"; chmod 755 {quoted}"
    _root(name, script, timeout=60)


def _read_root(name: str, path: str) -> str:
    try:
        return _root(name, f"cat {shlex.quote(path)} 2>/dev/null || true", timeout=30)
    except WslError:
        return ""


def netns_exists(name: str) -> bool:
    try:
        output = _root(name, "ip netns list 2>/dev/null || true", timeout=30)
    except WslError:
        return False
    target = netns_name(name)
    return any(line.split()[0].split("(")[0] == target for line in output.splitlines() if line.strip())


def list_netns(name: str) -> list[str]:
    try:
        output = _root(name, "ip netns list 2>/dev/null || true", timeout=30)
    except WslError:
        return []
    return [
        line.split()[0].split("(")[0]
        for line in output.splitlines()
        if line.strip()
    ]


def _systemctl_version(name: str) -> int:
    try:
        output = _root(name, "systemctl --version 2>/dev/null | head -n1", timeout=30)
    except WslError:
        return 0
    match = re.search(r"systemd\s+(\d+)", output)
    return int(match.group(1)) if match else 0


def supports_namespace_path(name: str) -> bool:
    return _systemctl_version(name) >= 249


def _show_property(name: str, unit: str, prop: str) -> str:
    try:
        return _root(
            name,
            f"systemctl show -p {prop} --value {shlex.quote(unit)} 2>/dev/null || true",
            timeout=30,
        ).strip()
    except WslError:
        return ""


def parse_exec_start(text: str) -> list[str]:
    match = _ARGV_RE.search(text)
    if match is None:
        return []
    try:
        return shlex.split(match.group(1), posix=True)
    except ValueError:
        return []


def _exec_start(name: str, unit: str) -> list[str]:
    argv = parse_exec_start(_show_property(name, unit, "ExecStart"))
    if argv:
        return argv
    try:
        text = _root(name, f"systemctl cat {shlex.quote(unit)} 2>/dev/null || true", timeout=30)
    except WslError:
        return []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ExecStart="):
            value = stripped[len("ExecStart="):].lstrip("-@+!")
            try:
                return shlex.split(value, posix=True)
            except ValueError:
                return []
    return []


def _has_permanent(name: str) -> bool:
    try:
        _root(name, f"test -f {shlex.quote(UNIT_FILE)}", timeout=30)
    except WslError:
        return False
    return True


def _stop_units(name: str, services: Iterable[str]) -> None:
    units = " ".join(shlex.quote(normalize_service(item)) for item in services)
    if not units:
        return
    try:
        _root(name, f"systemctl stop {units} 2>/dev/null || true", timeout=120)
    except WslError:
        logger.warning("停止 %s 的服務失敗", name)


def _start_units(name: str, services: Iterable[str]) -> None:
    for item in services:
        unit = normalize_service(item)
        try:
            _root(name, f"systemctl start {shlex.quote(unit)} 2>/dev/null || true", timeout=120)
        except WslError:
            logger.warning("重新啟動 %s 的 %s 失敗", name, unit)


def _stop_transient(name: str, services: Iterable[str]) -> None:
    for item in services:
        unit = transient_unit(name, normalize_service(item))
        try:
            _root(
                name,
                f"systemctl stop {shlex.quote(unit)} 2>/dev/null || true; "
                f"systemctl reset-failed {shlex.quote(unit)} 2>/dev/null || true",
                timeout=60,
            )
        except WslError:
            logger.warning("停止 transient unit %s 失敗", unit)


def _transient_units(name: str) -> list[str]:
    prefix = transient_prefix(name)
    try:
        output = _root(
            name,
            "systemctl list-units --no-legend --plain --type=service "
            f"{shlex.quote(prefix + '*')} 2>/dev/null || true",
            timeout=60,
        )
    except WslError:
        return []
    units = []
    for line in output.splitlines():
        token = line.split()[0] if line.strip() else ""
        if token.startswith(prefix) and token.endswith(".service"):
            units.append(token)
    return units


def _restore_shared_network(name: str) -> None:
    """把臨時 netns 內的服務搬回共用網路（設定被關閉時使用）。"""
    units = _transient_units(name)
    services = [service_from_transient(name, unit) for unit in units]
    _stop_transient_units(name, units)
    _remove_namespace(name, "")
    _start_units(name, [service for service in services if service])


def _stop_transient_units(name: str, units: Iterable[str]) -> None:
    for unit in units:
        try:
            _root(
                name,
                f"systemctl stop {shlex.quote(unit)} 2>/dev/null || true; "
                f"systemctl reset-failed {shlex.quote(unit)} 2>/dev/null || true",
                timeout=60,
            )
        except WslError:
            logger.warning("停止 transient unit %s 失敗", unit)


def _remove_namespace(name: str, ip: str) -> None:
    script = "\n".join(
        [
            "set +e",
            f"NS={shlex.quote(netns_name(name))}",
            f"HOST_IF={shlex.quote(host_if(name))}",
            f"IP={shlex.quote(ip)}",
            'ip route del "$IP/32" dev "$HOST_IF" 2>/dev/null',
            'ip link del "$HOST_IF" 2>/dev/null',
            'ip netns del "$NS" 2>/dev/null',
            "exit 0",
        ]
    )
    _root(name, script, timeout=60)


def _prepare_runtime_dirs(name: str, unit: str) -> None:
    """systemd-run 不繼承 RuntimeDirectory，手動補上（例如 /run/mysqld）。"""
    directories = _show_property(name, unit, "RuntimeDirectory").split()
    if not directories:
        return
    user = _show_property(name, unit, "User") or "root"
    group = _show_property(name, unit, "Group") or user
    installs = " ".join(
        f"install -d -o {shlex.quote(user)} -g {shlex.quote(group)} -m 755 "
        f"{shlex.quote('/run/' + directory)}"
        for directory in directories
    )
    try:
        _root(name, f"set -e; {installs}", timeout=30)
    except WslError:
        logger.warning("建立 %s 的 RuntimeDirectory 失敗", unit)


def apply_temporary(name: str, cfg: NetworkConfig) -> list[str]:
    """建立 netns 並把服務搬進去；回傳警告（不拋錯以外的失敗會上拋）。"""
    warnings: list[str] = []
    _stop_transient(name, cfg.services)
    _stop_transient_units(name, _transient_units(name))
    _stop_units(name, cfg.services)
    _remove_namespace(name, cfg.ip)
    try:
        _root(name, build_up_script(name, cfg.ip, idempotent=False), timeout=180)
    except WslError as exc:
        raise WslError(f"建立 netns 失敗：{exc}") from exc

    ns = netns_name(name)
    ns_path = f"/run/netns/{ns}"
    for item in cfg.services:
        unit = normalize_service(item)
        argv = _exec_start(name, unit)
        if not argv:
            warnings.append(f"無法取得 {unit} 的啟動命令，未搬入 netns")
            continue
        transient = transient_unit(name, unit)
        _prepare_runtime_dirs(name, unit)
        command = " ".join(shlex.quote(arg) for arg in argv)
        props = [f"--property=NetworkNamespacePath={ns_path}"]
        user = _show_property(name, unit, "User")
        if user and user != "root":
            props.append(f"--property=User={user}")
        group = _show_property(name, unit, "Group")
        if group and group != "root":
            props.append(f"--property=Group={group}")
        script = (
            f"systemd-run --unit={shlex.quote(transient)} --collect "
            f"{' '.join(props)} -- sh -c {shlex.quote(command)}"
        )
        try:
            _root(name, script, timeout=120)
        except WslError as exc:
            warnings.append(f"啟動 {unit} 於 netns 失敗：{exc}")
            continue
        state = _root(
            name,
            f"sleep 6; systemctl is-active {shlex.quote(transient)} 2>/dev/null || true",
            timeout=60,
        ).strip()
        if state and state != "active":
            warnings.append(f"{unit} 在 netns 內的狀態為 {state}")
    return warnings


def cleanup_temporary(
    name: str, services: Iterable[str], ip: str, restart: bool = True
) -> list[str]:
    warnings: list[str] = []
    _stop_transient(name, services)
    _stop_transient_units(name, _transient_units(name))
    try:
        _remove_namespace(name, ip)
    except WslError as exc:
        warnings.append(f"清理 netns 失敗：{exc}")
    if restart:
        _start_units(name, services)
    return warnings


def _install_permanent(name: str, cfg: NetworkConfig) -> list[str]:
    warnings: list[str] = []
    if not supports_namespace_path(name):
        raise WslError(
            "此 instance 的 systemd 版本不支援 NetworkNamespacePath（需 249 以上）"
        )
    units = [normalize_service(item) for item in cfg.services]
    _stop_transient(name, cfg.services)
    try:
        _root(name, f"systemctl stop {shlex.quote(UNIT_NAME)} 2>/dev/null || true", timeout=120)
    except WslError:
        pass
    _stop_units(name, cfg.services)

    _write_file(name, UP_SCRIPT, build_up_script(name, cfg.ip, idempotent=True), executable=True)
    _write_file(name, DOWN_SCRIPT, build_down_script(name, cfg.ip), executable=True)
    _write_file(name, UNIT_FILE, build_unit(cfg.services))
    dropin = build_dropin(name)
    for unit in units:
        path = f"/etc/systemd/system/{unit}.d/{DROPIN_NAME}"
        _write_file(name, path, dropin)

    _root(name, "systemctl daemon-reload", timeout=120)
    # 舊的臨時 netns 可能用了不同的 IP；先清掉讓 unit 重建。
    _remove_namespace(name, cfg.ip)
    _root(
        name,
        f"systemctl enable {shlex.quote(UNIT_NAME)} >/dev/null 2>&1 || true; "
        f"systemctl start {shlex.quote(UNIT_NAME)}",
        timeout=120,
    )
    _stop_transient(name, cfg.services)
    _start_units(name, cfg.services)
    _write_file(name, STATE_FILE, cfg.state_text())
    if not netns_exists(name):
        warnings.append("netns 未建立成功，服務可能仍在共用網路")
    time.sleep(3)
    for unit in units:
        state = _show_property(name, unit, "ActiveState")
        if state and state not in ("active", "activating"):
            warnings.append(f"{unit} 未啟動（狀態 {state}）")
    return warnings


def _uninstall_permanent(name: str) -> list[str]:
    warnings: list[str] = []
    script = "\n".join(
        [
            "set +e",
            f"systemctl disable {shlex.quote(UNIT_NAME)} >/dev/null 2>&1",
            'UNITS=""',
            "for f in /etc/systemd/system/*.service.d/10-wsl-deck-netns.conf; do",
            '  [ -e "$f" ] || continue',
            '  u=$(basename "$(dirname "$f")" .d)',
            '  UNITS="$UNITS $u"',
            '  systemctl stop "$u" 2>/dev/null',
            '  rm -f "$f"',
            '  rmdir "$(dirname "$f")" 2>/dev/null',
            "done",
            # 先等所有 stop job 收斂，避免後續 start 被殘留的 stop job 取消
            "sleep 1",
            f"systemctl stop {shlex.quote(UNIT_NAME)} >/dev/null 2>&1",
            "sleep 1",
            f"rm -f {shlex.quote(UNIT_FILE)} {shlex.quote(UP_SCRIPT)} "
            f"{shlex.quote(DOWN_SCRIPT)} {shlex.quote(STATE_FILE)}",
            "rmdir /etc/wsl-deck 2>/dev/null",
            "systemctl reset-failed wsl-deck-netns.service 2>/dev/null",
            "systemctl daemon-reload",
            'for u in $UNITS; do systemctl start "$u" 2>/dev/null; done',
            # 等殘留的 stop job 收斂後再確認一次
            "sleep 3",
            'for u in $UNITS; do systemctl is-active --quiet "$u" || systemctl start "$u" 2>/dev/null; done',
            "exit 0",
        ]
    )
    try:
        _root(name, script, timeout=180)
    except WslError as exc:
        warnings.append(f"停用永久模式時發生錯誤：{exc}")
    return warnings


def ensure_after_start(name: str, raw: Any, *, force: bool = False) -> list[str]:
    """instance 啟動後同步 C 設定；回傳警告，失敗時盡量回退到 A。"""
    cfg = NetworkConfig.from_raw(raw)
    try:
        if cfg is None:
            if _has_permanent(name):
                return _uninstall_permanent(name)
            if netns_exists(name):
                _restore_shared_network(name)
            return []
        if cfg.permanent:
            state = _read_root(name, STATE_FILE).strip()
            if not force and state == cfg.state_text().strip() and _has_permanent(name):
                return []
            return _install_permanent(name, cfg)
        if _has_permanent(name):
            _uninstall_permanent(name)
        return apply_temporary(name, cfg)
    except WslError as exc:
        logger.warning("%s 套用 C 方案失敗：%s", name, exc)
        if cfg is not None:
            try:
                cleanup_temporary(name, cfg.services, cfg.ip, restart=True)
            except WslError:
                logger.warning("%s 回退清理失敗", name)
        return [f"C 方案套用失敗，已退回共用網路（A）：{exc}"]


def effective_ip(name: str, raw: Any) -> str:
    """服務對外位址：C 生效時用設定 IP，否則用 distro 主 IP。"""
    cfg = NetworkConfig.from_raw(raw)
    if cfg is not None and netns_exists(name):
        return cfg.ip
    return get_distro_ip(name)


def cleanup_all(config_data: dict[str, Any], restart: bool = True) -> None:
    """App 結束時把所有臨時 netns 還原（永久模式不動）。"""
    networks = config_data.get("instance_networks", {})
    if not isinstance(networks, dict):
        return
    for distro, raw in networks.items():
        cfg = NetworkConfig.from_raw(raw)
        if cfg is None or cfg.permanent:
            continue
        try:
            if netns_exists(distro):
                cleanup_temporary(distro, cfg.services, cfg.ip, restart=restart)
                logger.info("已還原 %s 的臨時 netns", distro)
        except WslError as exc:
            logger.warning("還原 %s 的臨時 netns 失敗：%s", distro, exc)
