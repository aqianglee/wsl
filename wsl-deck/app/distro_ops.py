"""Instance 建立、備份、還原、複製、刪除流程。"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.wsl import Distro, WslError, run_wsl, shutdown_all, terminate_distro

logger = logging.getLogger(__name__)

Stage = Callable[[str], None]

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LONG_TIMEOUT = 3600


@dataclass(frozen=True)
class OnlineDistro:
    name: str
    friendly_name: str


@dataclass(frozen=True)
class NewInstancePlan:
    source: str  # "online" / "tar" / "vhdx"
    name: str
    install_dir: str
    file: str = ""
    version: int = 2


def _stage(stage: Stage | None, message: str) -> None:
    logger.info(message)
    if stage is not None:
        stage(message)


def _run(args: list[str], timeout: int) -> str:
    logger.info("執行：%s", subprocess.list2cmdline(["wsl.exe", *args]))
    return run_wsl(args, timeout=timeout)


def parse_online_list(text: str) -> list[OnlineDistro]:
    """解析 wsl --list --online 的表格（忽略前置說明與空行）。"""
    rows: list[OnlineDistro] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.replace("\x00", "").rstrip()
        if not line.strip():
            continue
        if not in_table:
            if re.match(r"\s*NAME\s{2,}", line, re.IGNORECASE):
                in_table = True
            continue
        match = re.match(r"\s*(\S+)\s{2,}(.+)$", line)
        if match:
            rows.append(OnlineDistro(match.group(1), match.group(2).strip()))
    return rows


def validate_new_name(name: str, existing: list[str]) -> None:
    name = name.strip()
    if not name:
        raise ValueError("名稱不可空白")
    if not NAME_PATTERN.match(name):
        raise ValueError("名稱只能使用英文字母、數字、句點、底線、減號，且需以字母或數字開頭")
    for item in existing:
        if name.lower() == item.lower():
            raise ValueError(f"已有同名 instance：{item}")


def validate_target_dir(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("安裝路徑必須是完整路徑")
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"安裝路徑不是資料夾：{path}")
        if any(path.iterdir()):
            raise ValueError(f"安裝路徑必須是空資料夾：{path}")
    elif not path.parent.exists():
        raise ValueError(f"安裝路徑的上層資料夾不存在：{path.parent}")


def default_backup_file(
    backup_root: Path,
    name: str,
    vhd: bool = True,
    now: datetime | None = None,
) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return backup_root / name / f"{name}-{stamp}{'.vhdx' if vhd else '.tar'}"


def _existing_parent(path: Path) -> Path:
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return probe


def free_bytes(path: Path) -> int:
    return shutil.disk_usage(_existing_parent(path)).free


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def check_free_space(path: Path, required: int) -> None:
    if required <= 0:
        return
    free = free_bytes(path)
    if free < required:
        raise ValueError(
            f"磁盤空間不足：需要約 {format_size(required)}，可用 {format_size(free)}"
        )


def list_online() -> list[OnlineDistro]:
    return parse_online_list(_run(["--list", "--online"], timeout=120))


def _prepare_dir(path: Path) -> None:
    validate_target_dir(path)
    path.mkdir(parents=False, exist_ok=True)


def create_instance(plan: NewInstancePlan, stage: Stage | None = None) -> None:
    target = Path(plan.install_dir)
    _prepare_dir(target)
    if plan.source != "online":
        source = Path(plan.file)
        if not source.is_file():
            raise ValueError(f"找不到來源檔案：{source}")
        factor = 1.2 if plan.source == "vhdx" else 2.0
        check_free_space(target, int(source.stat().st_size * factor))
    if plan.source == "online":
        _stage(stage, f"正在安裝 {plan.name}…")
        args = ["--install", "-d", plan.name, "--location", str(target), "--no-launch"]
    elif plan.source == "vhdx":
        _stage(stage, f"正在匯入 {plan.name}…")
        args = ["--import", plan.name, str(target), plan.file, "--version", "2", "--vhd"]
    else:
        _stage(stage, f"正在匯入 {plan.name}…")
        args = ["--import", plan.name, str(target), plan.file, "--version", str(plan.version)]
    try:
        _run(args, timeout=LONG_TIMEOUT)
    except WslError as exc:
        if plan.source == "online":
            raise WslError(
                f"{exc}\n提示：可先安裝，再用 wsl --manage {plan.name} --move \"{target}\" 搬移。"
            ) from exc
        raise


def backup_instance(
    distro: Distro,
    file: str,
    vhd: bool = True,
    stage: Stage | None = None,
) -> None:
    target = Path(file)
    target.parent.mkdir(parents=True, exist_ok=True)
    if distro.vhdx_size:
        check_free_space(target, int(distro.vhdx_size * (1.0 if vhd else 0.6)))
    if vhd:
        _stage(stage, "正在關閉 WSL 子系統…")
        shutdown_all()
    _stage(stage, f"正在匯出 {distro.name}…")
    try:
        _run(
            ["--export", distro.name, str(target), "--format", "vhd" if vhd else "tar"],
            timeout=LONG_TIMEOUT,
        )
    except WslError as exc:
        raise WslError(f"{exc}\n若匯出失敗，請先終止 instance 再試。") from exc


def restore_instance(
    distro: Distro,
    backup_file: str,
    keep_current: bool,
    backup_root: Path,
    stage: Stage | None = None,
) -> str:
    """覆蓋式還原；回傳現況備份路徑（未備份時為空字串）。"""
    backup_path = Path(backup_file)
    if not backup_path.is_file():
        raise ValueError(f"找不到備份檔：{backup_path}")
    vhd = backup_path.suffix.lower() in (".vhdx", ".vhd")
    if not distro.base_path:
        raise ValueError("找不到 instance 的安裝路徑，無法還原")
    target = Path(distro.base_path)
    needed = int(backup_path.stat().st_size * (1.0 if vhd else 2.0))
    check_free_space(target, max(0, needed - distro.vhdx_size))

    _stage(stage, f"正在終止 {distro.name}…")
    try:
        terminate_distro(distro.name)
    except WslError:
        pass

    safety_backup = ""
    if keep_current:
        safety_backup = str(default_backup_file(backup_root, distro.name, vhd=False))
        _stage(stage, "正在備份目前狀態…")
        backup_instance(distro, safety_backup, False, stage)

    _stage(stage, "正在移除現有 instance…")
    _run(["--unregister", distro.name], timeout=120)

    target = Path(distro.base_path)
    target.mkdir(parents=True, exist_ok=True)
    for leftover in target.glob("ext4.vhdx"):
        leftover.unlink(missing_ok=True)

    try:
        _stage(stage, "正在匯入備份…")
        if vhd:
            args = [
                "--import", distro.name, str(target), str(backup_path),
                "--version", "2", "--vhd",
            ]
        else:
            args = [
                "--import", distro.name, str(target), str(backup_path),
                "--version", str(distro.version),
            ]
        _run(args, timeout=LONG_TIMEOUT)
    except Exception:
        if safety_backup:
            _stage(stage, "還原失敗，正在用現況備份回復…")
            try:
                _run(["--unregister", distro.name], timeout=120)
            except WslError:
                pass
            _run(
                ["--import", distro.name, str(target), safety_backup, "--version", str(distro.version)],
                timeout=LONG_TIMEOUT,
            )
        raise
    return safety_backup


def clone_instance(
    source: Distro,
    new_name: str,
    target_dir: str,
    temp_dir: Path,
    stage: Stage | None = None,
) -> None:
    target = Path(target_dir)
    _prepare_dir(target)
    temp_dir.mkdir(parents=True, exist_ok=True)
    if source.vhdx_size:
        check_free_space(target, int(source.vhdx_size * 1.1))
        check_free_space(temp_dir, int(source.vhdx_size * 1.1))
    temp = temp_dir / f"{source.name}-clone-{datetime.now():%Y%m%d-%H%M%S}.tar"
    try:
        _stage(stage, "正在匯出暫存檔…")
        backup_instance(source, str(temp), False, stage)
        _stage(stage, f"正在匯入 {new_name}…")
        _run(
            ["--import", new_name, str(target), str(temp), "--version", str(source.version)],
            timeout=LONG_TIMEOUT,
        )
    except Exception:
        try:
            _run(["--unregister", new_name], timeout=60)
        except WslError:
            pass
        raise
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("刪除暫存檔失敗：%s（%s）", temp, exc)


def delete_instance(
    distro: Distro,
    backup_file: str | None = None,
    stage: Stage | None = None,
) -> None:
    if backup_file:
        vhd = Path(backup_file).suffix.lower() in (".vhdx", ".vhd")
        backup_instance(distro, backup_file, vhd, stage)
    _stage(stage, f"正在終止 {distro.name}…")
    try:
        terminate_distro(distro.name)
    except WslError:
        pass
    _stage(stage, f"正在刪除 {distro.name}…")
    _run(["--unregister", distro.name], timeout=120)
