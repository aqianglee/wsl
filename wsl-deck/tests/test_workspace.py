"""工作目錄骨架測試。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.workspace import WorkspacePaths, ensure_workspace, workspace_paths


class WorkspacePathsTest(unittest.TestCase):
    def test_default_paths(self) -> None:
        paths = workspace_paths(Path(r"D:\VirtualMachiles\wsl"))
        self.assertEqual(paths.instances, Path(r"D:\VirtualMachiles\wsl\instances"))
        self.assertEqual(paths.backups, Path(r"D:\VirtualMachiles\wsl\backups"))
        self.assertEqual(paths.snapshots, Path(r"D:\VirtualMachiles\wsl\snapshots"))

    def test_override_backups_and_snapshots(self) -> None:
        paths = workspace_paths(
            Path(r"D:\ws"),
            Path(r"E:\backups"),
            Path(r"E:\snapshots"),
        )
        self.assertEqual(paths.instances, Path(r"D:\ws\instances"))
        self.assertEqual(paths.backups, Path(r"E:\backups"))
        self.assertEqual(paths.snapshots, Path(r"E:\snapshots"))

    def test_skeleton_dirs(self) -> None:
        paths = WorkspacePaths(
            root=Path(r"D:\ws"),
            instances=Path(r"D:\ws\instances"),
            backups=Path(r"D:\ws\backups"),
            snapshots=Path(r"D:\ws\snapshots"),
        )
        self.assertEqual(
            paths.skeleton_dirs(),
            (
                Path(r"D:\ws"),
                Path(r"D:\ws\instances"),
                Path(r"D:\ws\backups"),
                Path(r"D:\ws\snapshots"),
            ),
        )


class EnsureWorkspaceTest(unittest.TestCase):
    def test_creates_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            paths = workspace_paths(root)
            created = ensure_workspace(paths)
            for folder in paths.skeleton_dirs():
                self.assertTrue(folder.is_dir())
            self.assertTrue((paths.snapshots / "_tools").is_dir())
            self.assertEqual(len(created), 5)

    def test_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = workspace_paths(Path(tmp) / "ws")
            ensure_workspace(paths)
            self.assertEqual(ensure_workspace(paths), [])


if __name__ == "__main__":
    unittest.main()
