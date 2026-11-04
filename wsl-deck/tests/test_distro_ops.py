"""distro_ops 純函式測試。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.distro_ops import (
    OnlineDistro,
    check_free_space,
    default_backup_file,
    format_size,
    free_bytes,
    parse_online_list,
    validate_new_name,
    validate_target_dir,
)

ONLINE_EN = (
    "NAME                            FRIENDLY NAME\n"
    "Ubuntu                          Ubuntu\n"
    "Ubuntu-24.04                    Ubuntu 24.04 LTS\n"
)

ONLINE_ZH = (
    "以下是可安装的有效分发的列表。\n"
    "使用“wsl.exe --install <Distro>”安装。\n\n"
    "NAME                            FRIENDLY NAME\n"
    "Ubuntu                          Ubuntu\n"
    "Debian                          Debian GNU/Linux\n"
)


class OnlineListTest(unittest.TestCase):
    def test_english_table(self) -> None:
        self.assertEqual(
            parse_online_list(ONLINE_EN),
            [
                OnlineDistro("Ubuntu", "Ubuntu"),
                OnlineDistro("Ubuntu-24.04", "Ubuntu 24.04 LTS"),
            ],
        )

    def test_chinese_preamble(self) -> None:
        self.assertEqual(
            parse_online_list(ONLINE_ZH),
            [
                OnlineDistro("Ubuntu", "Ubuntu"),
                OnlineDistro("Debian", "Debian GNU/Linux"),
            ],
        )

    def test_null_bytes(self) -> None:
        text = ONLINE_EN.replace("\n", "\x00\n")
        self.assertEqual(len(parse_online_list(text)), 2)

    def test_empty(self) -> None:
        self.assertEqual(parse_online_list(""), [])


class NameValidationTest(unittest.TestCase):
    def test_valid(self) -> None:
        validate_new_name("wsl-deck-test", ["ubuntu"])

    def test_duplicate_case_insensitive(self) -> None:
        with self.assertRaises(ValueError):
            validate_new_name("Ubuntu", ["ubuntu"])

    def test_blank(self) -> None:
        with self.assertRaises(ValueError):
            validate_new_name("  ", [])

    def test_illegal_characters(self) -> None:
        for name in ("a b", r"a\b", "a/b", "-abc", "a:b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_new_name(name, [])


class TargetDirTest(unittest.TestCase):
    def test_missing_parent_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_target_dir(Path("Z:/no-such-parent/child"))

    def test_relative_path_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_target_dir(Path("relative-install"))


class BackupPathTest(unittest.TestCase):
    def test_default_path(self) -> None:
        path = default_backup_file(
            Path(r"D:\backups"), "node22", True, datetime(2026, 10, 30, 12, 34, 56)
        )
        self.assertEqual(
            path,
            Path(r"D:\backups") / "node22" / "node22-20261030-123456.vhdx",
        )

    def test_tar_suffix(self) -> None:
        path = default_backup_file(
            Path(r"D:\backups"), "node22", False, datetime(2026, 10, 30, 12, 34, 56)
        )
        self.assertEqual(path.suffix, ".tar")


class SpaceTest(unittest.TestCase):
    def test_format_size(self) -> None:
        self.assertEqual(format_size(1536), "1.5 KB")

    def test_check_free_space_rejects_oversized_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with self.assertRaises(ValueError):
                check_free_space(folder, free_bytes(folder) + 1)


if __name__ == "__main__":
    unittest.main()
