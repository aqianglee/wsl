"""主題：Fusion 樣式與深／淺色 palette。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEME_MODES = ("system", "dark", "light")


def resolve_mode(mode: str, scheme: Qt.ColorScheme) -> str:
    if mode == "dark":
        return "dark"
    if mode == "light":
        return "light"
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def build_dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor("#202225")
    base = QColor("#1b1d20")
    text = QColor("#e6e6e6")
    button = QColor("#2b2e31")
    highlight = QColor("#2d7ff9")
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, window)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, button)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.ToolTipBase, base)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Mid, QColor("#3a3d40"))
    palette.setColor(QPalette.Midlight, QColor("#333639"))
    palette.setColor(QPalette.Dark, QColor("#2a2d30"))
    palette.setColor(QPalette.PlaceholderText, QColor("#8b9096"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#6f7478"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#6f7478"))
    return palette


def apply_theme(app: QApplication, mode: str) -> str:
    """套用主題並回傳實際結果（dark／light）。"""
    applied = resolve_mode(mode, app.styleHints().colorScheme())
    app.setStyle("Fusion")
    if applied == "dark":
        app.setPalette(build_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
    return applied
