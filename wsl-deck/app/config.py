"""配置檔載入、驗證與命令模板解析。"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

from app.workspace import (
    SUBDIR_BACKUPS,
    SUBDIR_INSTANCES,
    SUBDIR_SNAPSHOTS,
    WorkspacePaths,
    workspace_paths,
)

COMMAND_KEYS = (
    "list",
    "start",
    "terminate",
    "shutdown",
    "set_default",
    "unregister",
    "export_tar",
    "export_vhd",
    "import_tar",
    "import_vhd",
    "distro_ip",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "workspace_root": r"D:\VirtualMachiles\wsl",
    "snapshot_keep": {"last": 10, "daily": 7, "weekly": 4, "monthly": 6},
    "advanced_mode": False,
    "confirm_destructive": True,
    "close_to_tray": True,
    "autostart": False,
    "poll_interval": 10,
    "theme": "system",
    "view_mode": "card",
    "proxy": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 7890,
    },
    "log_file": "logs/wsl-deck.log",
    "system_instances": ["docker-desktop", "docker-desktop-data"],
    "commands": {
        "list": "wsl.exe --list --verbose",
        "start": 'wsl.exe -d "{name}" -- true',
        "terminate": 'wsl.exe --terminate "{name}"',
        "shutdown": "wsl.exe --shutdown",
        "set_default": 'wsl.exe --set-default "{name}"',
        "unregister": 'wsl.exe --unregister "{name}"',
        "export_tar": 'wsl.exe --export "{name}" "{file}"',
        "export_vhd": 'wsl.exe --export "{name}" "{file}" --format vhd',
        "import_tar": 'wsl.exe --import "{name}" "{install_dir}" "{file}" --version {version}',
        "import_vhd": 'wsl.exe --import "{name}" "{install_dir}" "{file}" --version {version} --vhd',
        "distro_ip": 'wsl.exe -d "{name}" -- hostname -I',
    },
    "port_forwards": [],
    "instance_networks": {},
}

NETWORK_SCOPES = ("temporary", "permanent")
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+$")

LEGACY_KEYS = {
    "preview_commands": "advanced_mode",
    "minimize_to_tray": "close_to_tray",
}
MIGRATION_BACKUP_SUFFIX = ".pre-m5.bak"


class ConfigError(Exception):
    """配置檔內容不合法。"""


def split_command(text: str) -> list[str]:
    """把 Windows 風格命令字串拆成參數列表，並去掉外層引號。"""
    if not text.strip():
        raise ConfigError("命令模板為空")
    tokens = shlex.split(text, posix=False)
    cleaned: list[str] = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
            token = token[1:-1]
        cleaned.append(token)
    return cleaned


class Config:
    """單一 config.json 的讀寫入口。"""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = json.loads(json.dumps(DEFAULT_CONFIG))
            self._migrate()
            self.save()
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置檔格式錯誤：{exc}") from exc
        if self._migrate():
            backup = self.path.with_name(self.path.name + MIGRATION_BACKUP_SUFFIX)
            if not backup.exists():
                shutil.copy2(self.path, backup)
            self.save()
        else:
            self._validate()

    def _workspace_root(self) -> str:
        """取得工作目錄：優先既有值，其次由 backup_root／distro_root 推導。"""
        workspace = str(self.data.get("workspace_root") or "").strip()
        if workspace:
            return workspace
        backup = str(self.data.get("backup_root") or "").strip()
        if backup:
            candidate = Path(backup)
            if (
                candidate.is_absolute()
                and candidate.name.lower() == SUBDIR_BACKUPS
                and candidate.parent != candidate
            ):
                return str(candidate.parent)
        return str(self.data.get("distro_root") or "").strip() or DEFAULT_CONFIG["workspace_root"]

    def _migrate(self) -> bool:
        """補齊預設鍵、舊鍵替換與工作目錄衍生鍵；回傳是否有變更。"""
        changed = False
        for old, new in LEGACY_KEYS.items():
            if old in self.data:
                if new not in self.data:
                    self.data[new] = bool(self.data[old])
                del self.data[old]
                changed = True
        for key, value in DEFAULT_CONFIG.items():
            if key == "commands":
                continue
            if key not in self.data:
                self.data[key] = json.loads(json.dumps(value))
                changed = True

        workspace = self._workspace_root()
        if not str(self.data.get("workspace_root") or "").strip():
            self.data["workspace_root"] = workspace
            changed = True
        derived = {
            "distro_root": str(Path(workspace) / SUBDIR_INSTANCES),
            "backup_root": str(Path(workspace) / SUBDIR_BACKUPS),
            "snapshot_root": str(Path(workspace) / SUBDIR_SNAPSHOTS),
        }
        for key, value in derived.items():
            if not str(self.data.get(key) or "").strip():
                self.data[key] = value
                changed = True

        keep = self.data.get("snapshot_keep")
        if not isinstance(keep, dict):
            self.data["snapshot_keep"] = json.loads(
                json.dumps(DEFAULT_CONFIG["snapshot_keep"])
            )
            changed = True
        else:
            for key, value in DEFAULT_CONFIG["snapshot_keep"].items():
                if key not in keep:
                    keep[key] = value
                    changed = True
        return changed

    def save(self) -> None:
        self._validate()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.path.parent / path

    def workspace(self) -> WorkspacePaths:
        """工作目錄骨架的實際路徑。"""
        return workspace_paths(
            self.resolve_path(str(self.data["workspace_root"])),
            self.resolve_path(str(self.data["backup_root"])),
            self.resolve_path(str(self.data["snapshot_root"])),
        )

    def instance_root(self) -> Path:
        """新增／複製 instance 的預設根目錄。

        distro_root 空白或等於工作目錄（舊佈局，實例散落在根層）時，
        改用工作目錄下的 instances；其他自訂路徑則原樣沿用。
        """
        distro = str(self.data.get("distro_root") or "").strip()
        if not distro:
            return self.workspace().instances
        distro_path = self.resolve_path(distro)
        workspace = self.resolve_path(str(self.data["workspace_root"]))
        if os.path.normcase(os.path.abspath(distro_path)) == os.path.normcase(
            os.path.abspath(workspace)
        ):
            return self.workspace().instances
        return distro_path

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def remove_port_forwards(self, distro: str) -> int:
        """刪除指定 instance 的所有端口規則，回傳刪除數量。"""
        rules = self.data.get("port_forwards", [])
        keep = [rule for rule in rules if rule.get("distro") != distro]
        removed = len(rules) - len(keep)
        if removed:
            self.data["port_forwards"] = keep
            self.save()
        return removed

    def port_forwards_for(self, distro: str) -> list[dict[str, Any]]:
        return [
            rule for rule in self.data.get("port_forwards", [])
            if rule.get("distro") == distro
        ]

    def set_port_forwards_for(self, distro: str, rules: list[dict[str, Any]]) -> None:
        keep = [
            rule for rule in self.data.get("port_forwards", [])
            if rule.get("distro") != distro
        ]
        self.data["port_forwards"] = keep + rules
        self.save()

    def instance_network(self, distro: str) -> dict[str, Any]:
        """取得指定 instance 的 C 方案設定（未設定時回傳空物件）。"""
        networks = self.data.get("instance_networks", {})
        if not isinstance(networks, dict):
            return {}
        raw = networks.get(distro)
        return raw if isinstance(raw, dict) else {}

    def set_instance_network(self, distro: str, network: dict[str, Any]) -> None:
        """寫入 C 方案設定；未啟用時視為移除。"""
        networks = dict(self.data.get("instance_networks", {}))
        if network.get("enabled"):
            networks[distro] = network
        else:
            networks.pop(distro, None)
        self.data["instance_networks"] = networks
        self.save()

    def remove_instance_network(self, distro: str) -> None:
        networks = dict(self.data.get("instance_networks", {}))
        if networks.pop(distro, None) is not None:
            self.data["instance_networks"] = networks
            self.save()

    def command(self, key: str, **values: Any) -> list[str]:
        template = self.data["commands"].get(key)
        if not template:
            raise ConfigError(f"缺少命令模板：{key}")
        try:
            text = template.format(**values)
        except KeyError as exc:
            raise ConfigError(f"命令模板 {key} 缺少參數：{exc.args[0]}") from exc
        return split_command(text)

    def _validate(self) -> None:
        if not isinstance(self.data, dict):
            raise ConfigError("配置檔根節點必須是物件")
        for key in (
            "workspace_root",
            "distro_root",
            "backup_root",
            "snapshot_root",
            "commands",
            "port_forwards",
            "instance_networks",
        ):
            if key not in self.data:
                raise ConfigError(f"缺少配置項：{key}")
        for key in ("workspace_root", "distro_root", "backup_root", "snapshot_root"):
            value = self.data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"{key} 必須是非空字串")
        commands = self.data["commands"]
        if not isinstance(commands, dict):
            raise ConfigError("commands 必須是物件")
        missing = [key for key in COMMAND_KEYS if not commands.get(key)]
        if missing:
            raise ConfigError(f"缺少命令模板：{', '.join(missing)}")
        for key in ("advanced_mode", "confirm_destructive", "close_to_tray", "autostart"):
            value = self.data.get(key, DEFAULT_CONFIG[key])
            if not isinstance(value, bool):
                raise ConfigError(f"{key} 必須是布林值")
        theme = self.data.get("theme", DEFAULT_CONFIG["theme"])
        if theme not in ("system", "dark", "light"):
            raise ConfigError(f"theme 必須是 system／dark／light：{theme}")
        view_mode = self.data.get("view_mode", DEFAULT_CONFIG["view_mode"])
        if view_mode not in ("card", "list"):
            raise ConfigError(f"view_mode 必須是 card／list：{view_mode}")
        interval = self.data.get("poll_interval", DEFAULT_CONFIG["poll_interval"])
        if (
            not isinstance(interval, int)
            or isinstance(interval, bool)
            or not 3 <= interval <= 600
        ):
            raise ConfigError("poll_interval 必須是 3-600 的整數")
        instances = self.data.get("system_instances", DEFAULT_CONFIG["system_instances"])
        if not isinstance(instances, list) or not all(
            isinstance(item, str) and item.strip() for item in instances
        ):
            raise ConfigError("system_instances 必須是非空字串的陣列")
        keep = self.data.get("snapshot_keep", DEFAULT_CONFIG["snapshot_keep"])
        if not isinstance(keep, dict):
            raise ConfigError("snapshot_keep 必須是物件")
        for key in ("last", "daily", "weekly", "monthly"):
            value = keep.get(key, 0)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= 100
            ):
                raise ConfigError(f"snapshot_keep.{key} 必須是 0-100 的整數")
        proxy = self.data.get("proxy", DEFAULT_CONFIG["proxy"])
        if not isinstance(proxy, dict):
            raise ConfigError("proxy 必須是物件")
        if not isinstance(proxy.get("enabled"), bool):
            raise ConfigError("proxy.enabled 必須是布林值")
        proxy_host = proxy.get("host")
        if not isinstance(proxy_host, str) or not proxy_host.strip():
            raise ConfigError("proxy.host 必須是非空字串")
        proxy_port = proxy.get("port")
        if (
            not isinstance(proxy_port, int)
            or isinstance(proxy_port, bool)
            or not 1 <= proxy_port <= 65535
        ):
            raise ConfigError("proxy.port 必須是 1-65535 的整數")
        if not isinstance(self.data["port_forwards"], list):
            raise ConfigError("port_forwards 必須是陣列")
        ports: set[int] = set()
        for rule in self.data["port_forwards"]:
            self._validate_port_rule(rule)
            port = rule["windows_port"]
            if port in ports:
                raise ConfigError(f"Windows 端口重複：{port}")
            ports.add(port)
        self._validate_instance_networks()

    def _validate_instance_networks(self) -> None:
        networks = self.data.get("instance_networks")
        if not isinstance(networks, dict):
            raise ConfigError("instance_networks 必須是物件")
        used_ips: dict[str, str] = {}
        for distro, raw in networks.items():
            if not isinstance(distro, str) or not distro.strip():
                raise ConfigError("instance_networks 的 instance 名稱不可空白")
            if not isinstance(raw, dict):
                raise ConfigError(f"{distro} 的網路設定必須是物件")
            enabled = raw.get("enabled", False)
            if not isinstance(enabled, bool):
                raise ConfigError(f"{distro} 的 enabled 必須是布林值")
            if not enabled:
                continue
            scope = raw.get("scope")
            if scope not in NETWORK_SCOPES:
                raise ConfigError(f"{distro} 的 scope 必須是 temporary／permanent")
            ip = str(raw.get("ip") or "").strip()
            try:
                address = ipaddress.ip_address(ip)
            except ValueError as exc:
                raise ConfigError(f"{distro} 的 IP 格式不正確：{ip}") from exc
            if address.is_loopback or address.is_multicast or address.is_unspecified:
                raise ConfigError(f"{distro} 的 IP 不可使用：{ip}")
            if ip in used_ips:
                raise ConfigError(
                    f"IP {ip} 同時被 {used_ips[ip]} 與 {distro} 使用"
                )
            used_ips[ip] = distro
            services = raw.get("services")
            if not isinstance(services, list) or not services:
                raise ConfigError(f"{distro} 至少需要一個要搬入 netns 的服務")
            for service in services:
                if not isinstance(service, str) or not SERVICE_NAME_RE.match(
                    service.strip()
                ):
                    raise ConfigError(f"{distro} 的服務名稱不合法：{service}")

    @staticmethod
    def _validate_port_rule(rule: Any) -> None:
        if not isinstance(rule, dict):
            raise ConfigError("端口規則必須是物件")
        for key in ("label", "distro", "windows_port", "distro_port"):
            if key not in rule:
                raise ConfigError(f"端口規則缺少欄位：{key}")
        if not isinstance(rule["distro"], str) or not rule["distro"].strip():
            raise ConfigError("端口規則的 distro 不可空白")
        for key in ("allow_lan", "enabled"):
            rule.setdefault(key, True)
            if not isinstance(rule[key], bool):
                raise ConfigError(f"端口規則的 {key} 必須是布林值")
        for key in ("windows_port", "distro_port"):
            port = rule[key]
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise ConfigError(f"端口規則 {rule.get('label', '')} 的 {key} 必須是 1-65535")
