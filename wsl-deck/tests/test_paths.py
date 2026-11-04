"""執行路徑測試。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app import paths


class AppDirTest(unittest.TestCase):
    def test_dev_dir_is_project_root(self) -> None:
        self.assertEqual(paths.app_dir(), Path(__file__).resolve().parent.parent)

    def test_frozen_dir_is_exe_parent(self) -> None:
        with patch.object(paths.sys, "frozen", True, create=True), \
             patch.object(paths.sys, "executable", r"C:\Apps\WSL Deck\WSL Deck.exe"):
            self.assertEqual(paths.app_dir(), Path(r"C:\Apps\WSL Deck"))

    def test_is_frozen_default_false(self) -> None:
        self.assertFalse(paths.is_frozen())


if __name__ == "__main__":
    unittest.main()
