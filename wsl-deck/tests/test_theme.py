"""主題純函式測試（不建立 QApplication）。"""

from __future__ import annotations

import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from app.ui.theme import build_dark_palette, resolve_mode


class ResolveModeTest(unittest.TestCase):
    def test_explicit_modes(self) -> None:
        self.assertEqual(resolve_mode("dark", Qt.ColorScheme.Light), "dark")
        self.assertEqual(resolve_mode("light", Qt.ColorScheme.Dark), "light")

    def test_system_follows_scheme(self) -> None:
        self.assertEqual(resolve_mode("system", Qt.ColorScheme.Dark), "dark")
        self.assertEqual(resolve_mode("system", Qt.ColorScheme.Light), "light")
        self.assertEqual(resolve_mode("system", Qt.ColorScheme.Unknown), "light")

    def test_dark_palette_roles(self) -> None:
        palette = build_dark_palette()
        self.assertEqual(palette.color(QPalette.Window), QColor("#202225"))
        self.assertEqual(palette.color(QPalette.WindowText), QColor("#e6e6e6"))


if __name__ == "__main__":
    unittest.main()
