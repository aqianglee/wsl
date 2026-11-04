"""備份／還原／複製／刪除對話框。"""

from __future__ import annotations

import re
from datetime import datetime
from itertools import chain
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
)

from app.config import Config
from app.distro_ops import default_backup_file, validate_new_name, validate_target_dir
from app.ui.dialog_base import DialogBase
from app.wsl import Distro

INVALID_FILENAME = re.compile(r'[\\/:*?"<>|]')


class BackupDialog(DialogBase):
    """備份設定；file_path 與 vhd 於 accept 後有效。"""

    def __init__(self, distro: Distro, config: Config, parent=None):
        super().__init__("備份 Instance", parent)
        self.file_path = ""
        self.vhd = True

        backup_root = config.resolve_path(config.get("backup_root", "backups"))
        folder = backup_root / distro.name
        self._folder_edit = QLineEdit(str(folder), self)
        self._folder_edit.textChanged.connect(self._update_preview)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._name_edit = QLineEdit(f"{distro.name}-{stamp}", self)
        self._name_edit.textChanged.connect(self._update_preview)

        self._format_combo = QComboBox(self)
        self._format_combo.addItem("VHDX（建議）", True)
        self._format_combo.addItem("TAR", False)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        self._form.addRow("資料夾", self._row_with_button(
            self._folder_edit, "瀏覽…", self._browse_folder))
        self._form.addRow("檔名", self._name_edit)
        self._form.addRow("格式", self._format_combo)

        self._preview = QLabel("", self)
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet("color: gray;")
        self._layout.insertWidget(self._layout.count() - 1, self._preview)

        self._format_note = self.add_info("")
        self._update_note()

        self.set_ok_text("開始備份")
        self._ok_btn.clicked.connect(self._on_accept)
        self._update_preview()

    def _on_format_changed(self, _index: int) -> None:
        self.vhd = bool(self._format_combo.currentData())
        self._update_note()
        self._update_preview()

    def _update_note(self) -> None:
        if self._format_combo.currentData():
            text = (
                "VHDX 備份會先執行 wsl --shutdown，"
                "所有執行中的 instance（含 docker-desktop）都會被終止。"
            )
        else:
            text = "TAR 可在 instance 執行中匯出，不需要關閉 WSL。"
        self._format_note.setText(text)

    def _filename(self) -> str:
        base = re.sub(r"\.(vhdx|tar)$", "", self._name_edit.text().strip(), flags=re.I)
        return f"{base}{'.vhdx' if self.vhd else '.tar'}"

    def _update_preview(self) -> None:
        folder = self._folder_edit.text().strip()
        name = self._filename()
        self._preview.setText(f"將寫入：{Path(folder) / name}" if folder and name else "")

    def _browse_folder(self) -> None:
        start = self._folder_edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "選擇備份資料夾", start)
        if path:
            self._folder_edit.setText(path)

    def _on_accept(self) -> None:
        folder_text = self._folder_edit.text().strip()
        base = re.sub(r"\.(vhdx|tar)$", "", self._name_edit.text().strip(), flags=re.I)
        if not folder_text:
            self.show_error("請選擇備份資料夾")
            return
        if not base:
            self.show_error("檔名不可空白")
            return
        if INVALID_FILENAME.search(base):
            self.show_error('檔名不可包含 \\ / : * ? " < > |')
            return
        folder = Path(folder_text)
        if folder.exists() and not folder.is_dir():
            self.show_error("備份路徑不是資料夾")
            return
        if not folder.exists() and not folder.parent.exists():
            self.show_error(f"上層資料夾不存在：{folder.parent}")
            return

        self.vhd = bool(self._format_combo.currentData())
        self.file_path = str(folder / self._filename())
        super().accept()


class RestoreDialog(DialogBase):
    """還原設定；file_path 與 keep_current 於 accept 後有效。"""

    def __init__(self, distro: Distro, config: Config, parent=None):
        super().__init__("還原 Instance", parent)
        self.file_path = ""
        self.keep_current = True
        self._distro = distro

        backup_root = config.resolve_path(config.get("backup_root", "backups"))
        self._folder = backup_root / distro.name

        self._file_edit = QLineEdit(self)
        self._file_edit.setPlaceholderText("選擇 .vhdx 或 .tar 備份檔")
        self._form.addRow("備份檔", self._row_with_button(
            self._file_edit, "瀏覽…", self._browse_file))

        self._keep_check = QCheckBox("先備份目前狀態（建議）", self)
        self._keep_check.setChecked(True)
        self._form.addRow("", self._keep_check)

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText(distro.name)
        self._form.addRow("輸入 instance 名稱", self._name_edit)

        if distro.running:
            self.add_info("instance 執行中，還原前會先終止它。")
        self.add_info("還原為覆蓋式：現有內容會被備份檔取代。")
        self.add_info("還原完成後，instance 會保持停止狀態。")

        self.set_ok_text("開始還原")
        self._ok_btn.clicked.connect(self._on_accept)
        self._preselect_latest()

    def _preselect_latest(self) -> None:
        if not self._folder.is_dir():
            return
        candidates = sorted(
            chain(self._folder.glob("*.vhdx"), self._folder.glob("*.tar")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            self._file_edit.setText(str(candidates[0]))

    def _browse_file(self) -> None:
        start = str(self._folder) if self._folder.exists() else str(Path.home())
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "選擇備份檔",
            start,
            "備份檔 (*.vhdx *.tar *.tar.gz *.tar.xz);;所有檔案 (*)",
        )
        if path:
            self._file_edit.setText(path)

    def _on_accept(self) -> None:
        path = self._file_edit.text().strip()
        if not Path(path).is_file():
            self.show_error("請選擇存在的備份檔")
            return
        if self._name_edit.text().strip() != self._distro.name:
            self.show_error("名稱不符，請輸入要還原的 instance 名稱")
            return
        self.file_path = path
        self.keep_current = self._keep_check.isChecked()
        super().accept()


class CloneDialog(DialogBase):
    """複製設定；new_name 與 target_dir 於 accept 後有效。"""

    def __init__(
        self,
        distro: Distro,
        config: Config,
        existing_names: list[str],
        parent=None,
    ):
        super().__init__("複製 Instance", parent)
        self.new_name = ""
        self.target_dir = ""
        self._existing = existing_names
        self._dir_edited = False
        self._distro_root = config.resolve_path(config.get("distro_root", "."))

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText(f"{distro.name}-copy")
        self._name_edit.textEdited.connect(self._on_name_edited)
        self._form.addRow("新名稱", self._name_edit)

        self._dir_edit = QLineEdit(self)
        self._dir_edit.textEdited.connect(self._on_dir_edited)
        self._form.addRow("目標目錄", self._row_with_button(
            self._dir_edit, "瀏覽…", self._browse_dir))

        self.add_info(f"來源磁盤大小：{distro.size_gb:.2f} GB")
        self.add_info("複製不會帶上端口規則；需要時請在詳情頁重新建立。")

        self.set_ok_text("開始複製")
        self._ok_btn.clicked.connect(self._on_accept)

    def _on_name_edited(self, text: str) -> None:
        self.show_error("")
        if not self._dir_edited:
            name = text.strip()
            self._dir_edit.setText(str(self._distro_root / name) if name else "")

    def _on_dir_edited(self, _text: str) -> None:
        self._dir_edited = True

    def _browse_dir(self) -> None:
        start = self._dir_edit.text().strip() or str(self._distro_root)
        path = QFileDialog.getExistingDirectory(self, "選擇目標目錄", start)
        if path:
            self._dir_edit.setText(path)
            self._dir_edited = True

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        target = self._dir_edit.text().strip()
        try:
            validate_new_name(name, self._existing)
            if not target:
                raise ValueError("目標目錄不可空白")
            validate_target_dir(Path(target))
        except ValueError as exc:
            self.show_error(str(exc))
            return
        self.new_name = name
        self.target_dir = target
        super().accept()


class DeleteDialog(DialogBase):
    """刪除確認；backup_file 於 accept 後有效（未勾選備份時為 None）。"""

    def __init__(self, distro: Distro, config: Config, parent=None):
        super().__init__("刪除 Instance", parent)
        self.backup_file: str | None = None
        self._distro = distro

        warning = QLabel(
            "刪除後無法復原，instance 內的資料會一併移除。", self
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #c0392b; font-weight: bold;")
        self._layout.insertWidget(1, warning)

        backup_root = config.resolve_path(config.get("backup_root", "backups"))
        self._default_backup = default_backup_file(backup_root, distro.name, False)

        self._backup_check = QCheckBox("先備份再刪除（建議）", self)
        self._backup_check.setChecked(True)
        self._backup_check.toggled.connect(self._on_backup_toggled)
        self._form.addRow("", self._backup_check)

        self._backup_label = QLabel(str(self._default_backup), self)
        self._backup_label.setWordWrap(True)
        self._backup_label.setStyleSheet("color: gray;")
        self._form.addRow("", self._backup_label)

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText(distro.name)
        self._form.addRow("輸入 instance 名稱", self._name_edit)

        self.set_ok_text("刪除")
        self._ok_btn.clicked.connect(self._on_accept)

    def _on_backup_toggled(self, checked: bool) -> None:
        self._backup_label.setVisible(checked)

    def _on_accept(self) -> None:
        if self._name_edit.text().strip() != self._distro.name:
            self.show_error("名稱不符，請輸入要刪除的 instance 名稱")
            return
        self.backup_file = str(self._default_backup) if self._backup_check.isChecked() else None
        super().accept()
