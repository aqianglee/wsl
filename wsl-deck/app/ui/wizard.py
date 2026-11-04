"""新增 Instance 三步精靈。"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from app.distro_ops import (
    NewInstancePlan,
    list_online,
    validate_new_name,
    validate_target_dir,
)
from app.ui.cursors import refresh_cursor
from app.ui.workers import TaskWorker

FILE_SUFFIX = re.compile(r"\.(tar\.gz|tar\.xz|tar|vhdx|vhd)$", re.IGNORECASE)
SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class NewInstanceWizard(QWizard):
    def __init__(self, distro_root: Path, existing_names: list[str], parent=None):
        super().__init__(parent)
        self._distro_root = distro_root
        self._existing = existing_names
        self._workers: set[TaskWorker] = set()
        self._online_loaded = False
        self._loading_online = False
        self._dir_edited = False
        self.plan: NewInstancePlan | None = None

        self.setWindowTitle("新增 Instance")
        self.setMinimumSize(680, 470)
        self.setWizardStyle(QWizard.ModernStyle)
        self.setButtonText(QWizard.NextButton, "下一步")
        self.setButtonText(QWizard.BackButton, "上一步")
        self.setButtonText(QWizard.FinishButton, "開始安裝")
        self.setButtonText(QWizard.CancelButton, "取消")

        self._build_pages()
        self.currentIdChanged.connect(self._on_page_changed)
        self._source_group.buttonToggled.connect(self._on_source_toggled)
        self._configure_source()

    # ---------- 頁面 ----------

    def _build_pages(self) -> None:
        self._source_page = self._build_source_page()
        self._selection_page = self._build_selection_page()
        self._naming_page = self._build_naming_page()
        self.setPage(0, self._source_page)
        self.setPage(1, self._selection_page)
        self.setPage(2, self._naming_page)

    def _build_source_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("步驟 1／3：選擇來源")
        page.setSubTitle(
            "官方發行版從線上清單安裝；rootfs／tar 與 VHDX 由本機檔案匯入。"
        )
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._source_group = QButtonGroup(self)
        self._online_radio = QRadioButton("官方發行版（wsl --install）", page)
        self._tar_radio = QRadioButton("rootfs／tar 檔案（wsl --import）", page)
        self._vhdx_radio = QRadioButton("VHDX 虛擬磁碟（wsl --import --vhd）", page)
        self._online_radio.setChecked(True)
        for index, button in enumerate(
            (self._online_radio, self._tar_radio, self._vhdx_radio)
        ):
            self._source_group.addButton(button, index)
            layout.addWidget(button)

        hints = QLabel(
            "官方來源會使用 --location 安裝到指定目錄；檔案來源的安裝目錄必須是空資料夾。",
            page,
        )
        hints.setWordWrap(True)
        hints.setStyleSheet("color: gray;")
        layout.addWidget(hints)
        layout.addStretch(1)
        return page

    def _build_selection_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("步驟 2／3：選擇發行版或檔案")
        page.setSubTitle("官方來源請從清單挑選；檔案來源請選擇 rootfs、tar 或 VHDX。")
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        self._online_panel = QWidget(page)
        online_layout = QVBoxLayout(self._online_panel)
        online_layout.setContentsMargins(0, 0, 0, 0)
        online_layout.setSpacing(6)

        row = QHBoxLayout()
        self._online_list = QListWidget(self._online_panel)
        self._online_list.setMinimumHeight(210)
        self._refresh_btn = QPushButton("重新整理", self._online_panel)
        self._refresh_btn.setMinimumHeight(32)
        self._refresh_btn.clicked.connect(lambda: self._load_online(force=True))
        refresh_cursor(self._refresh_btn)
        row.addWidget(self._online_list, 1)
        row.addWidget(self._refresh_btn)
        online_layout.addLayout(row)

        self._online_status = QLabel("", self._online_panel)
        self._online_status.setWordWrap(True)
        online_layout.addWidget(self._online_status)
        layout.addWidget(self._online_panel)

        self._file_panel = QWidget(page)
        file_layout = QHBoxLayout(self._file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)
        self._file_edit = QLineEdit(self._file_panel)
        self._file_edit.setReadOnly(True)
        self._file_edit.setPlaceholderText("尚未選擇檔案")
        self._browse_file_btn = QPushButton("瀏覽…", self._file_panel)
        self._browse_file_btn.setMinimumHeight(32)
        self._browse_file_btn.clicked.connect(self._browse_file)
        refresh_cursor(self._browse_file_btn)
        file_layout.addWidget(self._file_edit, 1)
        file_layout.addWidget(self._browse_file_btn)
        layout.addWidget(self._file_panel)

        self._selection_error = QLabel("", page)
        self._selection_error.setStyleSheet("color: #c0392b;")
        self._selection_error.setWordWrap(True)
        layout.addWidget(self._selection_error)
        layout.addStretch(1)

        self._online_list.currentItemChanged.connect(self._on_online_selected)
        return page

    def _build_naming_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("步驟 3／3：命名與位置")
        page.setSubTitle("安裝目錄必須是空資料夾；tar 可選 WSL 1／2，VHDX 固定 WSL 2。")
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit(page)
        self._name_edit.textEdited.connect(self._on_name_edited)
        self._name_note = QLabel("官方名稱固定，不可修改。", page)
        self._name_note.setStyleSheet("color: gray;")
        name_box = QVBoxLayout()
        name_box.setSpacing(2)
        name_box.addWidget(self._name_edit)
        name_box.addWidget(self._name_note)
        name_widget = QWidget(page)
        name_widget.setLayout(name_box)
        form.addRow("名稱", name_widget)

        self._dir_edit = QLineEdit(page)
        self._dir_edit.textEdited.connect(self._on_dir_edited)
        self._dir_browse = QPushButton("瀏覽…", page)
        self._dir_browse.setMinimumHeight(32)
        self._dir_browse.clicked.connect(self._browse_dir)
        refresh_cursor(self._dir_browse)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(self._dir_browse)
        dir_widget = QWidget(page)
        dir_widget.setLayout(dir_row)
        form.addRow("安裝目錄", dir_widget)

        self._version_label = QLabel("版本", page)
        self._version_combo = QComboBox(page)
        self._version_combo.addItem("WSL 2", 2)
        self._version_combo.addItem("WSL 1", 1)
        form.addRow(self._version_label, self._version_combo)

        layout.addLayout(form)

        self._name_error = QLabel("", page)
        self._name_error.setStyleSheet("color: #c0392b;")
        self._name_error.setWordWrap(True)
        layout.addWidget(self._name_error)
        layout.addStretch(1)
        return page

    # ---------- 來源切換 ----------

    def _source(self) -> str:
        if self._online_radio.isChecked():
            return "online"
        if self._tar_radio.isChecked():
            return "tar"
        return "vhdx"

    def _on_source_toggled(self, button, checked: bool) -> None:
        if not checked:
            return
        self._selection_error.clear()
        self._name_error.clear()
        self._file_edit.clear()
        self._dir_edited = False
        self._configure_source()
        self._update_defaults()

    def _configure_source(self) -> None:
        source = self._source()
        is_online = source == "online"
        self._online_panel.setVisible(is_online)
        self._file_panel.setVisible(not is_online)
        self._refresh_btn.setVisible(is_online)

        self._name_note.setVisible(is_online)
        self._name_edit.setReadOnly(is_online)

        show_version = source != "online"
        self._version_label.setVisible(show_version)
        self._version_combo.setVisible(show_version)
        if source == "tar":
            self._version_combo.setEnabled(True)
        elif source == "vhdx":
            self._version_combo.setEnabled(False)
            self._version_combo.setCurrentIndex(0)
        else:
            self._version_combo.setCurrentIndex(0)
        refresh_cursor(self._refresh_btn)
        refresh_cursor(self._dir_browse)

    def _update_defaults(self) -> None:
        source = self._source()
        if source == "online":
            current = self._online_list.currentItem()
            name = current.data(Qt.UserRole) if current is not None else ""
            self._name_edit.setText(name)
        elif self._file_edit.text():
            self._apply_file_name(self._file_edit.text())
        else:
            self._name_edit.clear()
        self._update_dir_default()

    def _update_dir_default(self) -> None:
        if self._dir_edited:
            return
        name = self._name_edit.text().strip()
        self._dir_edit.setText(str(self._distro_root / name) if name else "")

    # ---------- 線上清單 ----------

    def _on_page_changed(self, page_id: int) -> None:
        self._configure_source()
        if page_id == 1 and self._source() == "online" and not self._online_loaded:
            self._load_online()

    def _load_online(self, force: bool = False) -> None:
        if self._loading_online or (self._online_loaded and not force):
            return
        self._loading_online = True
        self._online_status.setText("正在讀取線上清單…")
        self._online_status.setStyleSheet("color: gray;")
        worker = TaskWorker(list_online)
        self._workers.add(worker)
        worker.signals.finished.connect(self._on_online_loaded)
        worker.signals.failed.connect(self._on_online_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_online_loaded(self, distros: list) -> None:
        self._loading_online = False
        self._online_loaded = True
        self._online_list.clear()
        for distro in distros:
            item = QListWidgetItem(f"{distro.name}　{distro.friendly_name}")
            item.setData(Qt.UserRole, distro.name)
            self._online_list.addItem(item)
        if distros:
            self._online_status.setText(f"共 {len(distros)} 個官方發行版。")
            self._online_status.setStyleSheet("color: gray;")
            self._online_list.setCurrentRow(0)
        else:
            self._online_status.setText("線上清單為空，請稍後重新整理。")
            self._online_status.setStyleSheet("color: #c0392b;")

    def _on_online_failed(self, message: str) -> None:
        self._loading_online = False
        self._online_status.setText(f"讀取線上清單失敗：{message}")
        self._online_status.setStyleSheet("color: #c0392b;")

    def _on_online_selected(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None or self._source() != "online":
            return
        name = str(current.data(Qt.UserRole))
        self._name_edit.setText(name)
        self._update_dir_default()

    # ---------- 檔案與名稱 ----------

    def _browse_file(self) -> None:
        if self._source() == "tar":
            file_filter = "rootfs／tar (*.tar *.tar.gz *.tar.xz);;所有檔案 (*)"
        else:
            file_filter = "VHDX (*.vhdx *.vhd);;所有檔案 (*)"
        path, _selected = QFileDialog.getOpenFileName(
            self, "選擇來源檔案", str(self._distro_root), file_filter
        )
        if not path:
            return
        self._file_edit.setText(path)
        self._apply_file_name(path)
        self._update_dir_default()

    def _apply_file_name(self, path: str) -> None:
        stem = FILE_SUFFIX.sub("", Path(path).name)
        stem = SAFE_CHARS.sub("-", stem).strip("-._")
        if not stem or not stem[0].isalnum():
            stem = f"wsl-{stem}" if stem else "new-instance"
        self._name_edit.setText(stem)

    def _on_name_edited(self, text: str) -> None:
        self._name_error.clear()
        self._update_dir_default()

    def _on_dir_edited(self, _text: str) -> None:
        self._dir_edited = True

    def _browse_dir(self) -> None:
        start = self._dir_edit.text().strip() or str(self._distro_root)
        path = QFileDialog.getExistingDirectory(self, "選擇安裝目錄", start)
        if path:
            self._dir_edit.setText(path)
            self._dir_edited = True
            self._name_error.clear()

    # ---------- 驗證與完成 ----------

    def validateCurrentPage(self) -> bool:
        page = self.currentPage()
        if page is self._selection_page:
            if self._source() == "online":
                if self._online_list.currentItem() is None:
                    self._selection_error.setText("請選擇一個發行版")
                    return False
            else:
                if not Path(self._file_edit.text()).is_file():
                    self._selection_error.setText("請選擇存在的 tar／VHDX 檔案")
                    return False
            self._selection_error.clear()

        if page is self._naming_page:
            try:
                validate_new_name(self._name_edit.text(), self._existing)
                install_dir = self._dir_edit.text().strip()
                if not install_dir:
                    raise ValueError("安裝目錄不可空白")
                validate_target_dir(Path(install_dir))
            except ValueError as exc:
                self._name_error.setText(str(exc))
                return False
            self._name_error.clear()
        return True

    def accept(self) -> None:
        self.plan = NewInstancePlan(
            source=self._source(),
            name=self._name_edit.text().strip(),
            install_dir=self._dir_edit.text().strip(),
            file=self._file_edit.text().strip(),
            version=int(self._version_combo.currentData() or 2),
        )
        super().accept()
