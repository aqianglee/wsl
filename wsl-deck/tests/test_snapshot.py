"""restic 快照純函式測試。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.snapshot import (
    BASE_EXCLUDES,
    CONTAINER_EXCLUDES,
    RESTORE_EXCLUDES,
    backup_arguments,
    ensure_password,
    exclude_paths,
    format_snapshot_time,
    keep_arguments,
    parse_backup_json,
    parse_read_only_mounts,
    parse_snapshots_json,
    parse_stats_json,
    readonly_only_errors,
    repo_paths,
    restore_arguments,
    windows_to_wsl_path,
)

SNAPSHOTS_JSON = json.dumps(
    [
        {
            "id": "b" * 64,
            "short_id": "bbbbbbbb",
            "time": "2026-11-04T10:00:00.123456789+08:00",
            "tags": ["wsl-deck"],
            "hostname": "Ubuntu-26.04",
        },
        {
            "id": "a" * 64,
            "short_id": "aaaaaaaa",
            "time": "2026-11-03T10:00:00.123456789+08:00",
            "tags": ["wsl-deck", "升級前"],
            "hostname": "Ubuntu-26.04",
        },
        {"id": "", "short_id": "cccccccc", "time": "2026-11-02T10:00:00"},
    ]
)

BACKUP_JSON = "\n".join(
    [
        '{"message_type":"status","percent_done":0.25}',
        '{"message_type":"status","percent_done":0.75}',
        (
            '{"message_type":"summary","files_new":12,"files_changed":3,'
            '"total_files_processed":120,"data_added":2048,'
            '"total_duration":9.5,"snapshot_id":"deadbeef"}'
        ),
    ]
)

STATS_JSON = '{"total_size": 1048576, "total_file_count": 42, "snapshots_count": 3}'

MOUNTS_TEXT = "\n".join(
    [
        "/dev/sdb /usr/src/linux-headers-6.18.54.1-microsoft-standard-WSL2 ext4 ro,relatime 0 0",
        "/dev/sdb /usr/lib/linux-tools/6.18.54.1-microsoft-standard-WSL2 ext4 ro,relatime 0 0",
        "drivers /usr/lib/wsl/drivers 9p ro,nosuid,nodev 0 0",
        "/dev/sdd / ext4 rw,relatime,discard,errors=remount-ro,data=ordered 0 0",
        "none /run/credentials/getty@tty1.service tmpfs ro,nosuid 0 0",
        "tmpfs /tmp/with\\040space tmpfs ro 0 0",
    ]
)


class PathTest(unittest.TestCase):
    def test_drive_path(self) -> None:
        self.assertEqual(
            windows_to_wsl_path(Path(r"D:\VirtualMachiles\wsl\snapshots")),
            "/mnt/d/VirtualMachiles/wsl/snapshots",
        )

    def test_spaces_and_forward_slashes(self) -> None:
        self.assertEqual(windows_to_wsl_path("E:/some where/repo"), "/mnt/e/some where/repo")

    def test_drive_root(self) -> None:
        self.assertEqual(windows_to_wsl_path("D:\\"), "/mnt/d")

    def test_unc_rejected(self) -> None:
        with self.assertRaises(ValueError):
            windows_to_wsl_path(r"\\server\share\repo")

    def test_relative_rejected(self) -> None:
        with self.assertRaises(ValueError):
            windows_to_wsl_path("snapshots/repo")

    def test_repo_paths(self) -> None:
        repo, password = repo_paths(Path(r"D:\ws\snapshots"), "node22")
        self.assertEqual(repo, Path(r"D:\ws\snapshots\node22\repo"))
        self.assertEqual(password, Path(r"D:\ws\snapshots\node22\repo.pass"))


class PasswordTest(unittest.TestCase):
    def test_creates_and_reuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pass_file = Path(tmp) / "repo.pass"
            first = ensure_password(pass_file)
            self.assertEqual(len(first), 64)
            self.assertEqual(first, ensure_password(pass_file))

    def test_blank_file_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pass_file = Path(tmp) / "repo.pass"
            pass_file.write_text("   \n", encoding="utf-8")
            password = ensure_password(pass_file)
            self.assertEqual(len(password), 64)


class ParseTest(unittest.TestCase):
    def test_snapshots_sorted_and_filtered(self) -> None:
        snapshots = parse_snapshots_json(SNAPSHOTS_JSON)
        self.assertEqual([item.short_id for item in snapshots], ["bbbbbbbb", "aaaaaaaa"])
        self.assertEqual(snapshots[1].tags, ("wsl-deck", "升級前"))

    def test_snapshots_empty(self) -> None:
        self.assertEqual(parse_snapshots_json(""), [])

    def test_snapshots_invalid(self) -> None:
        with self.assertRaises(Exception):
            parse_snapshots_json("{not json}")

    def test_stats(self) -> None:
        stats = parse_stats_json(STATS_JSON)
        self.assertEqual(stats.size, 1048576)
        self.assertEqual(stats.snapshots, 3)

    def test_backup_summary(self) -> None:
        summary = parse_backup_json(BACKUP_JSON)
        self.assertEqual(summary.files_new, 12)
        self.assertEqual(summary.files_changed, 3)
        self.assertEqual(summary.files_processed, 120)
        self.assertEqual(summary.data_added, 2048)
        self.assertAlmostEqual(summary.duration, 9.5)
        self.assertEqual(summary.snapshot_id, "deadbeef")

    def test_backup_without_summary(self) -> None:
        self.assertEqual(parse_backup_json("").files_processed, 0)

    def test_format_time(self) -> None:
        self.assertEqual(
            format_snapshot_time("2026-11-04T10:00:00.123456789+08:00"),
            "2026-11-04 10:00:00",
        )
        self.assertEqual(format_snapshot_time(""), "—")


class ArgumentsTest(unittest.TestCase):
    def test_keep_arguments(self) -> None:
        args = keep_arguments({"last": 10, "daily": 0, "weekly": 4, "monthly": 6})
        self.assertEqual(
            args,
            ["--keep-last", "10", "--keep-weekly", "4", "--keep-monthly", "6"],
        )

    def test_keep_all_zero_rejected(self) -> None:
        with self.assertRaises(ValueError):
            keep_arguments({"last": 0, "daily": 0, "weekly": 0, "monthly": 0})

    def test_excludes_default(self) -> None:
        paths = exclude_paths(False)
        self.assertIn("/proc", paths)
        for path in CONTAINER_EXCLUDES:
            self.assertIn(path, paths)
        self.assertEqual(len(paths), len(BASE_EXCLUDES) + len(CONTAINER_EXCLUDES))

    def test_excludes_include_container_data(self) -> None:
        paths = exclude_paths(True)
        self.assertEqual(paths, list(BASE_EXCLUDES))

    def test_backup_arguments(self) -> None:
        args = backup_arguments("node22", "升級前", False)
        self.assertEqual(args[0], "backup")
        self.assertIn("--one-file-system", args)
        self.assertIn("--json", args)
        self.assertIn("升級前", args)
        self.assertIn("/var/lib/docker", args)
        self.assertNotIn("", args)

    def test_backup_arguments_without_tag(self) -> None:
        args = backup_arguments("node22", "   ", True)
        self.assertEqual(args.count("--tag"), 1)


class RestoreArgumentsTest(unittest.TestCase):
    def test_restore_excludes_cover_wsl_mounts(self) -> None:
        for path in (
            "/usr/lib/wsl",
            "/usr/lib/linux-tools",
            "/usr/src/linux-headers-*",
            "/init",
        ):
            self.assertIn(path, RESTORE_EXCLUDES)
        for path in BASE_EXCLUDES:
            self.assertIn(path, RESTORE_EXCLUDES)

    def test_parse_read_only_mounts(self) -> None:
        mounts = parse_read_only_mounts(MOUNTS_TEXT)
        self.assertEqual(
            mounts,
            [
                "/usr/src/linux-headers-6.18.54.1-microsoft-standard-WSL2",
                "/usr/lib/linux-tools/6.18.54.1-microsoft-standard-WSL2",
                "/usr/lib/wsl/drivers",
                "/run/credentials/getty@tty1.service",
                "/tmp/with space",
            ],
        )

    def test_parse_mounts_ignores_root_and_remount_ro(self) -> None:
        mounts = parse_read_only_mounts("/dev/sdd / ext4 rw,errors=remount-ro 0 0")
        self.assertEqual(mounts, [])

    def test_parse_mounts_handles_empty(self) -> None:
        self.assertEqual(parse_read_only_mounts(""), [])

    def test_restore_arguments_whole_root(self) -> None:
        args = restore_arguments("cafe", "/", ("/usr/lib/wsl/drivers",))
        self.assertEqual(args[0], "restore")
        self.assertEqual(args[1], "cafe")
        self.assertNotIn("--include", args)
        self.assertIn("--overwrite", args)
        self.assertIn("always", args)
        self.assertEqual(args.count("--exclude"), len(RESTORE_EXCLUDES) + 1)
        self.assertIn("/usr/lib/wsl/drivers", args)

    def test_restore_arguments_whole_root_deduplicates(self) -> None:
        args = restore_arguments("cafe", "/", ("/usr/lib/wsl",))
        self.assertEqual(args.count("--exclude"), len(RESTORE_EXCLUDES))

    def test_restore_arguments_subpath(self) -> None:
        args = restore_arguments("cafe", "/etc/hosts", ("/usr/lib/wsl",))
        self.assertIn("--include", args)
        self.assertIn("/etc/hosts", args)
        self.assertNotIn("--exclude", args)

    def test_readonly_only_errors(self) -> None:
        text = (
            "ignoring error for /usr/lib/wsl/drivers: lchown: read-only file system\n"
            "Fatal: There were 1 errors"
        )
        self.assertTrue(readonly_only_errors(text))
        self.assertFalse(readonly_only_errors("ignoring error for /a: permission denied"))
        self.assertFalse(
            readonly_only_errors(
                text + "\nignoring error for /b: input/output error"
            )
        )
        self.assertFalse(readonly_only_errors(""))


if __name__ == "__main__":
    unittest.main()
