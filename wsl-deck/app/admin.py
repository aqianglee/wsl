"""管理員批次：讀取 job JSON、執行 netsh、寫回結果，並提供提權入口。"""

from __future__ import annotations

import base64
import ipaddress
import json
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


@dataclass
class AdminResult:
    ok: bool
    denied: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


def _run_netsh(args: list[str]) -> tuple[int, str]:
    command = ["netsh", *args]
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=CREATE_NO_WINDOW,
    )
    return proc.returncode, (proc.stderr or proc.stdout).strip()


def _valid_port(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def _validate(job: dict) -> None:
    for port in job.get("portproxy_delete", []):
        if not _valid_port(port):
            raise ValueError(f"listenport 不合法：{port}")
    for item in job.get("portproxy_add", []):
        ipaddress.IPv4Address(item["connect_address"])
        for key in ("windows_port", "connect_port"):
            if not _valid_port(item[key]):
                raise ValueError(f"{key} 不合法：{item[key]}")
    for key in ("firewall_add", "firewall_delete"):
        for item in job.get(key, []):
            if not str(item.get("distro", "")).strip():
                raise ValueError("防火牆規則缺少 distro")
            if not _valid_port(item.get("windows_port")):
                raise ValueError(f"防火牆 windows_port 不合法：{item.get('windows_port')}")


def _execute(job: dict, result: dict) -> None:
    for port in job.get("portproxy_delete", []):
        code, message = _run_netsh([
            "interface", "portproxy", "delete", "v4tov4",
            f"listenport={port}", "listenaddress=0.0.0.0",
        ])
        result["commands"].append(f"netsh portproxy delete listenport={port}")
        if code != 0:
            result["warnings"].append(f"刪除 portproxy {port}：{message}")

    for item in job.get("firewall_delete", []):
        name = item.get("name") or f"WSL Deck {item['distro']} {item['windows_port']}"
        code, message = _run_netsh([
            "advfirewall", "firewall", "delete", "rule", f"name={name}",
        ])
        result["commands"].append(f"netsh firewall delete name={name}")
        if code != 0:
            result["warnings"].append(f"刪除防火牆 {name}：{message}")

    for item in job.get("portproxy_add", []):
        code, message = _run_netsh([
            "interface", "portproxy", "add", "v4tov4",
            "listenaddress=0.0.0.0",
            f"listenport={item['windows_port']}",
            f"connectaddress={item['connect_address']}",
            f"connectport={item['connect_port']}",
            "protocol=tcp",
        ])
        result["commands"].append(
            f"netsh portproxy add listenport={item['windows_port']} "
            f"connect={item['connect_address']}:{item['connect_port']}"
        )
        if code != 0:
            result["errors"].append(f"新增 portproxy {item['windows_port']}：{message}")

    for item in job.get("firewall_add", []):
        name = item.get("name") or f"WSL Deck {item['distro']} {item['windows_port']}"
        code, message = _run_netsh([
            "advfirewall", "firewall", "add", "rule",
            f"name={name}", "dir=in", "action=allow", "protocol=TCP",
            f"localport={item['windows_port']}",
            "profile=private", "remoteip=localsubnet",
        ])
        result["commands"].append(f"netsh firewall add name={name}")
        if code != 0:
            result["errors"].append(f"新增防火牆 {name}：{message}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    job_path, result_path = Path(argv[0]), Path(argv[1])
    result: dict[str, object] = {
        "ok": False, "errors": [], "warnings": [], "commands": [],
    }
    try:
        job = json.loads(job_path.read_text(encoding="utf-8-sig"))
        _validate(job)
        _execute(job, result)
        result["ok"] = not result["errors"]
    except Exception as exc:  # noqa: BLE001 - 一律寫回結果
        result["errors"].append(str(exc))
    finally:
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0 if result["ok"] else 1


def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _admin_launcher(job_path: Path, result_path: Path) -> tuple[str, str, str]:
    """回傳（執行檔, PowerShell ArgumentList, 工作目錄）。"""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        return exe, f'--admin-job "{job_path}" "{result_path}"', str(Path(exe).parent)
    project = Path(__file__).resolve().parent.parent
    return exe, f'-m app.admin "{job_path}" "{result_path}"', str(project)


def run_admin_job(job: dict) -> AdminResult:
    """以 runas 啟動自身副本；回傳子進程寫出的結果。"""
    base = Path(tempfile.gettempdir()) / f"wsl-deck-{uuid.uuid4().hex}"
    job_path = Path(f"{base}.job.json")
    result_path = Path(f"{base}.result.json")
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

    exe, arg_string, work_dir = _admin_launcher(job_path, result_path)
    script = (
        "$ProgressPreference='SilentlyContinue';"
        "$ErrorActionPreference='Stop';"
        f"try {{ $p = Start-Process -FilePath {_ps_quote(exe)} "
        f"-ArgumentList {_ps_quote(arg_string)} "
        f"-WorkingDirectory {_ps_quote(work_dir)} "
        "-Verb RunAs -WindowStyle Hidden -Wait -PassThru } catch { exit 1223 }; "
        "exit $p.ExitCode"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")

    try:
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-EncodedCommand", encoded,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        job_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)
        return AdminResult(ok=False, errors=["等待管理員授權逾時"])
    except FileNotFoundError:
        job_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)
        return AdminResult(ok=False, errors=["找不到 powershell.exe"])

    try:
        if result_path.exists():
            data = json.loads(result_path.read_text(encoding="utf-8-sig"))
            return AdminResult(
                ok=bool(data.get("ok")),
                errors=[str(item) for item in data.get("errors", [])],
                warnings=[str(item) for item in data.get("warnings", [])],
                commands=[str(item) for item in data.get("commands", [])],
            )
        denied = proc.returncode != 0
        message = "未取得管理員授權，或管理員進程未回報結果"
        stderr = proc.stderr.strip()
        if stderr and "#< CLIXML" not in stderr and "<Objs" not in stderr:
            message = stderr
        return AdminResult(ok=False, denied=denied, errors=[message])
    except json.JSONDecodeError as exc:
        return AdminResult(ok=False, errors=[f"管理員結果格式錯誤：{exc}"])
    finally:
        job_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
