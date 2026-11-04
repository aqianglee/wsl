"""restic 增量快照：準備、建立、列表、清理、校驗與還原。"""

from __future__ import annotations

import bz2
import json
import logging
import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from app.proxy import ProxyConfig
from app.workspace import SUBDIR_TOOLS, WorkspacePaths
from app.wsl import (
    Distro,
    WslError,
    run_wsl_process,
    start_distro,
    terminate_distro,
)

logger = logging.getLogger(__name__)

Stage = Callable[[str], None]
T = TypeVar("T")

RESTIC_VERSION = "0.17.3"
RESTIC_BINARY_NAME = "restic-linux-amd64"
RESTIC_URL = (
    f"https://github.com/restic/restic/releases/download/v{RESTIC_VERSION}/"
    f"restic_{RESTIC_VERSION}_linux_amd64.bz2"
)
SNAPSHOT_TAG = "wsl-deck"
PASSWORD_BYTES = 32
LONG_TIMEOUT = 3600
QUERY_TIMEOUT = 180
DOWNLOAD_TIMEOUT = 600

BASE_EXCLUDES = (
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/tmp",
    "/var/tmp",
    "/mnt",
    "/media",
    "/lost+found",
)
CONTAINER_EXCLUDES = ("/var/lib/docker", "/var/lib/containerd")
RESTORE_EXCLUDES = (
    *BASE_EXCLUDES,
    "/usr/lib/wsl",
    "/usr/lib/linux-tools",
    "/usr/src/linux-headers-*",
    "/init",
)

KEEP_FLAGS = (
    ("last", "--keep-last"),
    ("daily", "--keep-daily"),
    ("weekly", "--keep-weekly"),
    ("monthly", "--keep-monthly"),
)

TIME_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})")
MOUNT_ESCAPE = re.compile(r"\\([0-7]{3})")


@dataclass(frozen=True)
class Snapshot:
    id: str
    short_id: str
    time: str
    tags: tuple[str, ...]
    host: str


@dataclass(frozen=True)
class RepoStats:
    size: int
    snapshots: int


@dataclass(frozen=True)
class BackupSummary:
    files_new: int = 0
    files_changed: int = 0
    files_processed: int = 0
    data_added: int = 0
    duration: float = 0.0
    snapshot_id: str = ""


def _stage(stage: Stage | None, message: str) -> None:
    logger.info(message)
    if stage is not None:
        stage(message)


def windows_to_wsl_path(path: str | Path) -> str:
    """把 Windows 磁碟機路徑轉成 WSL 的 /mnt/<drive>/... 形式。"""
    text = str(path).strip()
    if text.startswith("\\\\"):
        raise ValueError("快照倉庫不支援 UNC 網路路徑，請改用磁碟機路徑")
    drive, sep, rest = text.partition(":")
    if len(drive) != 1 or not drive.isalpha() or not sep:
        raise ValueError(f"路徑必須以磁碟機開頭：{text}")
    parts = [part for part in rest.replace("\\", "/").split("/") if part]
    suffix = "/".join(parts)
    return f"/mnt/{drive.lower()}/{suffix}" if suffix else f"/mnt/{drive.lower()}"


def restic_binary_path(paths: WorkspacePaths) -> Path:
    return paths.snapshots / SUBDIR_TOOLS / RESTIC_BINARY_NAME


def repo_paths(snapshot_root: Path, name: str) -> tuple[Path, Path]:
    folder = snapshot_root / name
    return folder / "repo", folder / "repo.pass"


def ensure_password(pass_file: Path) -> str:
    """讀取或建立倉庫密碼檔。"""
    if pass_file.is_file():
        text = pass_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    password = secrets.token_hex(PASSWORD_BYTES)
    pass_file.parent.mkdir(parents=True, exist_ok=True)
    pass_file.write_text(password + "\n", encoding="utf-8")
    return password


def _download_and_unpack(url: str, target: Path, proxy: ProxyConfig | None) -> None:
    tmp = target.with_suffix(".bz2")
    args = [
        "curl.exe",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        str(DOWNLOAD_TIMEOUT),
        "-o",
        str(tmp),
        url,
    ]
    if proxy is not None and proxy.enabled:
        args[1:1] = ["--socks5-hostname", f"{proxy.host}:{proxy.port}"]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise WslError("找不到 curl.exe，無法下載 restic") from exc
    except subprocess.TimeoutExpired as exc:
        raise WslError("下載 restic 逾時") from exc
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip()
        raise WslError(f"下載 restic 失敗：{message}")
    try:
        data = bz2.decompress(tmp.read_bytes())
    except (OSError, ValueError) as exc:
        raise WslError(f"解壓 restic 失敗：{exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)
    target.write_bytes(data)
    try:
        target.chmod(0o755)
    except OSError as exc:
        logger.warning("設定 restic 執行權限失敗：%s", exc)
    logger.info("已下載 restic %s：%s", RESTIC_VERSION, target)


def ensure_restic(
    paths: WorkspacePaths,
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> Path:
    """取得 restic 靜態二進位；不存在時自動下載一次。"""
    binary = restic_binary_path(paths)
    if binary.is_file() and binary.stat().st_size > 0:
        return binary
    binary.parent.mkdir(parents=True, exist_ok=True)
    _stage(stage, "正在下載 restic（首次使用只需一次）…")
    _download_and_unpack(RESTIC_URL, binary, proxy)
    _stage(stage, "restic 已就緒")
    return binary


def _restic_command(
    distro_name: str,
    binary: Path,
    repo: Path,
    pass_file: Path,
    *args: str,
) -> list[str]:
    return [
        "-d",
        distro_name,
        "-u",
        "root",
        "--",
        "env",
        f"RESTIC_PASSWORD_FILE={windows_to_wsl_path(pass_file)}",
        windows_to_wsl_path(binary),
        "-r",
        windows_to_wsl_path(repo),
        *args,
    ]


def _repo_ready(repo: Path) -> bool:
    return (repo / "config").is_file()


def _check(code: int, stdout: str, stderr: str, allow_codes: tuple[int, ...] = (0,)) -> str:
    if code in allow_codes:
        return stdout
    message = stderr or stdout or f"restic 退出碼 {code}"
    raise WslError(message)


def parse_snapshots_json(text: str) -> list[Snapshot]:
    """解析 restic snapshots --json（略過不合格式的項目）。"""
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        raise WslError(f"restic 快照列表格式錯誤：{exc}") from exc
    if not isinstance(data, list):
        raise WslError("restic 快照列表格式錯誤：預期陣列")

    result: list[Snapshot] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        snapshot_id = str(item.get("id", "")).strip()
        if not snapshot_id:
            continue
        tags = item.get("tags") or []
        result.append(
            Snapshot(
                id=snapshot_id,
                short_id=str(item.get("short_id", "") or snapshot_id[:8]),
                time=str(item.get("time", "")),
                tags=tuple(str(tag) for tag in tags if str(tag).strip()),
                host=str(item.get("hostname", "")),
            )
        )
    result.sort(key=lambda item: item.time, reverse=True)
    return result


def parse_stats_json(text: str) -> RepoStats:
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise WslError(f"restic 統計格式錯誤：{exc}") from exc
    if not isinstance(data, dict):
        raise WslError("restic 統計格式錯誤：預期物件")
    return RepoStats(
        size=int(data.get("total_size", 0) or 0),
        snapshots=int(data.get("snapshots_count", 0) or 0),
    )


def parse_backup_json(text: str) -> BackupSummary:
    """取最後一筆 summary 訊息。"""
    summary: dict = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("message_type") == "summary":
            summary = item
    return BackupSummary(
        files_new=int(summary.get("files_new", 0) or 0),
        files_changed=int(summary.get("files_changed", 0) or 0),
        files_processed=int(summary.get("total_files_processed", 0) or 0),
        data_added=int(summary.get("data_added", 0) or 0),
        duration=float(summary.get("total_duration", 0.0) or 0.0),
        snapshot_id=str(summary.get("snapshot_id", "")),
    )


def format_snapshot_time(text: str) -> str:
    match = TIME_PATTERN.search(text or "")
    if not match:
        return text or "—"
    return f"{match.group(1)} {match.group(2)}"


def keep_arguments(keep: dict[str, int]) -> list[str]:
    """把保留策略轉成 restic forget 參數；全部為 0 時報錯。"""
    args: list[str] = []
    for key, flag in KEEP_FLAGS:
        value = int(keep.get(key, 0) or 0)
        if value > 0:
            args.extend([flag, str(value)])
    if not args:
        raise ValueError("保留策略至少要保留一份快照")
    return args


def exclude_paths(include_container_data: bool) -> list[str]:
    paths = list(BASE_EXCLUDES)
    if not include_container_data:
        paths.extend(CONTAINER_EXCLUDES)
    return paths


def backup_arguments(host: str, tag: str, include_container_data: bool) -> list[str]:
    args = [
        "backup",
        "/",
        "--one-file-system",
        "--tag",
        SNAPSHOT_TAG,
        "--host",
        host,
        "--json",
    ]
    if tag.strip():
        args.extend(["--tag", tag.strip()])
    for path in exclude_paths(include_container_data):
        args.extend(["--exclude", path])
    return args


def _unescape_mount_path(text: str) -> str:
    return MOUNT_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), text)


def parse_read_only_mounts(text: str) -> list[str]:
    """從 /proc/mounts 收集只讀掛載點（忽略根目錄）。"""
    result: list[str] = []
    for line in (text or "").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        mount_point = _unescape_mount_path(fields[1])
        if "ro" not in fields[3].split(",") or mount_point == "/":
            continue
        if mount_point not in result:
            result.append(mount_point)
    return result


def read_only_mounts(distro_name: str) -> list[str]:
    """讀取 instance 目前的只讀掛載點。"""
    code, out, err = run_wsl_process(
        ["-d", distro_name, "-u", "root", "--", "cat", "/proc/mounts"],
        timeout=QUERY_TIMEOUT,
    )
    _check(code, out, err)
    return parse_read_only_mounts(out)


def restore_arguments(
    snapshot_id: str,
    target_path: str,
    extra_excludes: tuple[str, ...] = (),
) -> list[str]:
    """組裝 restic restore 參數。

    restic 的 --include 與 --exclude 互斥：整機還原用 --exclude 跳過只讀掛載，
    指定路徑還原則用 --include。
    """
    if target_path != "/":
        return [
            "restore",
            snapshot_id,
            "--target",
            "/",
            "--include",
            target_path,
            "--overwrite",
            "always",
        ]

    excludes = list(RESTORE_EXCLUDES)
    for path in extra_excludes:
        if path and path not in excludes:
            excludes.append(path)
    args = ["restore", snapshot_id, "--target", "/", "--overwrite", "always"]
    for path in excludes:
        args.extend(["--exclude", path])
    return args


def readonly_only_errors(text: str) -> bool:
    """判斷 restic 的錯誤是否全為只讀檔案系統（可安全略過）。"""
    lines = [
        line
        for line in (text or "").splitlines()
        if line.strip() and "ignoring error for" in line
    ]
    return bool(lines) and all("read-only file system" in line for line in lines)


def _with_running(distro: Distro, stage: Stage | None, action: Callable[[], T]) -> T:
    """instance 停止時暫時啟動，執行後終止回原狀。"""
    started = False
    if not distro.running:
        _stage(stage, f"正在啟動 {distro.name}…")
        start_distro(distro.name)
        started = True
    try:
        return action()
    finally:
        if started:
            _stage(stage, f"正在終止 {distro.name}…")
            try:
                terminate_distro(distro.name)
            except WslError:
                logger.warning("終止 %s 失敗", distro.name)


def _prepare(
    distro_name: str,
    paths: WorkspacePaths,
    proxy: ProxyConfig | None,
    stage: Stage | None,
) -> tuple[Path, Path, Path]:
    repo, pass_file = repo_paths(paths.snapshots, distro_name)
    repo.mkdir(parents=True, exist_ok=True)
    ensure_password(pass_file)
    binary = ensure_restic(paths, proxy, stage)
    return binary, repo, pass_file


def create_snapshot(
    distro: Distro,
    paths: WorkspacePaths,
    proxy: ProxyConfig | None = None,
    include_container_data: bool = False,
    tag: str = "",
    stage: Stage | None = None,
) -> BackupSummary:
    """建立一份增量快照。"""
    binary, repo, pass_file = _prepare(distro.name, paths, proxy, stage)

    def action() -> str:
        if not _repo_ready(repo):
            _stage(stage, "正在初始化快照倉庫…")
            code, out, err = run_wsl_process(
                _restic_command(distro.name, binary, repo, pass_file, "init"),
                timeout=QUERY_TIMEOUT,
            )
            _check(code, out, err)
        _stage(stage, "正在掃描並寫入快照（首次較久）…")
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name,
                binary,
                repo,
                pass_file,
                *backup_arguments(distro.name, tag, include_container_data),
            ),
            timeout=LONG_TIMEOUT,
        )
        if code == 3:
            logger.warning("restic 有部分檔案無法讀取，已略過")
        _check(code, out, err, allow_codes=(0, 3))
        return out

    text = _with_running(distro, stage, action)
    summary = parse_backup_json(text)
    _stage(
        stage,
        f"快照完成：處理 {summary.files_processed} 個檔案，"
        f"新增 {summary.files_new}／變更 {summary.files_changed}",
    )
    return summary


def load_state(
    distro: Distro,
    paths: WorkspacePaths,
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> tuple[list[Snapshot], RepoStats]:
    """一次啟動讀取快照列表與倉庫統計。"""
    repo, pass_file = repo_paths(paths.snapshots, distro.name)
    if not _repo_ready(repo):
        return [], RepoStats(0, 0)
    binary = ensure_restic(paths, proxy, stage)

    def action() -> tuple[list[Snapshot], RepoStats]:
        code, out, err = run_wsl_process(
            _restic_command(distro.name, binary, repo, pass_file, "snapshots", "--json"),
            timeout=QUERY_TIMEOUT,
        )
        snapshots = parse_snapshots_json(_check(code, out, err))
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name, binary, repo, pass_file, "stats", "--json", "--mode", "raw-data"
            ),
            timeout=QUERY_TIMEOUT,
        )
        return snapshots, parse_stats_json(_check(code, out, err))

    return _with_running(distro, stage, action)


def forget_snapshot(
    distro: Distro,
    paths: WorkspacePaths,
    snapshot_id: str,
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> str:
    """刪除單一快照並回收空間。"""
    binary, repo, pass_file = _prepare(distro.name, paths, proxy, stage)

    def action() -> str:
        _stage(stage, "正在刪除快照並回收空間…")
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name, binary, repo, pass_file, "forget", snapshot_id, "--prune"
            ),
            timeout=LONG_TIMEOUT,
        )
        return _check(code, out, err)

    return _with_running(distro, stage, action)


def forget_by_policy(
    distro: Distro,
    paths: WorkspacePaths,
    keep: dict[str, int],
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> str:
    """依保留策略清理舊快照。"""
    arguments = keep_arguments(keep)
    binary, repo, pass_file = _prepare(distro.name, paths, proxy, stage)

    def action() -> str:
        _stage(stage, "正在依保留策略清理…")
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name, binary, repo, pass_file, "forget", *arguments, "--prune"
            ),
            timeout=LONG_TIMEOUT,
        )
        return _check(code, out, err)

    return _with_running(distro, stage, action)


def check_repo(
    distro: Distro,
    paths: WorkspacePaths,
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> str:
    """校驗倉庫（抽樣讀取 5% 資料）。"""
    binary, repo, pass_file = _prepare(distro.name, paths, proxy, stage)

    def action() -> str:
        _stage(stage, "正在校驗快照倉庫…")
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name,
                binary,
                repo,
                pass_file,
                "check",
                "--read-data-subset=5%",
            ),
            timeout=LONG_TIMEOUT,
        )
        return _check(code, out, err)

    return _with_running(distro, stage, action)


def restore_path(
    distro: Distro,
    paths: WorkspacePaths,
    snapshot_id: str,
    target_path: str,
    proxy: ProxyConfig | None = None,
    stage: Stage | None = None,
) -> str:
    """把快照中的指定路徑還原回 instance（不刪除多餘檔案）。"""
    path = target_path.strip() or "/"
    if not path.startswith("/"):
        raise ValueError("還原路徑必須以 / 開頭")
    binary, repo, pass_file = _prepare(distro.name, paths, proxy, stage)

    def action() -> str:
        excludes = tuple(read_only_mounts(distro.name))
        _stage(stage, f"正在還原 {path}…")
        code, out, err = run_wsl_process(
            _restic_command(
                distro.name,
                binary,
                repo,
                pass_file,
                *restore_arguments(snapshot_id, path, excludes),
            ),
            timeout=LONG_TIMEOUT,
        )
        detail = err or out
        if code != 0 and readonly_only_errors(detail):
            count = sum(
                1 for line in detail.splitlines() if "read-only file system" in line
            )
            logger.warning("還原時略過 %d 個唯讀掛載點", count)
            _stage(stage, f"已還原，略過 {count} 個唯讀掛載點")
            return out
        return _check(code, out, err)

    return _with_running(distro, stage, action)
