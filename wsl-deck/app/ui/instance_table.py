"""表格牆：五列（圖標／名稱／IP／大小／操作），列高 48px。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.cursors import refresh_cursor
from app.ui.icons import (
    heart_pixmap,
    install_dir_icon,
    linux_archive_icon,
    power_start_icon,
    power_stop_icon,
    prohibition_pixmap,
    terminal_icon,
)
from app.ui.instance_card import (
    ICON_BUTTON_SIZE,
    ICON_SIZE,
    SYSTEM_REASON,
)
from app.wsl import Distro

ROW_HEIGHT = 48
HEADER_HEIGHT = 32
ICON_COLUMN_WIDTH = 40
IP_COLUMN_WIDTH = 150
SIZE_COLUMN_WIDTH = 100
COLUMN_PADDING = 12
BUTTONS_WIDTH = 348
OPS_COLUMN_WIDTH = BUTTONS_WIDTH + COLUMN_PADDING * 2
TABLE_MARGIN = 12

ROW_STYLE = f"""
QFrame#instanceRow {{
    background: transparent;
    border-bottom: 1px solid rgba(128, 128, 128, 45);
}}
QFrame#instanceRow:hover {{
    background: palette(midlight);
}}
QWidget#tableHeader {{
    background: transparent;
}}
QFrame#headerLine {{
    background: rgba(128, 128, 128, 65);
}}
QFrame#columnDivider {{
    background: rgba(128, 128, 128, 56);
}}
QLabel#tableHeaderText {{
    color: #7f8c8d;
}}
QToolButton#rowIcon {{
    border: none;
    background: transparent;
    padding: 0;
    margin: 0;
    outline: none;
}}
QToolButton#rowIcon:hover {{
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}}
QPushButton#rowAction {{
    border: 1px solid palette(mid);
    border-radius: 7px;
    background: palette(button);
    padding: 4px 10px;
}}
QPushButton#rowAction:hover {{
    background: palette(midlight);
    border-color: #4a90e2;
}}
QToolButton#rowIcon:disabled, QPushButton#rowAction:disabled {{
    color: #9aa0a6;
    background: transparent;
    border: none;
}}
"""


def _header_font() -> QFont:
    font = QFont()
    font.setPointSize(10)
    font.setBold(True)
    return font


def _column_divider(parent: QWidget) -> QFrame:
    divider = QFrame(parent)
    divider.setObjectName("columnDivider")
    divider.setFixedWidth(1)
    divider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    return divider


class InstanceRow(QFrame):
    open_requested = Signal(object)
    start_requested = Signal(str)
    stop_requested = Signal(str)
    terminal_requested = Signal(str)
    linux_files_requested = Signal(str)
    install_dir_requested = Signal(str)

    def __init__(self, distro: Distro, is_system: bool, parent=None):
        super().__init__(parent)
        self._distro = distro
        self._system = is_system
        self.setObjectName("instanceRow")
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(ROW_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._build()
        self.update_distro(distro, is_system)

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_column_divider(self))

        self._icon = QLabel(self)
        self._icon.setFixedSize(ICON_COLUMN_WIDTH, ROW_HEIGHT)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)
        layout.addWidget(_column_divider(self))

        self._name = QLabel(self)
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        self._name.setFont(name_font)
        self._name.setContentsMargins(COLUMN_PADDING, 0, COLUMN_PADDING, 0)
        layout.addWidget(self._name, 1)
        layout.addWidget(_column_divider(self))

        self._ip = QLabel(self)
        ip_font = QFont("Consolas")
        ip_font.setPointSize(10)
        self._ip.setFont(ip_font)
        self._ip.setFixedWidth(IP_COLUMN_WIDTH)
        self._ip.setAlignment(Qt.AlignCenter)
        self._ip.setStyleSheet("color: #555;")
        layout.addWidget(self._ip)
        layout.addWidget(_column_divider(self))

        self._size = QLabel(self)
        size_font = QFont()
        size_font.setPointSize(10)
        self._size.setFont(size_font)
        self._size.setFixedWidth(SIZE_COLUMN_WIDTH)
        self._size.setAlignment(Qt.AlignCenter)
        self._size.setStyleSheet("color: #555;")
        layout.addWidget(self._size)
        layout.addWidget(_column_divider(self))

        ops = QHBoxLayout()
        ops.setContentsMargins(COLUMN_PADDING, 0, COLUMN_PADDING, 0)
        ops.setSpacing(8)

        self._detail_btn = QPushButton("詳情", self)
        self._detail_btn.setObjectName("rowAction")
        self._detail_btn.setFixedSize(64, ICON_BUTTON_SIZE)
        self._detail_btn.clicked.connect(self._emit_open)
        ops.addWidget(self._detail_btn)

        self._power_btn = QToolButton(self)
        self._power_btn.setObjectName("rowIcon")
        self._power_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._power_btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._power_btn.clicked.connect(self._on_power)
        ops.addWidget(self._power_btn)

        self._terminal_btn = QToolButton(self)
        self._terminal_btn.setObjectName("rowIcon")
        self._terminal_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._terminal_btn.setIcon(terminal_icon())
        self._terminal_btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._terminal_btn.setToolTip("開啟終端")
        self._terminal_btn.clicked.connect(
            lambda: self.terminal_requested.emit(self._distro.name)
        )
        ops.addWidget(self._terminal_btn)

        self._linux_btn = QPushButton("Linux 檔案", self)
        self._linux_btn.setObjectName("rowAction")
        self._linux_btn.setIcon(linux_archive_icon())
        self._linux_btn.setIconSize(QSize(16, 16))
        self._linux_btn.setFixedSize(100, ICON_BUTTON_SIZE)
        self._linux_btn.clicked.connect(
            lambda: self.linux_files_requested.emit(self._distro.name)
        )
        ops.addWidget(self._linux_btn)

        self._install_btn = QPushButton("安裝目錄", self)
        self._install_btn.setObjectName("rowAction")
        self._install_btn.setIcon(install_dir_icon())
        self._install_btn.setIconSize(QSize(16, 16))
        self._install_btn.setFixedSize(100, ICON_BUTTON_SIZE)
        self._install_btn.clicked.connect(
            lambda: self.install_dir_requested.emit(self._distro.base_path)
        )
        ops.addWidget(self._install_btn)

        holder = QWidget(self)
        holder.setFixedWidth(OPS_COLUMN_WIDTH)
        holder.setLayout(ops)
        layout.addWidget(holder, 0, Qt.AlignVCenter)
        layout.addWidget(_column_divider(self))
        self._buttons = (
            self._detail_btn,
            self._power_btn,
            self._terminal_btn,
            self._linux_btn,
            self._install_btn,
        )

    def update_distro(self, distro: Distro, is_system: bool) -> None:
        self._distro = distro
        self._system = is_system
        self._name.setText(distro.name)

        if distro.ip:
            self._ip.setText(distro.ip)
        elif distro.running:
            self._ip.setText("…")
        else:
            self._ip.setText("-")

        self._size.setText(f"{distro.size_gb:.1f} GB")

        if is_system:
            self._icon.setPixmap(prohibition_pixmap())
            self._icon.setToolTip(SYSTEM_REASON)
        elif distro.is_default:
            self._icon.setPixmap(heart_pixmap())
            self._icon.setToolTip("預設 instance")
        else:
            self._icon.setPixmap(QPixmap())
            self._icon.setToolTip("")

        if distro.running:
            self._power_btn.setIcon(power_stop_icon())
            self._power_btn.setToolTip("執行中，點擊終止")
        else:
            self._power_btn.setIcon(power_start_icon())
            self._power_btn.setToolTip("已停止，點擊啟動")

        enabled = not is_system
        for button in self._buttons:
            button.setEnabled(enabled)
        self._install_btn.setEnabled(enabled and bool(distro.base_path))

        if is_system:
            for button in self._buttons:
                button.setToolTip(SYSTEM_REASON)
            self.setToolTip(SYSTEM_REASON)
        else:
            self._linux_btn.setToolTip("開啟 Linux 檔案")
            self._install_btn.setToolTip(distro.base_path or "找不到安裝目錄")
            self.setToolTip(f"{distro.name}\n{distro.base_path}")

        for button in self._buttons:
            refresh_cursor(button)

    def _emit_open(self) -> None:
        self.open_requested.emit(self._distro)

    def _on_power(self) -> None:
        if self._system:
            return
        if self._distro.running:
            self.stop_requested.emit(self._distro.name)
        else:
            self.start_requested.emit(self._distro.name)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self._distro)
        super().mousePressEvent(event)


class InstanceTable(QWidget):
    open_requested = Signal(object)
    start_requested = Signal(str)
    stop_requested = Signal(str)
    terminal_requested = Signal(str)
    linux_files_requested = Signal(str)
    install_dir_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, InstanceRow] = {}
        self._order: list[str] = []
        self.setStyleSheet(ROW_STYLE)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(self)
        header.setObjectName("tableHeader")
        header.setFixedHeight(HEADER_HEIGHT)
        self._header_outer = QVBoxLayout(header)
        self._header_outer.setContentsMargins(TABLE_MARGIN, 0, TABLE_MARGIN, 0)
        self._header_outer.setSpacing(0)

        header_row = QWidget(header)
        self._header_layout = QHBoxLayout(header_row)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(0)

        self._header_layout.addWidget(_column_divider(header_row))

        spacer = QLabel(header_row)
        spacer.setFixedWidth(ICON_COLUMN_WIDTH)
        self._header_layout.addWidget(spacer)
        self._header_layout.addWidget(_column_divider(header_row))

        name_title = QLabel("名稱", header_row)
        name_title.setObjectName("tableHeaderText")
        name_title.setFont(_header_font())
        name_title.setAlignment(Qt.AlignCenter)
        self._header_layout.addWidget(name_title, 1)
        self._header_layout.addWidget(_column_divider(header_row))

        ip_title = QLabel("IP", header_row)
        ip_title.setObjectName("tableHeaderText")
        ip_title.setFont(_header_font())
        ip_title.setAlignment(Qt.AlignCenter)
        ip_title.setFixedWidth(IP_COLUMN_WIDTH)
        self._header_layout.addWidget(ip_title)
        self._header_layout.addWidget(_column_divider(header_row))

        size_title = QLabel("大小", header_row)
        size_title.setObjectName("tableHeaderText")
        size_title.setFont(_header_font())
        size_title.setAlignment(Qt.AlignCenter)
        size_title.setFixedWidth(SIZE_COLUMN_WIDTH)
        self._header_layout.addWidget(size_title)
        self._header_layout.addWidget(_column_divider(header_row))

        ops_title = QLabel("操作", header_row)
        ops_title.setObjectName("tableHeaderText")
        ops_title.setFont(_header_font())
        ops_title.setAlignment(Qt.AlignCenter)
        ops_title.setFixedWidth(OPS_COLUMN_WIDTH)
        self._header_layout.addWidget(ops_title)
        self._header_layout.addWidget(_column_divider(header_row))

        header_top = QFrame(header)
        header_top.setObjectName("headerLine")
        header_top.setFixedHeight(1)
        self._header_outer.addWidget(header_top)
        self._header_outer.addWidget(header_row, 1)
        header_line = QFrame(header)
        header_line.setObjectName("headerLine")
        header_line.setFixedHeight(1)
        self._header_outer.addWidget(header_line)
        layout.addWidget(header)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.verticalScrollBar().rangeChanged.connect(
            self._schedule_header_margin
        )
        self._scroll.verticalScrollBar().installEventFilter(self)

        self._host = QWidget(self._scroll)
        self._rows_layout = QVBoxLayout(self._host)
        self._rows_layout.setContentsMargins(TABLE_MARGIN, 0, TABLE_MARGIN, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(self._host)
        layout.addWidget(self._scroll, 1)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._scroll.verticalScrollBar() and event.type() in (
            QEvent.Show,
            QEvent.Hide,
        ):
            self._schedule_header_margin()
        return super().eventFilter(obj, event)

    def _schedule_header_margin(self, *_args) -> None:
        QTimer.singleShot(0, self._apply_header_margin)

    def _apply_header_margin(self) -> None:
        bar = self._scroll.verticalScrollBar()
        gutter = bar.width() if bar.isVisible() else 0
        self._header_outer.setContentsMargins(
            TABLE_MARGIN, 0, TABLE_MARGIN + gutter, 0
        )

    def set_distros(
        self,
        distros: list[Distro],
        system_check: Callable[[str], bool],
    ) -> None:
        names = {distro.name for distro in distros}

        for name in list(self._rows):
            if name not in names:
                row = self._rows.pop(name)
                row.setParent(None)
                row.deleteLater()

        for distro in distros:
            row = self._rows.get(distro.name)
            if row is None:
                row = InstanceRow(distro, system_check(distro.name), self._host)
                row.open_requested.connect(self.open_requested)
                row.start_requested.connect(self.start_requested)
                row.stop_requested.connect(self.stop_requested)
                row.terminal_requested.connect(self.terminal_requested)
                row.linux_files_requested.connect(self.linux_files_requested)
                row.install_dir_requested.connect(self.install_dir_requested)
                self._rows[distro.name] = row
            else:
                row.update_distro(distro, system_check(distro.name))

        self._order = [distro.name for distro in distros]
        self._relayout()
        self._schedule_header_margin()

    def update_distro_info(
        self, name: str, distro: Distro, is_system: bool
    ) -> None:
        """輕量更新單行（如 IP 回填），不重新排版。"""
        row = self._rows.get(name)
        if row is not None:
            row.update_distro(distro, is_system)

    def _relayout(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().show()

        for name in self._order:
            self._rows_layout.addWidget(self._rows[name])
        self._rows_layout.addStretch(1)
