"""卡片牆：依視窗寬度自動換行。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from app.ui.instance_card import InstanceCard
from app.wsl import Distro

CARD_MIN_WIDTH = 280


class CardWall(QWidget):
    open_requested = Signal(object)
    start_requested = Signal(str)
    stop_requested = Signal(str)
    terminal_requested = Signal(str)
    linux_files_requested = Signal(str)
    install_dir_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(16)
        self._cards: dict[str, InstanceCard] = {}
        self._order: list[str] = []
        self._columns = 0
        self._scroll: QScrollArea | None = None

    def attach_scroll(self, scroll: QScrollArea) -> None:
        """以 scroll viewport 寬度排版，避免被卡片最小寬度撐死。"""
        self._scroll = scroll
        scroll.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if (
            self._scroll is not None
            and obj is self._scroll.viewport()
            and event.type() == QEvent.Resize
        ):
            self._relayout(force=True)
        return super().eventFilter(obj, event)

    def _available_width(self) -> int:
        if self._scroll is not None:
            width = self._scroll.viewport().width()
            if width > 0:
                return width
        return self.width()

    def set_distros(
        self,
        distros: list[Distro],
        system_check: Callable[[str], bool],
    ) -> None:
        names = {distro.name for distro in distros}

        for name in list(self._cards):
            if name not in names:
                card = self._cards.pop(name)
                card.setParent(None)
                card.deleteLater()

        for distro in distros:
            card = self._cards.get(distro.name)
            if card is None:
                card = InstanceCard(distro, system_check(distro.name), self)
                card.open_requested.connect(self.open_requested)
                card.start_requested.connect(self.start_requested)
                card.stop_requested.connect(self.stop_requested)
                card.terminal_requested.connect(self.terminal_requested)
                card.linux_files_requested.connect(self.linux_files_requested)
                card.install_dir_requested.connect(self.install_dir_requested)
                self._cards[distro.name] = card
            else:
                card.update_distro(distro, system_check(distro.name))

        self._order = [distro.name for distro in distros]
        self._relayout(force=True)

    def _relayout(self, force: bool = False) -> None:
        width = self._available_width()
        if width <= 0:
            return
        columns = max(1, width // CARD_MIN_WIDTH)
        if not force and columns == self._columns:
            return
        self._columns = columns
        if self._scroll is not None and self.width() != width:
            self.setFixedWidth(width)

        while self._layout.count():
            self._layout.takeAt(0)

        for index, name in enumerate(self._order):
            self._layout.addWidget(
                self._cards[name],
                index // columns,
                index % columns,
                alignment=Qt.AlignTop,
            )

        rows = (len(self._order) + columns - 1) // columns
        for row in range(max(rows + 1, self._layout.rowCount())):
            self._layout.setRowStretch(row, 0)
        self._layout.setRowStretch(rows, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout()
