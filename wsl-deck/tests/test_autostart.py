"""開機自啟測試（不觸碰真實註冊表）。"""

from __future__ import annotations

import unittest

from app import autostart


class AutostartTest(unittest.TestCase):
    def test_build_run_command_quotes_exe(self) -> None:
        self.assertEqual(
            autostart.build_run_command(r"C:\Program Files\WSL Deck\WSL Deck.exe"),
            '"C:\\Program Files\\WSL Deck\\WSL Deck.exe" --silent',
        )

    def test_dev_mode_not_supported(self) -> None:
        self.assertFalse(autostart.is_supported())
        self.assertFalse(autostart.is_enabled())

    def test_set_enabled_raises_in_dev(self) -> None:
        with self.assertRaises(RuntimeError):
            autostart.set_enabled(True)


if __name__ == "__main__":
    unittest.main()
