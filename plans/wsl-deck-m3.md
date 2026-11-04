# M3 實作計畫：新增／備份／還原／複製／刪除

> 狀態：待確認（確認後才動工）
> 上層文件：[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)、[wsl-deck-mvp.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-mvp.md)
> 目標：完成 M3 全部功能，維持現有 UI 定案與程式風格。

**Goal：** 讓使用者不輸入任何命令，用 GUI 完成 instance 的新增、備份、覆蓋式還原、複製與刪除。

**Architecture：** 新增 `app/distro_ops.py` 集中所有建立／匯出／匯入／註銷流程；UI 只負責收集參數與顯示進度。長時間操作沿用 `TaskWorker`，新增 stage 訊號驅動模態進度框。

**Tech Stack：** Python 3.14、PySide6-Essentials 6.12、`wsl.exe`、`unittest`。

---

## 0. 範圍

- 只做 M3：精靈、備份、還原、複製、刪除、卡片右鍵選單、詳情頁四個按鈕啟用。
- 不做 M4 網路規則與 M5 托盤／設定／打包（刪除時只清 `config.json` 內既有 `port_forwards`，防火牆規則留給 M4）。
- 不重構既有卡片版面、游標、輪詢與日誌機制。

## 1. 已在本機驗證的 CLI 事實（WSL 3.0.3.0）

| 操作 | 實際語法 | 備註 |
|------|----------|------|
| 官方安裝 | `wsl --install -d <name> --location <dir> --no-launch` | `--location`、`--no-launch` 均存在 |
| 匯出 VHDX | `wsl --export <name> <file> --format vhd` | 現有 config 模板的 `--vhd` 是錯的，需修正 |
| 匯出 tar | `wsl --export <name> <file> --format tar` | 支援 tar/tar.gz/tar.xz |
| 匯入 VHDX | `wsl --import <name> <dir> <file> --version 2 --vhd` | 說明明載「在安裝位置建立 VHD 檔案的副本」 |
| 匯入 tar | `wsl --import <name> <dir> <file> --version <v>` | 在安裝位置生成 ext4.vhdx |
| 線上清單 | `wsl --list --online` | 中文前言＋英文表頭 `NAME  FRIENDLY NAME` |

D 槽可用空間約 177 GB，足夠測試。

## 2. 檔案結構

```
wsl-deck/
  app/
    distro_ops.py          # 新增：建立/備份/還原/複製/刪除、線上清單、驗證
    config.py              # 修改：export_vhd 模板、remove_port_forwards()
    ui/
      workers.py           # 修改：TaskWorker stage 訊號
      progress.py          # 新增：模態進度框
      wizard.py            # 新增：新增 Instance 三步精靈
      backup_dialogs.py    # 新增：備份/還原/複製/刪除對話框
      instance_card.py     # 修改：右鍵選單與四個訊號
      card_wall.py         # 修改：轉發四個訊號
      detail_page.py       # 修改：啟用備份/還原/複製/刪除並發訊號
      main_window.py       # 修改：流程編排、進度框、重新整理後開詳情
  config.json              # 修改：export_vhd 模板
  tests/
    test_distro_ops.py     # 新增
    test_config.py         # 修改：remove_port_forwards
```

## 3. 任務

### Task 1：`distro_ops.py` 純函式與驗證（含測試）

**Files：**
- Create：`wsl-deck/app/distro_ops.py`
- Create：`wsl-deck/tests/test_distro_ops.py`

- [ ] **Step 1：先寫測試**

```python
"""distro_ops 純函式測試。"""

from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from app.distro_ops import (
    OnlineDistro,
    default_backup_file,
    parse_online_list,
    validate_new_name,
    validate_target_dir,
)


ONLINE_EN = (
    "NAME                            FRIENDLY NAME\n"
    "Ubuntu                          Ubuntu\n"
    "Ubuntu-24.04                    Ubuntu 24.04 LTS\n"
)

ONLINE_ZH = (
    "以下是可安装的有效分发的列表。\n"
    "使用“wsl.exe --install <Distro>”安装。\n\n"
    "NAME                            FRIENDLY NAME\n"
    "Ubuntu                          Ubuntu\n"
    "Debian                          Debian GNU/Linux\n"
)


class OnlineListTest(unittest.TestCase):
    def test_english_table(self) -> None:
        self.assertEqual(
            parse_online_list(ONLINE_EN),
            [
                OnlineDistro("Ubuntu", "Ubuntu"),
                OnlineDistro("Ubuntu-24.04", "Ubuntu 24.04 LTS"),
            ],
        )

    def test_chinese_preamble(self) -> None:
        self.assertEqual(
            parse_online_list(ONLINE_ZH),
            [
                OnlineDistro("Ubuntu", "Ubuntu"),
                OnlineDistro("Debian", "Debian GNU/Linux"),
            ],
        )

    def test_null_bytes(self) -> None:
        text = ONLINE_EN.replace("\n", "\x00\n")
        self.assertEqual(len(parse_online_list(text)), 2)

    def test_empty(self) -> None:
        self.assertEqual(parse_online_list(""), [])


class NameValidationTest(unittest.TestCase):
    def test_valid(self) -> None:
        validate_new_name("wsl-deck-test", ["ubuntu"])

    def test_duplicate_case_insensitive(self) -> None:
        with self.assertRaises(ValueError):
            validate_new_name("Ubuntu", ["ubuntu"])

    def test_blank(self) -> None:
        with self.assertRaises(ValueError):
            validate_new_name("  ", [])

    def test_illegal_characters(self) -> None:
        for name in ("a b", r"a\b", "a/b", "-abc", "a:b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_new_name(name, [])


class TargetDirTest(unittest.TestCase):
    def test_missing_parent_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_target_dir(Path("Z:/no-such-parent/child"))


class BackupPathTest(unittest.TestCase):
    def test_default_path(self) -> None:
        path = default_backup_file(
            Path(r"D:\backups"), "node22", True, datetime(2026, 10, 30, 12, 34, 56)
        )
        self.assertEqual(
            path,
            Path(r"D:\backups") / "node22" / "node22-20261030-123456.vhdx",
        )

    def test_tar_suffix(self) -> None:
        path = default_backup_file(
            Path(r"D:\backups"), "node22", False, datetime(2026, 10, 30, 12, 34, 56)
        )
        self.assertEqual(path.suffix, ".tar")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2：執行測試確認失敗**

```
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest tests.test_distro_ops -q
```

預期：`ModuleNotFoundError: No module named 'app.distro_ops'`。

- [ ] **Step 3：實作純函式**

```python
"""Instance 建立、備份、還原、複製、刪除流程。"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

Stage = Callable[[str], None]

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class OnlineDistro:
    name: str
    friendly_name: str


@dataclass(frozen=True)
class NewInstancePlan:
    source: str          # "online" / "tar" / "vhdx"
    name: str
    install_dir: str
    file: str = ""
    version: int = 2


def _stage(stage: Stage | None, message: str) -> None:
    logger.info(message)
    if stage is not None:
        stage(message)


def parse_online_list(text: str) -> list[OnlineDistro]:
    rows: list[OnlineDistro] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.replace("\x00", "").rstrip()
        if not line.strip():
            continue
        if not in_table:
            if re.match(r"\s*NAME\s{2,}", line, re.IGNORECASE):
                in_table = True
            continue
        match = re.match(r"\s*(\S+)\s{2,}(.+)$", line)
        if match:
            rows.append(OnlineDistro(match.group(1), match.group(2).strip()))
    return rows


def validate_new_name(name: str, existing: list[str]) -> None:
    name = name.strip()
    if not name:
        raise ValueError("名稱不可空白")
    if not NAME_PATTERN.match(name):
        raise ValueError("名稱只能使用英文字母、數字、句點、底線、減號，且需以字母或數字開頭")
    for item in existing:
        if name.lower() == item.lower():
            raise ValueError(f"已有同名 instance：{item}")


def validate_target_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"安裝路徑不是資料夾：{path}")
        if any(path.iterdir()):
            raise ValueError(f"安裝路徑必須是空資料夾：{path}")
    elif not path.parent.exists():
        raise ValueError(f"安裝路徑的上層資料夾不存在：{path.parent}")


def default_backup_file(
    backup_root: Path,
    name: str,
    vhd: bool = True,
    now: datetime | None = None,
) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return backup_root / name / f"{name}-{stamp}{'.vhdx' if vhd else '.tar'}"
```

- [ ] **Step 4：執行測試確認通過**

```
.\.venv\Scripts\python.exe -m unittest tests.test_distro_ops -q
```

預期：11 項通過。

### Task 2：`distro_ops.py` 實際操作函式

**Files：** Modify：`wsl-deck/app/distro_ops.py`

- [ ] **Step 1：加入操作函式**

```python
from app.wsl import Distro, WslError, run_wsl, terminate_distro

LONG_TIMEOUT = 3600


def list_online() -> list[OnlineDistro]:
    return parse_online_list(run_wsl(["--list", "--online"], timeout=120))


def _prepare_dir(path: Path) -> None:
    validate_target_dir(path)
    path.mkdir(parents=False, exist_ok=True)


def create_instance(plan: NewInstancePlan, stage: Stage | None = None) -> None:
    target = Path(plan.install_dir)
    _prepare_dir(target)
    if plan.source == "online":
        _stage(stage, f"正在安裝 {plan.name}…")
        args = ["--install", "-d", plan.name, "--location", str(target), "--no-launch"]
    elif plan.source == "vhdx":
        _stage(stage, f"正在匯入 {plan.name}…")
        args = ["--import", plan.name, str(target), plan.file, "--version", "2", "--vhd"]
    else:
        _stage(stage, f"正在匯入 {plan.name}…")
        args = ["--import", plan.name, str(target), plan.file, "--version", str(plan.version)]
    try:
        run_wsl(args, timeout=LONG_TIMEOUT)
    except WslError as exc:
        if plan.source == "online":
            raise WslError(
                f"{exc}\n提示：可先安裝，再用 wsl --manage {plan.name} --move \"{target}\" 搬移。"
            ) from exc
        raise


def backup_instance(
    distro: Distro,
    file: str,
    vhd: bool = True,
    stage: Stage | None = None,
) -> None:
    target = Path(file)
    target.parent.mkdir(parents=True, exist_ok=True)
    _stage(stage, f"正在匯出 {distro.name}…")
    try:
        run_wsl(
            ["--export", distro.name, str(target), "--format", "vhd" if vhd else "tar"],
            timeout=LONG_TIMEOUT,
        )
    except WslError as exc:
        raise WslError(f"{exc}\n若匯出失敗，請先終止 instance 再試。") from exc


def restore_instance(
    distro: Distro,
    backup_file: str,
    keep_current: bool,
    backup_root: Path,
    stage: Stage | None = None,
) -> str:
    backup_path = Path(backup_file)
    if not backup_path.is_file():
        raise ValueError(f"找不到備份檔：{backup_path}")
    vhd = backup_path.suffix.lower() in (".vhdx", ".vhd")

    safety_backup = ""
    if keep_current:
        safety_backup = str(default_backup_file(backup_root, distro.name, vhd=True))
        _stage(stage, "正在備份目前狀態…")
        backup_instance(distro, safety_backup, True, stage)

    _stage(stage, f"正在終止 {distro.name}…")
    try:
        terminate_distro(distro.name)
    except WslError:
        pass

    _stage(stage, "正在移除現有 instance…")
    run_wsl(["--unregister", distro.name], timeout=120)

    target = Path(distro.base_path)
    target.mkdir(parents=True, exist_ok=True)
    for leftover in target.glob("ext4.vhdx"):
        leftover.unlink(missing_ok=True)

    try:
        _stage(stage, "正在匯入備份…")
        if vhd:
            args = ["--import", distro.name, str(target), str(backup_path), "--version", "2", "--vhd"]
        else:
            args = [
                "--import", distro.name, str(target), str(backup_path),
                "--version", str(distro.version),
            ]
        run_wsl(args, timeout=LONG_TIMEOUT)
    except Exception:
        if safety_backup:
            _stage(stage, "還原失敗，正在用現況備份回復…")
            try:
                run_wsl(["--unregister", distro.name], timeout=120)
            except WslError:
                pass
            run_wsl(
                ["--import", distro.name, str(target), safety_backup, "--version", "2", "--vhd"],
                timeout=LONG_TIMEOUT,
            )
        raise
    return safety_backup


def clone_instance(
    source: Distro,
    new_name: str,
    target_dir: str,
    temp_dir: Path,
    stage: Stage | None = None,
) -> None:
    target = Path(target_dir)
    _prepare_dir(target)
    temp_dir.mkdir(parents=True, exist_ok=True)
    vhd = source.version >= 2
    suffix = ".vhdx" if vhd else ".tar"
    temp = temp_dir / f"{source.name}-clone-{datetime.now():%Y%m%d-%H%M%S}{suffix}"
    try:
        _stage(stage, "正在匯出暫存檔…")
        backup_instance(source, str(temp), vhd, stage)
        _stage(stage, f"正在匯入 {new_name}…")
        if vhd:
            args = ["--import", new_name, str(target), str(temp), "--version", "2", "--vhd"]
        else:
            args = ["--import", new_name, str(target), str(temp), "--version", str(source.version)]
        run_wsl(args, timeout=LONG_TIMEOUT)
    except Exception:
        try:
            run_wsl(["--unregister", new_name], timeout=60)
        except WslError:
            pass
        raise
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("刪除暫存檔失敗：%s（%s）", temp, exc)


def delete_instance(
    distro: Distro,
    backup_file: str | None = None,
    stage: Stage | None = None,
) -> None:
    if backup_file:
        backup_instance(distro, backup_file, True, stage)
    _stage(stage, f"正在刪除 {distro.name}…")
    run_wsl(["--unregister", distro.name], timeout=120)
```

- [ ] **Step 2：匯入檢查**

```
.\.venv\Scripts\python.exe -c "import app.distro_ops as m; print(m.create_instance.__name__)"
```

預期：`create_instance`。

**實測後調整（已完成）：**
- VHDX 匯出必須先 `wsl --shutdown`（僅 terminate 仍會 sharing violation）；`backup_instance(vhd=True)` 會先關閉 WSL，備份對話框明示會終止所有 instance。
- 還原的「現況備份」改用 TAR（可執行中匯出），避免因 VHDX 匯出而中斷；失敗回復也用 TAR 匯入。
- 複製的暫存檔改用 TAR；刪除的預設備份改用 TAR，並在 `unregister` 前先 terminate。
- 實測 `--unregister` 會刪除整個安裝資料夾；`--import --vhd` 會把來源 VHDX 複製到安裝目錄，原備份檔保留。

### Task 3：Config 小幅修正

**Files：** Modify：`wsl-deck/app/config.py`、`wsl-deck/config.json`、`wsl-deck/tests/test_config.py`

- [ ] **Step 1：修正 export_vhd 模板**

`app/config.py` 與 `config.json` 都改成：

```json
"export_vhd": "wsl.exe --export \"{name}\" \"{file}\" --format vhd"
```

- [ ] **Step 2：加入刪除端口規則的方法與測試**

`Config` 內新增：

```python
def remove_port_forwards(self, distro: str) -> int:
    """刪除指定 instance 的所有端口規則，回傳刪除數量。"""
    rules = self.data.get("port_forwards", [])
    keep = [rule for rule in rules if rule.get("distro") != distro]
    removed = len(rules) - len(keep)
    if removed:
        self.data["port_forwards"] = keep
        self.save()
    return removed
```

`tests/test_config.py` 新增：

```python
def test_remove_port_forwards(self) -> None:
    self.config.data["port_forwards"] = [
        {"label": "web", "distro": "node22", "windows_port": 8080, "distro_port": 80},
        {"label": "api", "distro": "node22", "windows_port": 8081, "distro_port": 81},
        {"label": "ssh", "distro": "ubuntu", "windows_port": 2222, "distro_port": 22},
    ]
    self.config.save()
    self.assertEqual(self.config.remove_port_forwards("node22"), 2)
    self.assertEqual(len(self.config.data["port_forwards"]), 1)
    self.assertEqual(self.config.data["port_forwards"][0]["distro"], "ubuntu")
```

- [ ] **Step 3：跑測試**

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：全部通過（現有 13 項＋新增）。

### Task 4：TaskWorker stage 與模態進度框

**Files：** Modify：`wsl-deck/app/ui/workers.py`、Create：`wsl-deck/app/ui/progress.py`

- [ ] **Step 1：workers.py 增加 stage**

```python
class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    stage = Signal(str)


class TaskWorker(QRunnable):
    def __init__(self, fn: Callable, *args, with_stage: bool = False, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.with_stage = with_stage
        self.signals = TaskSignals()

    def run(self) -> None:
        if self.with_stage:
            self.kwargs.setdefault("stage", self._emit_stage)
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("背景工作失敗")
            self._emit(self.signals.failed, str(exc))
        else:
            self._emit(self.signals.finished, result)

    def _emit_stage(self, message: str) -> None:
        self._emit(self.signals.stage, message)

    @staticmethod
    def _emit(signal, value) -> None:
        try:
            signal.emit(value)
        except RuntimeError:
            logger.debug("UI 已關閉，丟棄背景工作結果")
```

- [ ] **Step 2：progress.py**

```python
"""不可取消的模態進度框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog, QLabel, QProgressBar, QVBoxLayout,
)


class OperationDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        heading = QLabel(title, self)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        self.stage_label = QLabel("準備中…", self)
        self.stage_label.setWordWrap(True)
        layout.addWidget(self.stage_label)

        bar = QProgressBar(self)
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        layout.addWidget(bar)

        note = QLabel("操作進行中，請勿關閉此視窗。", self)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

    def set_stage(self, text: str) -> None:
        self.stage_label.setText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
```

### Task 5：新增 Instance 三步精靈

**Files：** Create：`wsl-deck/app/ui/wizard.py`

- [ ] **Step 1：建立 `NewInstanceWizard`**

```python
"""新增 Instance 三步精靈。"""

from __future__ import annotations

from pathlib import Path
from functools import partial

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QVBoxLayout, QWidget, QWizard, QWizardPage,
)

from app.distro_ops import (
    NewInstancePlan, list_online, validate_new_name, validate_target_dir,
)
from app.ui.cursors import refresh_cursor
from app.ui.workers import TaskWorker


class NewInstanceWizard(QWizard):
    def __init__(self, distro_root: Path, existing_names: list[str], parent=None):
        super().__init__(parent)
        self._distro_root = distro_root
        self._existing = existing_names
        self._workers: set[TaskWorker] = set()
        self._online_loaded = False
        self._dir_edited = False
        self.plan: NewInstancePlan | None = None

        self.setWindowTitle("新增 Instance")
        self.setMinimumWidth(640)
        self.setWizardStyle(QWizard.ModernStyle)
        self._build_source_page()
        self._build_selection_page()
        self._build_naming_page()
        self.setPage(0, self._source_page)
        self.setPage(1, self._selection_page)
        self.setPage(2, self._naming_page)
```

頁面內容：

- **來源頁**：三個 `QRadioButton`（`官方發行版`、`rootfs／tar`、`VHDX`），放進 `QButtonGroup`，切換時更新選檔頁的可見區塊。
- **選擇頁**：
  - 線上面板：`QListWidget`＋「重新整理」按鈕＋狀態 `QLabel`；進入頁面時若尚未載入，用 `TaskWorker(list_online)` 非同步載入；失敗顯示紅字並可重試。
  - 檔案面板：唯讀 `QLineEdit`＋「瀏覽…」按鈕；tar 篩選 `*.tar *.tar.gz *.tar.xz`，VHDX 篩選 `*.vhdx *.vhd`。
- **命名頁**：`QFormLayout`
  - 名稱：官方來源時唯讀並顯示「官方名稱固定」；檔案來源可改。
  - 安裝目錄：預設 `distro_root\<name>`；使用者改過目錄後不再自動跟隨名稱。
  - 版本：tar 可選 1／2；VHDX 固定 2 並禁用；官方隱藏。
  - 錯誤 `QLabel`（紅字）。

關鍵行為：

```python
def validateCurrentPage(self) -> bool:
    if self.currentPage() is self._selection_page:
        if self._source() == "online":
            if self._online_list.currentItem() is None:
                self._selection_error.setText("請選擇一個發行版")
                return False
        else:
            path = Path(self._file_edit.text())
            if not path.is_file():
                self._selection_error.setText("請選擇存在的 tar／VHDX 檔案")
                return False
    if self.currentPage() is self._naming_page:
        try:
            validate_new_name(self._name_edit.text(), self._existing)
            validate_target_dir(Path(self._dir_edit.text().strip()))
        except ValueError as exc:
            self._name_error.setText(str(exc))
            return False
    return True

def accept(self) -> None:
    source = self._source()
    self.plan = NewInstancePlan(
        source=source,
        name=self._name_edit.text().strip(),
        install_dir=self._dir_edit.text().strip(),
        file=self._file_edit.text().strip(),
        version=int(self._version_combo.currentData() or 2),
    )
    super().accept()
```

`_source()` 回傳 `"online"`／`"tar"`／`"vhdx"`；切換來源時清除錯誤、重建預設名稱與目錄。

### Task 6：備份／還原／複製／刪除對話框

**Files：** Create：`wsl-deck/app/ui/backup_dialogs.py`

- [ ] **Step 1：共用外觀**

所有對話框：`QDialog`、最小寬度 540、`QFormLayout`、底部「取消」＋主要按鈕（最小高度 32）、`refresh_cursor()`；主要按鈕按 Enter 觸發。

- [ ] **Step 2：四類對話框介面**

```python
class BackupDialog(QDialog):
    """回傳 file_path: str、vhd: bool。"""
    def __init__(self, distro: Distro, config: Config, parent=None): ...


class RestoreDialog(QDialog):
    """回傳 file_path: str、keep_current: bool。"""
    def __init__(self, distro: Distro, config: Config, parent=None): ...


class CloneDialog(QDialog):
    """回傳 new_name: str、target_dir: str。"""
    def __init__(self, distro: Distro, config: Config, existing_names: list[str], parent=None): ...


class DeleteDialog(QDialog):
    """回傳 backup_file: str | None。"""
    def __init__(self, distro: Distro, config: Config, parent=None): ...
```

各自內容：

- **BackupDialog**
  - 資料夾（預設 `backup_root\<name>`）＋瀏覽；檔名（預設 `<name>-yyyyMMdd-HHmmss`）；格式 `VHDX（建議）／TAR`。
  - 切換格式時同步副檔名；執行中顯示提示「執行中也可匯出，但建議先終止以確保一致」。
  - `file_path` = 資料夾／檔名＋副檔名；驗證資料夾可建立、檔名不含 `\/:*?"<>|`。
- **RestoreDialog**
  - 備份檔（預設開在 `backup_root\<name>`，瀏覽篩選 `.vhdx/.tar/.tar.gz/.tar.xz`）。
  - 勾選「先備份目前狀態（建議）」，預設勾選。
  - 名稱輸入框，必須與 instance 名稱完全相同才可按確認；不符時紅字提示。
  - 執行中顯示「還原前會先終止 instance」。
- **CloneDialog**
  - 新名稱、目標目錄（預設 `distro_root\<new>`）＋瀏覽；顯示來源磁盤大小 `X.XX GB`；提示「端口規則不會複製」。
  - 驗證名稱格式與重複、目標目錄為空。
- **DeleteDialog**
  - 紅字警告「刪除後無法復原，建議先備份。」
  - 勾選「先備份再刪除」，預設勾選；勾選時顯示將寫入的預設備份路徑。
  - 名稱輸入框，輸入完全相符才可按「刪除」。

### Task 7：卡片右鍵選單與詳情頁按鈕

> 後續調整（2026-11-02）：依使用者回饋移除卡片右鍵選單，只保留詳情頁四個按鈕；下列右鍵選單內容僅作歷史紀錄。

**Files：** Modify：`wsl-deck/app/ui/instance_card.py`、`card_wall.py`、`detail_page.py`

- [ ] **Step 1：InstanceCard**

新增訊號：

```python
backup_requested = Signal(str)
restore_requested = Signal(str)
clone_requested = Signal(str)
delete_requested = Signal(str)
```

`_build()` 內：

```python
self.setContextMenuPolicy(Qt.CustomContextMenu)
self.customContextMenuRequested.connect(self._show_context_menu)
```

```python
def _show_context_menu(self, pos) -> None:
    if self._system:
        return
    menu = QMenu(self)
    for text, signal in (
        ("備份", self.backup_requested),
        ("還原", self.restore_requested),
        ("複製", self.clone_requested),
        ("刪除", self.delete_requested),
    ):
        action = menu.addAction(text)
        action.triggered.connect(
            lambda _checked=False, sig=signal: sig.emit(self._distro.name)
        )
    menu.exec(self.mapToGlobal(pos))
```

- [ ] **Step 2：CardWall 轉發四個訊號**

新增同名訊號並在建立卡片時逐一 connect 到 `self.<signal>`。

- [ ] **Step 3：DetailPage**

新增四個訊號；移除四個按鈕的 `setEnabled(False)`／「M3 提供」tooltip，改為：

```python
self._backup_btn.clicked.connect(lambda: self._emit_name(self.backup_requested))
self._restore_btn.clicked.connect(lambda: self._emit_name(self.restore_requested))
self._clone_btn.clicked.connect(lambda: self._emit_name(self.clone_requested))
self._delete_btn.clicked.connect(lambda: self._emit_name(self.delete_requested))
```

`set_distro()` 結尾：

```python
for button in (self._backup_btn, self._restore_btn, self._clone_btn, self._delete_btn):
    button.setEnabled(not is_system)
    refresh_cursor(button)
```

### Task 8：MainWindow 流程編排

**Files：** Modify：`wsl-deck/app/ui/main_window.py`

- [ ] **Step 1：`_run_operation()` 共用進度流程**

```python
from app.ui.progress import OperationDialog

def _run_operation(self, title, fn, on_success, on_error=None) -> None:
    self._timer.stop()
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
    self._timer.start(max(3, int(self.config.get("poll_interval", 10))) * 1000)

    if "error" in outcome:
        message = str(outcome["error"])
        logger.error("%s失敗：%s", title, message)
        QMessageBox.warning(self, f"{title}失敗", f"{message}\n\n詳細步驟請見日誌。")
        if on_error is not None:
            on_error(message)
        return
    on_success(outcome.get("result"))
```

- [ ] **Step 2：新增流程處理**

```python
def _new_instance(self) -> None:
    wizard = NewInstanceWizard(
        self.config.resolve_path(self.config.get("distro_root", ".")),
        [distro.name for distro in self._distros],
        self,
    )
    if wizard.exec() != QDialog.Accepted or wizard.plan is None:
        return
    plan = wizard.plan
    self._run_operation(
        "新增 Instance",
        partial(create_instance, plan),
        lambda _result: self._after_created(plan.name),
        lambda _message: self.refresh(),
    )

def _after_created(self, name: str) -> None:
    logger.info("已新增 %s", name)
    self._open_after_refresh = name
    self.refresh()

def _backup(self, name: str) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    dialog = BackupDialog(distro, self.config, self)
    if dialog.exec() != QDialog.Accepted:
        return
    self._run_operation(
        f"備份 {name}",
        partial(backup_instance, distro, dialog.file_path, dialog.vhd),
        lambda _result: self._after_action(f"已備份 {name} 到 {dialog.file_path}"),
        lambda _message: None,
    )

def _restore(self, name: str) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    dialog = RestoreDialog(distro, self.config, self)
    if dialog.exec() != QDialog.Accepted:
        return
    self._run_operation(
        f"還原 {name}",
        partial(
            restore_instance, distro, dialog.file_path, dialog.keep_current,
            self.config.resolve_path(self.config.get("backup_root", "backups")),
        ),
        lambda _result: self._after_action(f"已還原 {name}"),
        lambda _message: self.refresh(),
    )

def _clone(self, name: str) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    dialog = CloneDialog(distro, self.config, [d.name for d in self._distros], self)
    if dialog.exec() != QDialog.Accepted:
        return
    backup_root = self.config.resolve_path(self.config.get("backup_root", "backups"))
    self._run_operation(
        f"複製 {name}",
        partial(
            clone_instance, distro, dialog.new_name, dialog.target_dir,
            backup_root / "_tmp",
        ),
        lambda _result: self._after_created(dialog.new_name),
        lambda _message: self.refresh(),
    )

def _delete(self, name: str) -> None:
    distro = self._find(name)
    if distro is None or self._is_system(name):
        return
    dialog = DeleteDialog(distro, self.config, self)
    if dialog.exec() != QDialog.Accepted:
        return

    def removed(_result) -> None:
        count = self.config.remove_port_forwards(name)
        if count:
            logger.info("已移除 %s 的 %d 條端口規則", name, count)
        if self._current is not None and self._current.name == name:
            self._show_main()
        self._after_action(f"已刪除 {name}")

    self._run_operation(
        f"刪除 {name}",
        partial(delete_instance, distro, dialog.backup_file),
        removed,
        lambda _message: self.refresh(),
    )
```

- [ ] **Step 3：接線與啟用**

- `_build_main_page()`：`self._new_btn.setEnabled(True)`、移除「M3 提供」tooltip、`clicked.connect(self._new_instance)`。
- `_connect_signals()`：CardWall 與 DetailPage 的 `backup_requested`、`restore_requested`、`clone_requested`、`delete_requested` 接到對應方法。
- 新增 `_find(name)`：

```python
def _find(self, name: str) -> Distro | None:
    return next((distro for distro in self._distros if distro.name == name), None)
```

- 新增 `self._open_after_refresh: str = ""`；在 `_on_distros()` 更新完卡片後：

```python
if self._open_after_refresh:
    target = next(
        (distro for distro in distros if distro.name == self._open_after_refresh), None
    )
    self._open_after_refresh = ""
    if target is not None:
        self._show_detail(target)
```

### Task 9：測試與整體驗收

- [ ] **Step 1：自動測試**

```
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：13 項舊測試＋15 項新測試（共 28 項）全部通過。

- [ ] **Step 2：啟動 GUI（由使用者執行）**

```
d:\VirtualMachiles\wsl\wsl-deck\.venv\Scripts\pythonw.exe d:\VirtualMachiles\wsl\wsl-deck\main.py
```

- [ ] **Step 3：手動驗收（只對測試 instance 操作）**

1. **新增**：`+ 新增 Instance` → VHDX → `backups\ubuntu\ubuntu.vhdx` → 名稱 `wsl-deck-test`、目錄 `D:\VirtualMachiles\wsl\wsl-deck-test` → 進度完成後自動進詳情頁。
2. **備份**：詳情頁「備份」→ 預設路徑 `backups\wsl-deck-test\wsl-deck-test-*.vhdx` → 檔案存在且大小合理。
3. **還原**：開終端在 `/tmp` 建標記檔 → 詳情頁「還原」→ 選剛才備份、勾選先備份、輸入名稱 → 完成後標記檔消失。
4. **複製**：詳情頁「複製」→ 新名稱 `wsl-deck-test-clone` → 目錄預設 → 完成後卡片出現；確認 `config.json` 的 `port_forwards` 未增加。
5. **刪除 A**：勾選先備份 → 輸入名稱 → 完成後 instance 消失、備份檔產生。
6. **刪除 B**：取消勾選先備份 → 輸入名稱 → 直接刪除。
7. **右鍵選單**：已移除；備份／還原／複製／刪除只從詳情頁操作。
8. **取消保護**：任一對話框改名不符或直接取消，不得發生任何變更。
9. **清理**：刪除所有測試 instance；必要時手動移除測試備份。

- [ ] **Step 4：回報**

整理實際結果、任何與計畫不同的 CLI 行為（尤其是 unregister 後安裝目錄殘留、執行中匯出）並更新 handoff 文件。

## 4. 風險與對策

- **執行中備份**：實測 VHDX 匯出即使 terminate 仍會 sharing violation，必須 `wsl --shutdown`；因此 VHDX 備份會先關閉整個 WSL（含 docker-desktop），對話框已明示。TAR 可在執行中匯出。
- **還原現況備份**：統一使用 TAR，流程為「終止 → TAR 備份現況 → 註銷 → 匯入備份」，避免備份步驟中斷所有 instance。
- **複製／刪除備份**：暫存檔與刪除預設備份都使用 TAR；複製不複製端口規則。
- **還原後安裝目錄**：實測 `--unregister` 會刪除整個安裝資料夾，還原時重新建立再匯入；不再需要清除殘留 vhdx。
- **VHDX 還原版本**：一律以版本 2 匯入；tar 還原保留原版本。
- **官方安裝失敗**：錯誤訊息附「先安裝再 `wsl --manage --move`」提示。
- **磁盤空間**：建立與複製前檢查目標目錄可用空間（需求以來源檔案大小估算）；備份空間不足由匯出錯誤回報。
- **複製失敗殘留**：匯入失敗時嘗試 `--unregister <new_name>`，並刪除暫存檔。
- **舊 config 鍵**：M3 不動 `preview_commands`／`minimize_to_tray`，留待 M5 遷移。

## 5. 確認清單

- [ ] 同意新增 `distro_ops.py` 集中所有 instance 生命週期操作。
- [ ] 同意修正 export 模板為 `--format vhd`（現有 `--vhd` 在本機無效）。
- [ ] 同意還原一律先備份現況（可取消勾選）並在失敗時嘗試自動回復。
- [ ] 同意刪除只清 `config.json` 端口規則；防火牆規則留待 M4。
- [x] 卡片右鍵選單已依回饋移除；備份／還原／複製／刪除只保留詳情頁按鈕。
- [ ] 確認後開始實作，完成後回報並等待驗收。
