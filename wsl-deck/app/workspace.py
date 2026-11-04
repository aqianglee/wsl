"""工作目錄骨架：instances／backups／snapshots 與路徑推導。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SUBDIR_INSTANCES = "instances"
SUBDIR_BACKUPS = "backups"
SUBDIR_SNAPSHOTS = "snapshots"
SUBDIR_TOOLS = "_tools"

WORKSPACE_SUBDIRS = (SUBDIR_INSTANCES, SUBDIR_BACKUPS, SUBDIR_SNAPSHOTS)


@dataclass(frozen=True)
class WorkspacePaths:
    """工作目錄下的三個同層路徑。"""

    root: Path
    instances: Path
    backups: Path
    snapshots: Path

    def skeleton_dirs(self) -> tuple[Path, ...]:
        """骨架本體：工作目錄 + 三個子目錄。"""
        return (self.root, *(self.root / name for name in WORKSPACE_SUBDIRS))


def workspace_paths(
    workspace_root: Path,
    backup_root: Path | None = None,
    snapshot_root: Path | None = None,
) -> WorkspacePaths:
    """推導三個子目錄；備份／快照可各自覆寫。"""
    root = Path(workspace_root)
    return WorkspacePaths(
        root=root,
        instances=root / SUBDIR_INSTANCES,
        backups=Path(backup_root) if backup_root else root / SUBDIR_BACKUPS,
        snapshots=Path(snapshot_root) if snapshot_root else root / SUBDIR_SNAPSHOTS,
    )


def ensure_workspace(paths: WorkspacePaths) -> list[Path]:
    """建立骨架與工具目錄；回傳本次實際建立的目錄。"""
    candidates = list(paths.skeleton_dirs())
    for extra in (paths.backups, paths.snapshots, paths.snapshots / SUBDIR_TOOLS):
        if extra not in candidates:
            candidates.append(extra)

    created: list[Path] = []
    for folder in candidates:
        if folder.is_dir():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        created.append(folder)
    if created:
        logger.info("已建立工作目錄骨架：%s", "、".join(str(item) for item in created))
    return created
