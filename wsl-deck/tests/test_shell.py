"""終端啟動參數測試。"""

from __future__ import annotations

import unittest

from app.shell import terminal_args


class TerminalArgsTest(unittest.TestCase):
    def test_title_uses_user_and_instance(self) -> None:
        args = terminal_args("ubuntu", "kyo")
        self.assertEqual(
            args[:5],
            ["wt.exe", "new-tab", "--title", "kyo@ubuntu", "--suppressApplicationTitle"],
        )

    def test_title_falls_back_to_instance(self) -> None:
        args = terminal_args("ubuntu", "")
        self.assertEqual(args[3], "ubuntu")

    def test_runs_wsl_for_instance(self) -> None:
        self.assertEqual(terminal_args("ubuntu", "kyo")[-3:], ["wsl.exe", "-d", "ubuntu"])


if __name__ == "__main__":
    unittest.main()
