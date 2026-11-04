"""快照管理：建立、列表、還原、刪除、清理與校驗。"""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.config import Config
from app.distro_ops import format_size
from app.proxy import current_proxy
from app.snapshot import (
    BackupSummary,
    RepoStats,
    Snapshot,
    check_repo,
    create_snapshot,
    forget_by_policy,
    forget_snapshot,
    format_snapshot_time,
    load_state,
    restore_path,
)
from app.ui.app_icon import app_icon
from app.ui.cursors import refresh_cursor
from app.ui.dialog_base import DialogBase
from app.ui.progress import OperationDialog
from app.ui.workers import TaskWorker
from app.wsl import Distro

BUTTON_HEIGHT = 32
BUTTON_WIDTH = 96


class SnapshotDialog(QDialog):
    """單一 instance 的快照倉庫管理。"""

    def __init__(self, distro: Distro, config: Config, parent=None):
        super().__init__(parent)
        self._distro = distro
        self._config = config
        self._paths = config.workspace()
        self._proxy = current_proxy()
        self._snapshots: list[Snapshot] = []
        self._workers: set[TaskWorker] = set()

        self.setWindowTitle(f"快照 — {distro.name}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(720, 460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._build()
        QTimer.singleShot(0, self._refresh)

    # ---------- 介面 ----------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel(f"{self._distro.name} 的增量快照", self)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self._stats_label = QLabel("", self)
        self._stats_label.setStyleSheet("color: gray;")
        self._stats_label.setWordWrap(True)
        layout.addWidget(self._stats_label)

        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["時間", "備註／標籤", "ID"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(40)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self._table, 1)

        self._error = QLabel("", self)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._create_btn = QPushButton("立即快照", self)
        self._restore_btn = QPushButton("還原檔案", self)
        self._delete_btn = QPushButton("刪除", self)
        self._clean_btn = QPushButton("清理", self)
        self._check_btn = QPushButton("校驗", self)
        self._folder_btn = QPushButton("開啟資料夾", self)
        self._close_btn = QPushButton("關閉", self)

        self._action_buttons = (
            self._create_btn,
            self._restore_btn,
            self._delete_btn,
            self._clean_btn,
            self._check_btn,
            self._folder_btn,
        )
        for button in (*self._action_buttons, self._close_btn):
            button.setFixedHeight(BUTTON_HEIGHT)
            refresh_cursor(button)
        for button in self._action_buttons:
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self._close_btn)
        layout.addLayout(buttons)

        self._create_btn.clicked.connect(self._on_create)
        self._restore_btn.clicked.connect(self._on_restore)
        self._delete_btn.clicked.connect(self._on_delete)
        self._clean_btn.clicked.connect(self._on_clean)
        self._check_btn.clicked.connect(self._on_check)
        self._folder_btn.clicked.connect(self._on_open_folder)
        self._close_btn.clicked.connect(self.accept)
        self._update_buttons()

    def _selected(self) -> Snapshot | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._snapshots):
            return None
        return self._snapshots[row]

    def _update_buttons(self) -> None:
        selected = self._selected() is not None
        self._restore_btn.setEnabled(selected)
        self._delete_btn.setEnabled(selected)

    # ---------- 資料 ----------

    def _refresh(self) -> None:
        self._error.setText("")
        repo = self._paths.snapshots / self._distro.name
        self._stats_label.setText(f"倉庫：{repo}｜讀取中…")
        self._run("讀取快照", self._load, self._on_loaded)
        if self._error.text():
            self._stats_label.setText(f"倉庫：{repo}｜讀取失敗")

    def _load(self, stage=None):
        return load_state(self._distro, self._paths, self._proxy, stage)

    def _on_loaded(self, result) -> None:
        snapshots, stats = result
        self._snapshots = list(snapshots)
        self._fill_table()
        self._update_stats(stats)
        self._update_buttons()

    def _fill_table(self) -> None:
        self._table.setRowCount(len(self._snapshots))
        for row, snapshot in enumerate(self._snapshots):
            time_item = QTableWidgetItem(format_snapshot_time(snapshot.time))
            time_item.setData(Qt.UserRole, snapshot.id)
            tags = "、".join(snapshot.tags) if snapshot.tags else "—"
            self._table.setItem(row, 0, time_item)
            self._table.setItem(row, 1, QTableWidgetItem(tags))
            self._table.setItem(row, 2, QTableWidgetItem(snapshot.short_id))
        if self._snapshots:
            self._table.selectRow(0)

    def _update_stats(self, stats: RepoStats) -> None:
        repo = self._paths.snapshots / self._distro.name
        self._stats_label.setText(
            f"倉庫：{repo}｜已用 {format_size(stats.size)}｜{len(self._snapshots)} 個快照"
        )

    # ---------- 操作 ----------

    def _on_create(self) -> None:
        dialog = SnapshotCreateDialog(self._distro, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._run(
            "建立快照",
            partial(
                create_snapshot,
                self._distro,
                self._paths,
                self._proxy,
                dialog.include_container_data,
                dialog.tag,
            ),
            self._on_created,
        )

    def _on_created(self, summary: BackupSummary) -> None:
        message = (
            f"快照完成。\n\n處理檔案：{summary.files_processed}\n"
            f"新增：{summary.files_new}｜變更：{summary.files_changed}\n"
            f"寫入資料：{format_size(summary.data_added)}\n"
            f"耗時：{summary.duration:.1f} 秒"
        )
        QMessageBox.information(self, "建立快照", message)
        self._refresh()

    def _on_restore(self) -> None:
        snapshot = self._selected()
        if snapshot is None:
            return
        dialog = RestorePathDialog(snapshot, self._snapshots, self)
        if dialog.exec() != QDialog.Accepted:
            return

        def task(stage=None):
            if dialog.keep_snapshot:
                create_snapshot(
                    self._distro,
                    self._paths,
                    self._proxy,
                    False,
                    "還原前",
                    stage,
                )
            return restore_path(
                self._distro,
                self._paths,
                dialog.snapshot_id,
                dialog.path,
                self._proxy,
                stage,
            )

        self._run("還原快照", task, self._on_restored)

    def _on_restored(self, _result) -> None:
        QMessageBox.information(self, "還原快照", "還原完成。")
        self._refresh()

    def _on_delete(self) -> None:
        snapshot = self._selected()
        if snapshot is None:
            return
        answer = QMessageBox.question(
            self,
            "刪除快照",
            f"確定刪除 {format_snapshot_time(snapshot.time)} 的快照？\n"
            "刪除後會立即回收未再被引用的資料。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run(
            "刪除快照",
            partial(
                forget_snapshot,
                self._distro,
                self._paths,
                snapshot.id,
                self._proxy,
            ),
            self._on_deleted,
        )

    def _on_deleted(self, _result) -> None:
        self._refresh()

    def _on_clean(self) -> None:
        keep = self._config.get("snapshot_keep", {})
        answer = QMessageBox.question(
            self,
            "依策略清理",
            "保留策略：最近 {last} 份、每日 {daily} 份、每週 {weekly} 份、每月 {monthly} 份。\n"
            "超出的快照會被刪除並回收空間。".format(
                last=keep.get("last", 0),
                daily=keep.get("daily", 0),
                weekly=keep.get("weekly", 0),
                monthly=keep.get("monthly", 0),
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run(
            "清理快照",
            partial(
                forget_by_policy,
                self._distro,
                self._paths,
                keep,
                self._proxy,
            ),
            self._on_cleaned,
        )

    def _on_cleaned(self, _result) -> None:
        self._refresh()

    def _on_check(self) -> None:
        self._run(
            "校驗快照倉庫",
            partial(check_repo, self._distro, self._paths, self._proxy),
            lambda _result: QMessageBox.information(
                self, "校驗快照倉庫", "校驗完成，未發現錯誤。"
            ),
        )

    def _on_open_folder(self) -> None:
        folder = self._paths.snapshots / self._distro.name
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ---------- 背景工作 ----------

    def _run(self, title, fn, on_success=None) -> None:
        dialog = OperationDialog(title, self)
        worker = TaskWorker(fn, with_stage=True)
        self._workers.add(worker)
        outcome: dict[str, object] = {}

        def finish(result) -> None:
            outcome["result"] = result
            dialog.accept()

        def fail(message: str) -> None:
            outcome["error"] = message
            dialog.reject()

        worker.signals.stage.connect(dialog.set_stage)
        worker.signals.finished.connect(finish)
        worker.signals.failed.connect(fail)
        QThreadPool.globalInstance().start(worker)
        dialog.exec()
        self._workers.discard(worker)

        if "error" in outcome:
            self._error.setText(f"{title}失敗：{outcome['error']}")
            return
        if on_success is not None:
            on_success(outcome.get("result"))


class SnapshotCreateDialog(DialogBase):
    """快照備註與 Docker 資料選項。"""

    def __init__(self, distro: Distro, parent=None):
        super().__init__("建立快照", parent)
        self.tag = ""
        self.include_container_data = False

        self._tag_edit = QLineEdit(self)
        self._tag_edit.setPlaceholderText("例如：升級前（可留空）")
        self._form.addRow("備註", self._tag_edit)

        self._docker_check = QCheckBox("包含 Docker／containerd 資料（較慢）", self)
        self._form.addRow("", self._docker_check)

        self.add_info(
            "快照會備份整個根檔案系統；資料庫或容器寫入中的檔案可能不同步，"
            "建議先停止相關服務。"
        )
        self.add_info("instance 原本是停止狀態時，會先啟動，完成後自動終止回原狀。")

        self.set_ok_text("開始快照")
        self._ok_btn.clicked.connect(self._on_accept)

    def _on_accept(self) -> None:
        tag = self._tag_edit.text().strip()
        if len(tag) > 40:
            self.show_error("備註最多 40 個字")
            return
        self.tag = tag
        self.include_container_data = self._docker_check.isChecked()
        super().accept()


class RestorePathDialog(DialogBase):
    """選擇快照與要還原的路徑。"""

    def __init__(self, snapshot: Snapshot, snapshots: list[Snapshot], parent=None):
        super().__init__("還原快照", parent)
        self.snapshot_id = snapshot.id
        self.path = "/"
        self.keep_snapshot = True

        self._snapshot_combo = QComboBox(self)
        for item in snapshots:
            label = format_snapshot_time(item.time)
            if item.tags:
                label = f"{label}｜{'、'.join(item.tags)}"
            self._snapshot_combo.addItem(f"{label}（{item.short_id}）", item.id)
        index = self._snapshot_combo.findData(snapshot.id)
        self._snapshot_combo.setCurrentIndex(max(0, index))
        self._form.addRow("快照", self._snapshot_combo)

        self._path_edit = QLineEdit("/", self)
        self._path_edit.setPlaceholderText("例如：/etc、/home/user/project")
        self._form.addRow("還原路徑", self._path_edit)

        self._keep_check = QCheckBox("還原前先建立一次快照（建議）", self)
        self._keep_check.setChecked(True)
        self._form.addRow("", self._keep_check)

        self.add_info("還原會覆蓋現有檔案，但不會刪除快照以外的多餘檔案。")
        self.add_info("還原時 instance 必須執行；若原本停止，完成後會自動終止回原狀。")

        self.set_ok_text("開始還原")
        self._ok_btn.clicked.connect(self._on_accept)

    def _on_accept(self) -> None:
        path = self._path_edit.text().strip() or "/"
        if not path.startswith("/"):
            self.show_error("還原路徑必須以 / 開頭")
            return
        self.path = path
        self.snapshot_id = str(self._snapshot_combo.currentData() or self.snapshot_id)
        self.keep_snapshot = self._keep_check.isChecked()
        super().accept()
