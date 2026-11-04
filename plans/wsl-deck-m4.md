# M4 實作計畫：網路規則、提權套用與重套

> 狀態：已確認並實作（待 GUI 驗收）
> 上層文件：[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)、[wsl-deck-mvp.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-mvp.md)
> 目標：完成 M4，讓使用者用 GUI 建立 8080 → 80 的端口轉發，只跳一次 UAC，並在啟動／開 App 時自動重套。

**Goal：** 為每個 instance 管理 Windows→distro 的 TCP 端口規則，透過一次 UAC 批次寫入 portproxy 與防火牆。

**Architecture：** 新增 `network.py` 負責規則驗證、掃描、portproxy 狀態解析與套用編排；`admin.py` 以提權子進程批次執行 netsh。UI 新增 `network_panel.py`、`rule_dialog.py`、`scan_dialog.py`，由 `MainWindow` 串接。所有 netsh 寫入只發生在提權子進程。

**Tech Stack：** Python 3.14、PySide6-Essentials 6.12、`netsh`、Windows PowerShell 5（提權）、`unittest`。

---

## 0. 範圍

- 只做 M4：規則 CRUD、掃描、立即套用、App 啟動與 instance 啟動後重套、一次 UAC 批次、狀態顯示。
- 不做 M5 托盤／開機自啟／打包；「重開機後仍有效」的完整驗收留到 M5，M4 先以「關閉 App 再開」驗證自動重套。
- 不改卡片牆與既有視覺；網路區放在詳情頁。

## 1. 已驗證的環境事實

- `netsh interface portproxy show v4tov4` 無規則時輸出空字串、退出碼 0。
- `netsh interface portproxy add v4tov4 listenport=... connectaddress=... connectport=... listenaddress=0.0.0.0 protocol=tcp` 為本機支援語法。
- `netsh advfirewall firewall add rule name=... dir=in action=allow protocol=TCP localport=... profile=private remoteip=localsubnet` 支援。
- 寫入 portproxy／防火牆需管理員；查詢 `show` 不需要。
- Windows PowerShell 5 可用 `Start-Process -Verb RunAs -Wait -PassThru` 取得提權子進程退出碼。

## 2. 檔案結構

```
wsl-deck/
  app/
    network.py             # 新增：解析、驗證、掃描、狀態、套用編排
    admin.py               # 新增：提權子進程，批次執行 netsh
    config.py              # 修改：規則欄位預設、重複端口檢查、查詢/儲存
    ui/
      network_panel.py     # 新增：詳情頁網路規則表與按鈕
      rule_dialog.py       # 新增：新增/編輯規則對話框
      scan_dialog.py       # 新增：掃描結果勾選對話框
      detail_page.py       # 修改：嵌入 NetworkPanel、轉發訊號
      main_window.py       # 修改：CRUD、套用、重套時機、狀態刷新
  tests/
    test_network.py        # 新增
    test_config.py         # 修改
```

## 3. 資料模型

`config.json` 的 `port_forwards` 每條規則：

```json
{
  "label": "8080 → 80",
  "distro": "wsl-deck-test",
  "windows_port": 8080,
  "distro_port": 80,
  "allow_lan": true,
  "enabled": true
}
```

- `label` 由 UI 自動產生，不單獨顯示。
- 同一 `windows_port` 全 App 只能有一條；`distro_port` 可重複。
- 舊資料缺少 `allow_lan`／`enabled` 時視為 `true`。

狀態定義（依序判斷）：

| 狀態 | 條件 |
|------|------|
| 已停用 | `enabled == false` |
| 待啟動 | instance 未執行 |
| 已套用 | 執行中，且 portproxy 有 `listen_port=windows_port`、`connect_address=目前 IP`、`connect_port=distro_port` |
| 待套用 | 其餘（含剛新增、IP 變更、套用失敗） |

## 4. 任務

### Task 1：Config 規則欄位與驗證

**Files：** Modify：`wsl-deck/app/config.py`、`wsl-deck/tests/test_config.py`

- [ ] **Step 1：先寫測試**

```python
def test_port_rule_defaults(self) -> None:
    self.config.data["port_forwards"] = [
        {"label": "web", "distro": "node22", "windows_port": 8080, "distro_port": 80}
    ]
    self.config.save()
    self.assertTrue(self.config.data["port_forwards"][0]["allow_lan"])
    self.assertTrue(self.config.data["port_forwards"][0]["enabled"])
    self.assertEqual(len(self.config.port_forwards_for("node22")), 1)

def test_duplicate_windows_port_rejected(self) -> None:
    self.config.data["port_forwards"] = [
        {"label": "a", "distro": "node22", "windows_port": 8080, "distro_port": 80},
        {"label": "b", "distro": "ubuntu", "windows_port": 8080, "distro_port": 81},
    ]
    with self.assertRaises(ConfigError):
        self.config.save()

def test_set_port_forwards_for(self) -> None:
    self.config.set_port_forwards_for("node22", [
        {"label": "web", "distro": "node22", "windows_port": 8080,
         "distro_port": 80, "allow_lan": True, "enabled": True},
    ])
    self.assertEqual(len(self.config.port_forwards_for("node22")), 1)
```

- [ ] **Step 2：實作**

`_validate_port_rule`：

```python
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
```

`_validate()` 在迴圈後檢查重複：

```python
ports: set[int] = set()
for rule in self.data["port_forwards"]:
    port = rule["windows_port"]
    if port in ports:
        raise ConfigError(f"Windows 端口重複：{port}")
    ports.add(port)
```

新增方法：

```python
def port_forwards_for(self, distro: str) -> list[dict[str, Any]]:
    return [rule for rule in self.data["port_forwards"] if rule["distro"] == distro]

def set_port_forwards_for(self, distro: str, rules: list[dict[str, Any]]) -> None:
    keep = [rule for rule in self.data["port_forwards"] if rule["distro"] != distro]
    self.data["port_forwards"] = keep + rules
    self.save()
```

- [ ] **Step 3：跑測試**

```
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest tests.test_config -q
```

### Task 2：`network.py` 解析、驗證、狀態（含測試）

**Files：** Create：`wsl-deck/app/network.py`、`wsl-deck/tests/test_network.py`

- [ ] **Step 1：先寫測試**

```python
"""network 純函式測試。"""

from __future__ import annotations

import unittest

from app.network import (
    ApplyResult,
    PortProxyEntry,
    apply_rules,
    build_admin_job,
    firewall_rule_name,
    parse_listen_ports,
    parse_portproxy,
    rule_status,
    validate_rule,
)


PORT_PROXY_TEXT = """
Listen on ipv4:             Connect to ipv4:

Address         Port        Address         Port

--------------- ----------  --------------- ----------

*               8080        172.20.10.2     80
0.0.0.0         8081        172.20.10.2     81
"""


class PortProxyParseTest(unittest.TestCase):
    def test_parse(self) -> None:
        self.assertEqual(
            parse_portproxy(PORT_PROXY_TEXT),
            [
                PortProxyEntry(8080, "172.20.10.2", 80),
                PortProxyEntry(8081, "172.20.10.2", 81),
            ],
        )

    def test_empty(self) -> None:
        self.assertEqual(parse_portproxy(""), [])


class ScanParseTest(unittest.TestCase):
    def test_ss_output(self) -> None:
        text = (
            "State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
            "LISTEN 0      4096   0.0.0.0:80         0.0.0.0:*\n"
            "LISTEN 0      128    [::]:22            [::]:*\n"
            "LISTEN 0      128    127.0.0.1:3000     0.0.0.0:*\n"
        )
        self.assertEqual(parse_listen_ports(text), [22, 80, 3000])

    def test_netstat_output(self) -> None:
        text = (
            "tcp        0      0 0.0.0.0:8080        0.0.0.0:*               LISTEN\n"
            "tcp6       0      0 :::22               :::*                    LISTEN\n"
            "udp        0      0 0.0.0.0:53          0.0.0.0:*\n"
        )
        self.assertEqual(parse_listen_ports(text), [22, 8080])


class RuleValidationTest(unittest.TestCase):
    def test_valid(self) -> None:
        rule = {"label": "web", "distro": "node22", "windows_port": 8080,
                "distro_port": 80, "allow_lan": True, "enabled": True}
        validate_rule(rule, [])

    def test_duplicate_windows_port(self) -> None:
        existing = [{"label": "a", "distro": "ubuntu", "windows_port": 8080,
                     "distro_port": 80, "allow_lan": True, "enabled": True}]
        rule = {"label": "b", "distro": "node22", "windows_port": 8080,
                "distro_port": 81, "allow_lan": True, "enabled": True}
        with self.assertRaises(ValueError):
            validate_rule(rule, existing)

    def test_port_range(self) -> None:
        rule = {"label": "x", "distro": "node22", "windows_port": 70000,
                "distro_port": 0, "allow_lan": True, "enabled": True}
        with self.assertRaises(ValueError):
            validate_rule(rule, [])


class StatusTest(unittest.TestCase):
    def test_statuses(self) -> None:
        rule = {"windows_port": 8080, "distro_port": 80, "enabled": True}
        self.assertEqual(rule_status(rule, False, "", []), "待啟動")
        self.assertEqual(rule_status(rule, True, "172.20.10.2", []), "待套用")
        entries = [PortProxyEntry(8080, "172.20.10.2", 80)]
        self.assertEqual(rule_status(rule, True, "172.20.10.2", entries), "已套用")
        rule["enabled"] = False
        self.assertEqual(rule_status(rule, True, "172.20.10.2", entries), "已停用")


class JobTest(unittest.TestCase):
    def test_build_job(self) -> None:
        rules = [
            {"label": "web", "distro": "node22", "windows_port": 8080,
             "distro_port": 80, "allow_lan": True, "enabled": True},
            {"label": "off", "distro": "node22", "windows_port": 8081,
             "distro_port": 81, "allow_lan": True, "enabled": False},
        ]
        job = build_admin_job(
            [("node22", "172.20.10.2", rules)], [("node22", 8090)]
        )
        self.assertEqual(job["portproxy_delete"], [8080, 8081, 8090])
        self.assertEqual(len(job["portproxy_add"]), 1)
        self.assertEqual(job["portproxy_add"][0]["windows_port"], 8080)
        self.assertEqual(len(job["firewall_add"]), 1)
        self.assertEqual(
            job["firewall_add"][0]["windows_port"], 8080
        )
        self.assertEqual(
            job["firewall_add"][0]["name"], "WSL Deck node22 8080"
        )
        self.assertIn(8090, [item["windows_port"] for item in job["firewall_delete"]])

    def test_firewall_name(self) -> None:
        self.assertEqual(firewall_rule_name("node22", 8080), "WSL Deck node22 8080")
```

- [ ] **Step 2：實作 `network.py`**

```python
"""網路規則：驗證、掃描、portproxy 狀態與套用編排。"""

from __future__ import annotations

import ipaddress
import logging
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
    proc = subprocess.run(
        ["netsh", "interface", "portproxy", "show", "v4tov4"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, creationflags=CREATE_NO_WINDOW,
    )
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


def scan_tcp_ports(name: str) -> list[int]:
    output = run_wsl(
        ["-d", name, "--", "sh", "-c", "ss -tln 2>/dev/null || netstat -tln"],
        timeout=120,
    )
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
        if not isinstance(port, int) or not 1 <= port <= 65535:
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
                "distro": name, "windows_port": port,
                "name": firewall_rule_name(name, port),
            }
            if rule.get("enabled", True):
                if rule.get("allow_lan", True):
                    firewall_add.append({
                        "distro": name, "windows_port": port,
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
            "distro": name, "windows_port": port,
            "name": firewall_rule_name(name, port),
        }

    return {
        "portproxy_delete": sorted(delete_ports),
        "portproxy_add": portproxy_add,
        "firewall_delete": list(firewall_delete.values()),
        "firewall_add": firewall_add,
    }
```

- [ ] **Step 3：跑測試**

```
.\.venv\Scripts\python.exe -m unittest tests.test_network -q
```

### Task 3：`admin.py` 一次 UAC 批次

**Files：** Create：`wsl-deck/app/admin.py`

- [ ] **Step 1：提權子進程 CLI**

```python
"""管理員批次：讀取 job JSON，執行 netsh，寫回結果。"""

from __future__ import annotations

import ipaddress
import json
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


def _run(command: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, creationflags=CREATE_NO_WINDOW,
    )
    return proc.returncode, (proc.stderr or proc.stdout).strip()


def _validate(job: dict) -> None:
    for port in job.get("portproxy_delete", []):
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"listenport 不合法：{port}")
    for item in job.get("portproxy_add", []):
        ipaddress.IPv4Address(item["connect_address"])
        for key in ("windows_port", "connect_port"):
            port = item[key]
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError(f"{key} 不合法：{port}")
    for item in job.get("firewall_add", []):
        if not str(item.get("distro", "")).strip():
            raise ValueError("防火牆規則缺少 distro")
        port = item.get("windows_port")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"防火牆 windows_port 不合法：{port}")
    for item in job.get("firewall_delete", []):
        if not str(item.get("distro", "")).strip():
            raise ValueError("防火牆規則缺少 distro")
        port = item.get("windows_port")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"防火牆 windows_port 不合法：{port}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    job_path, result_path = Path(argv[0]), Path(argv[1])
    result = {"ok": False, "errors": [], "warnings": [], "commands": []}
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        _validate(job)

        for port in job.get("portproxy_delete", []):
            command = [
                "netsh", "interface", "portproxy", "delete", "v4tov4",
                f"listenport={port}", "listenaddress=0.0.0.0",
            ]
            code, message = _run(command)
            result["commands"].append(" ".join(command))
            if code != 0:
                result["warnings"].append(f"刪除 portproxy {port}：{message}")

        for item in job.get("firewall_delete", []):
            name = f"WSL Deck {item['distro']} {item['windows_port']}"
            command = ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"]
            code, message = _run(command)
            result["commands"].append(" ".join(command))
            if code != 0:
                result["warnings"].append(f"刪除防火牆 {name}：{message}")

        for item in job.get("portproxy_add", []):
            command = [
                "netsh", "interface", "portproxy", "add", "v4tov4",
                f"listenaddress=0.0.0.0",
                f"listenport={item['windows_port']}",
                f"connectaddress={item['connect_address']}",
                f"connectport={item['connect_port']}",
                "protocol=tcp",
            ]
            code, message = _run(command)
            result["commands"].append(" ".join(command))
            if code != 0:
                result["errors"].append(f"新增 portproxy {item['windows_port']}：{message}")

        for item in job.get("firewall_add", []):
            name = f"WSL Deck {item['distro']} {item['windows_port']}"
            command = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={name}", "dir=in", "action=allow", "protocol=TCP",
                f"localport={item['windows_port']}",
                "profile=private", "remoteip=localsubnet",
            ]
            code, message = _run(command)
            result["commands"].append(" ".join(command))
            if code != 0:
                result["errors"].append(f"新增防火牆 {name}：{message}")

        result["ok"] = not result["errors"]
    except Exception as exc:  # noqa: BLE001 - 寫回結果檔
        result["errors"].append(str(exc))
    finally:
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2：提權啟動與等待**

在 `admin.py` 增加：

```python
import base64
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AdminResult:
    ok: bool
    denied: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def run_admin_job(job: dict) -> AdminResult:
    """以 runas 啟動自身副本；成功回傳子進程寫出的結果。"""
    base = Path(tempfile.gettempdir()) / f"wsl-deck-{uuid.uuid4().hex}"
    job_path = base.with_suffix(".job.json")
    result_path = base.with_suffix(".result.json")
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

    project = Path(__file__).resolve().parent.parent
    exe = sys.executable
    script = (
        f"$p = Start-Process -FilePath {_quote(exe)} "
        f"-ArgumentList @('-m','app.admin',{_quote(str(job_path))},{_quote(str(result_path))}) "
        f"-WorkingDirectory {_quote(str(project))} -Verb RunAs -Wait -PassThru; "
        f"exit $p.ExitCode"
    )

    try:
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, creationflags=CREATE_NO_WINDOW,
        )
        if not result_path.exists():
            denied = proc.returncode != 0
            return AdminResult(
                ok=False,
                denied=denied,
                errors=[proc.stderr.strip() or "未取得管理員授權"],
            )
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return AdminResult(
            ok=bool(data.get("ok")),
            errors=list(data.get("errors", [])),
            warnings=list(data.get("warnings", [])),
            commands=list(data.get("commands", [])),
        )
    finally:
        job_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)
```

- [ ] **Step 3：手動驗證提權（不寫入規則）**

建立只含 `"portproxy_delete": []` 的空 job，執行 `run_admin_job`，確認：
- 跳一次 UAC；
- 取消時 `denied=True`；
- 允許時 `ok=True`。

### Task 4：套用編排（`apply_rules`）

**Files：** Modify：`wsl-deck/app/network.py`

- [ ] **Step 1：實作**

```python
def apply_rules(
    targets: list[tuple[str, list[dict]]],
    cleanup: list[tuple[str, int]] | None = None,
    stage: Stage | None = None,
) -> ApplyResult:
    from app.admin import run_admin_job

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
                ip = get_distro_ip(name)
            except WslError as exc:
                result.ok = False
                result.errors.append(f"{name}：取得 IP 失敗（{exc}）")
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
```

- [ ] **Step 2：單元測試**

用 fake `show_portproxy`／`get_distro_ip`／`run_admin_job` 驗證：

```python
from unittest.mock import patch

class ApplyRulesTest(unittest.TestCase):
    def test_skip_occupied_port(self) -> None:
        rules = [{"label": "web", "distro": "node22", "windows_port": 8080,
                  "distro_port": 80, "allow_lan": True, "enabled": True}]
        with patch("app.network.show_portproxy", return_value=[]), \
             patch("app.network.get_distro_ip", return_value="172.20.10.2"), \
             patch("app.network.port_occupied", return_value=True), \
             patch("app.admin.run_admin_job") as admin:
            result = apply_rules([("node22", rules)])
        self.assertEqual(
            result.warnings, ["Windows 端口 8080 已被其他程式佔用，已略過"]
        )
        admin.assert_not_called()
```

- 停用規則只產生刪除命令。
- 端口被佔用時跳過新增並回傳 warning。
- 沒有工作時不呼叫 `run_admin_job`。

### Task 5：`NetworkPanel` 與規則對話框

**Files：** Create：`wsl-deck/app/ui/network_panel.py`、`wsl-deck/app/ui/rule_dialog.py`

- [ ] **Step 1：NetworkPanel**

```python
class NetworkPanel(QGroupBox):
    add_requested = Signal()
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    apply_requested = Signal()
    scan_requested = Signal()

    def set_context(self, name: str, is_system: bool, running: bool) -> None: ...
    def set_rules(self, rules: list[dict], statuses: dict[int, str]) -> None: ...
    def selected_windows_port(self) -> int | None: ...
```

- `QTableWidget` 五欄：Windows 端口、distro 端口、允許 LAN、啟用、狀態。
- 列為唯讀、整列選取、雙擊列開啟編輯。
- 按鈕列：新增規則、編輯、刪除、立即套用、掃描監聽端口；高度 32、手型／禁止游標。
- 系統 instance 全部禁用；無規則時顯示「尚無規則」。
- 狀態色：已套用綠、待套用橙、待啟動灰、已停用灰。
- 底部灰字：「允許 LAN 僅對私人網路（profile=private）的本地子網開放；Public 網路會被阻擋。」
- 無選取時編輯／刪除禁用；無規則時立即套用禁用。

- [ ] **Step 2：RuleDialog**

```python
class RuleDialog(QDialog):
    def __init__(self, distro: str, rules: list[dict], rule: dict | None = None, parent=None): ...
    # 成功後：self.rule = {...}
```

- 欄位：Windows 端口（QSpinBox 1-65535，預設 8080）、distro 端口（預設 80）、允許 LAN（預設勾選）、啟用（預設勾選）。
- 編輯時預填，`ignore_windows_port=舊值`。
- `label` 自動 `f"{windows} → {distro}"`。
- `validate_rule()` 失敗時紅字顯示，不關閉。
- 按鈕：取消／確定（新增時「新增規則」、編輯時「儲存」）。

### Task 6：掃描對話框

**Files：** Create：`wsl-deck/app/ui/scan_dialog.py`

- [ ] **Step 1：ScanDialog**

```python
class ScanDialog(QDialog):
    def __init__(self, distro: str, ports: list[int], rules: list[dict], parent=None): ...
    # 成功後：self.rules -> list[dict]
```

- 表格欄位：勾選、distro 端口、Windows 端口（QSpinBox，預設同 distro 端口）、備註。
- 已存在相同 distro 端口的規則標註「已有規則」並預設不勾選（仍可勾選建立不同 Windows 端口）。
- 預設勾選全部未衝突端口；Windows 端口與現有規則或本次其他勾選列衝突時紅字並阻止確定。
- 確定後產生規則：`allow_lan=True`、`enabled=True`、label 自動。

### Task 7：DetailPage 嵌入與訊號

**Files：** Modify：`wsl-deck/app/ui/detail_page.py`

- [ ] **Step 1：替換網路區 placeholder**

把目前 `QGroupBox("網路規則")` 的說明與兩個停用按鈕換成：

```python
self.network_panel = NetworkPanel(self)
layout.addWidget(self.network_panel)
self.network_panel.add_requested.connect(self.network_add_requested)
self.network_panel.edit_requested.connect(self.network_edit_requested)
self.network_panel.delete_requested.connect(self.network_delete_requested)
self.network_panel.apply_requested.connect(self.network_apply_requested)
self.network_panel.scan_requested.connect(self.network_scan_requested)
```

新增訊號：

```python
network_add_requested = Signal()
network_edit_requested = Signal(int)
network_delete_requested = Signal(int)
network_apply_requested = Signal()
network_scan_requested = Signal()
```

`set_distro()` 內：

```python
self.network_panel.set_context(distro.name, is_system, distro.running)
```

`set_network(rules, statuses)` 轉呼叫 panel。

### Task 8：MainWindow 編排

**Files：** Modify：`wsl-deck/app/ui/main_window.py`

- [ ] **Step 1：狀態刷新**

```python
def _refresh_network(self, name: str, rules: list[dict] | None = None) -> None:
    distro = self._find(name)
    if distro is None or self._current is None or self._current.name != name:
        return
    if self._network_busy:
        return
    self._network_busy = True
    rules = rules if rules is not None else self.config.port_forwards_for(name)
    self._run_task(
        partial(self._network_snapshot, name, distro.running),
        partial(self._on_network_snapshot, name, rules),
        partial(self._on_network_error, name, rules),
    )

def _network_snapshot(self, name: str, running: bool):
    from app.network import show_portproxy
    ip = get_distro_ip(name) if running else ""
    return ip, show_portproxy()
```

`_on_network_snapshot` 計算 statuses 並 `self._detail_page.set_network(rules, statuses)`；`_network_busy=False`：

```python
def _on_network_snapshot(self, name: str, rules: list[dict], snapshot) -> None:
    self._network_busy = False
    distro = self._find(name)
    if distro is None or self._current is None or self._current.name != name:
        return
    ip, entries = snapshot
    statuses = {
        rule["windows_port"]: rule_status(rule, distro.running, ip, entries)
        for rule in rules
    }
    self._detail_page.set_network(rules, statuses)

def _on_network_error(self, name: str, rules: list[dict], message: str) -> None:
    self._network_busy = False
    logger.warning("讀取網路狀態失敗：%s", message)
    distro = self._find(name)
    running = bool(distro and distro.running)
    statuses = {
        rule["windows_port"]: (
            "待啟動" if not running else ("已停用" if not rule.get("enabled", True) else "待套用")
        )
        for rule in rules
    }
    if self._current is not None and self._current.name == name:
        self._detail_page.set_network(rules, statuses)
```

在 `_show_detail()`、`_on_distros()` 當前詳情頁時呼叫 `_refresh_network`。

- [ ] **Step 2：規則 CRUD**

- 新增：`RuleDialog` → `validate_rule` 已完成 → 追加到 `config.data["port_forwards"]`、`save()` → `_after_rule_change(name, cleanup=[])`。
- 編輯：找舊規則；`RuleDialog(rule=old)`；儲存時保留 label；若 Windows 端口改變或由啟用改停用，`cleanup=[舊 windows_port]`。
- 刪除：確認對話框（列出端口），移除規則、`save()`，`cleanup=[windows_port]`。
- `_after_rule_change`：
  ```python
  self._refresh_network(name)
  if distro.running:
      answer = QMessageBox.question(
          self, "規則已變更", "要立即套用變更嗎？",
          QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
      )
      if answer == QMessageBox.Yes:
          self._apply_instance(name, cleanup_ports=cleanup)
      else:
          self._pending_cleanup.setdefault(name, set()).update(cleanup)
  else:
      self._pending_cleanup.setdefault(name, set()).update(cleanup)
  # 若新規則重新使用了待清理的端口，移除該清理項
  used = {rule["windows_port"] for rule in self.config.data["port_forwards"]}
  self._pending_cleanup[name] = {
      port for port in self._pending_cleanup.get(name, set()) if port not in used
  }
  ```
- 使用 `QMessageBox.question` 的 Yes／No（中文系統會顯示「是／否」）；成功後再依選擇套用或記入待清理。

- [ ] **Step 3：套用**

```python
def _ask_start_for_apply(self) -> bool:
    answer = QMessageBox.question(
        self, "套用網路規則", "instance 未執行，要先啟動再套用嗎？"
    )
    return answer == QMessageBox.Yes

def _apply_instance(self, name: str, cleanup_ports: list[int] | None = None) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    if not distro.running:
        if self._ask_start_for_apply():
            self._apply_after_start = name
            self._start(name)
        return
    pending = set(self._pending_cleanup.get(name, set()))
    pending.update(cleanup_ports or [])
    used = {rule["windows_port"] for rule in self.config.data["port_forwards"]}
    cleanup = [(name, port) for port in sorted(pending) if port not in used]
    rules = self.config.port_forwards_for(name)
    self._run_operation(
        "套用網路規則",
        partial(apply_rules, [(name, rules)], cleanup),
        partial(self._on_apply_done, name),
        lambda _message: self._refresh_network(name),
    )

def _on_apply_done(self, name: str, result) -> None:
    if result.ok:
        self._pending_cleanup.pop(name, None)
    if result.denied:
        QMessageBox.warning(self, "需要管理員權限", "已取消管理員授權，規則維持待套用。")
    elif result.errors:
        QMessageBox.warning(self, "套用失敗", "\n".join(result.errors))
    if result.warnings:
        logger.warning("；".join(result.warnings))
    logger.info("已套用 %s 的網路規則", name)
    self._refresh_network(name)
    self.refresh()
```

- pending cleanup 只在成功後清除；失敗或拒絕 UAC 時保留，下次再試。
- 已被現有規則重新使用的 Windows 端口不列入 cleanup，避免誤刪新規則。

- [ ] **Step 4：重套時機**

- instance 啟動成功：`_start()` 成功 callback 改為 `self._after_started(name)`。
  ```python
  def _after_started(self, name: str) -> None:
      logger.info("已啟動 %s", name)
      if self._scan_after_start == name:
          self._scan_after_start = ""
          self._scan_ports(name)
          return
      if self._apply_after_start == name:
          self._apply_after_start = ""
          self._apply_instance(name)
          return
      rules = self.config.port_forwards_for(name)
      if rules or name in self._pending_cleanup:
          self._apply_instance(name)
      else:
          self.refresh()
  ```
- App 啟動自動重套：`_on_distros` 首次成功後，若任一執行中 instance 有啟用規則，`QTimer.singleShot(0, self._auto_apply_all)`，只做一次。
  ```python
  def _auto_apply_all(self) -> None:
      targets = []
      for distro in self._distros:
          if not distro.running or self._is_system(distro.name):
              continue
          rules = self.config.port_forwards_for(distro.name)
          if rules:
              targets.append((distro.name, rules))
      if not targets:
          return
      self._run_operation("重新套用網路規則", partial(apply_rules, targets), self._on_auto_apply_done)
  ```
  - 一次 `apply_rules` 呼叫 = 一次 UAC，涵蓋所有 instance。
  - UAC 拒絕後不重試；狀態顯示待套用。

  ```python
  def _on_auto_apply_done(self, result) -> None:
      if result.denied:
          logger.warning("已取消管理員授權，網路規則維持待套用")
      if result.errors:
          logger.warning("自動套用失敗：%s", "；".join(result.errors))
      if result.warnings:
          logger.warning("；".join(result.warnings))
      if self._current is not None:
          self._refresh_network(self._current.name)
      self.refresh()
  ```
- 手動「立即套用」：`network_apply_requested` → `_apply_instance(current.name)`。
- instance 停止：不刪除規則；`_refresh_network` 將狀態顯示「待啟動」。

- [ ] **Step 5：掃描**

```python
def _scan_network(self, name: str) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    if not distro.running:
        answer = QMessageBox.question(self, "掃描監聽端口", "instance 未執行，要先啟動再掃描嗎？")
        if answer != QMessageBox.Yes:
            return
        self._scan_after_start = name
        self._start(name)
        return
    self._scan_ports(name)

def _scan_ports(self, name: str) -> None:
    self._run_operation(
        "掃描監聽端口",
        partial(scan_tcp_ports, name),
        partial(self._show_scan_result, name),
        lambda _message: None,
    )

def _show_scan_result(self, name: str, ports: list[int]) -> None:
    if not ports:
        QMessageBox.information(self, "掃描監聽端口", "沒有找到監聽中的 TCP 端口。")
        return
    dialog = ScanDialog(name, ports, self.config.port_forwards_for(name), self)
    if dialog.exec() != QDialog.Accepted:
        return
    if not dialog.rules:
        return
    self.config.data["port_forwards"].extend(dialog.rules)
    self.config.save()
    self._after_rule_change(name)
```

`_after_started` 若 `self._scan_after_start == name`，先掃描、不自動套用；掃描新增規則後再由 `_after_rule_change` 詢問套用。

- [ ] **Step 6：接線**

`_connect_signals()` 增加：

```python
self._detail_page.network_add_requested.connect(self._network_add)
self._detail_page.network_edit_requested.connect(self._network_edit)
self._detail_page.network_delete_requested.connect(self._network_delete)
self._detail_page.network_apply_requested.connect(self._network_apply)
self._detail_page.network_scan_requested.connect(self._network_scan)
```

`__init__` 增加：

```python
self._network_busy = False
self._scan_after_start = ""
self._apply_after_start = ""
self._pending_cleanup: dict[str, set[int]] = {}
self._auto_apply_done = False
```

### Task 9：測試與驗收

- [ ] **Step 1：自動測試**

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：28 項舊測試＋新增 14 項（共 42 項）全部通過。

- [ ] **Step 2：GUI 驗收（測試 instance）**

1. 建立 `wsl-deck-test`（M3 精靈）。
2. 詳情頁「新增規則」：Windows 8080、distro 80、允許 LAN、啟用。
3. 啟動 instance；在 distro 內跑 `python3 -m http.server 80`（測試 instance 預設為 root；若無 python3 改用 `busybox httpd -p 80`）。
4. 按「立即套用」→ 只跳一次 UAC。
5. 檢查：
   ```
   netsh interface portproxy show v4tov4
   netsh advfirewall firewall show rule name="WSL Deck wsl-deck-test 8080"
   curl http://localhost:8080
   curl http://<Windows 區網 IP>:8080
   ```
6. 規則狀態應為「已套用」；同網段另一台裝置可訪問（若無其他裝置，以 Windows 區網 IP 訪問代替）。
7. 終止 instance → 狀態變「待啟動」；再啟動 → 自動跳一次 UAC 並回到「已套用」。
8. 關閉 App 再開（instance 執行中）→ 啟動後自動跳一次 UAC，狀態回到「已套用」。
9. 刪除規則 → 詢問是否立即套用 → 是 → UAC 後 `portproxy show` 與防火牆規則消失。
10. 衝突測試：Windows 先用其他程式佔用 8090，新增 8090 → 套用時顯示「已被其他程式佔用，已略過」，不影響其他規則。
11. 清理測試 instance 與所有規則。

- [ ] **Step 3：回報**

記錄 UAC 次數、實際 netsh 輸出、狀態變化與任何 CLI 差異，更新 handoff。

## 5. 風險與對策

- **每次套用都會跳 UAC**：以批次 job 把同一次操作的所有規則放在一個提權子進程；拒絕後不自動重試，狀態維持待套用。
- **啟動 App 自動重套可能打斷使用者**：只在第一次刷新後執行一次，且所有 instance 合併成一次 UAC。
- **Public 網路**：防火牆只開 private + localsubnet；面板固定提示 Public 會被阻擋。
- **Windows 端口被其他程式佔用**：套用前以 socket bind 檢查；有 portproxy 項目的端口視為本 App 可覆蓋，其餘跳過並警告。
- **netsh 刪除不存在的規則**：視為 warning，不中斷新增。
- **portproxy 顯示格式在地化**：以「4 個 token、第 2/4 個為數字」解析，不看表頭文字。
- **IP 變更**：狀態以目前 IP 比對；instance 重新啟動後會自動重套。
- **套用失敗後的殘留**：job 先刪後加；新增失敗會回報，舊規則可能已刪除，使用者可再按立即套用重試。
- **M5 打包**：目前提權以 `sys.executable -m app.admin` 啟動；PyInstaller 後需改為 exe `--admin-job`，列入 M5。

## 6. 確認清單

- [ ] 規則 CRUD 只在詳情頁網路區，不做卡片右鍵。
- [ ] 一次操作只跳一次 UAC；App 啟動時多個 instance 合併為一次。
- [ ] 規則變更後詢問「立即套用／稍後」；稍後則保留待套用與清理清單。
- [ ] 刪除／停用規則會清掉對應 portproxy 與防火牆規則。
- [ ] 掃描未執行時詢問是否啟動，`ss -tln` 失敗退回 `netstat -tln`。
- [ ] 防火牆只開 private + localsubnet，規則名稱 `WSL Deck <instance> <windows_port>`。
- [ ] 確認後開始實作，完成後回報並等待 GUI 驗收。
