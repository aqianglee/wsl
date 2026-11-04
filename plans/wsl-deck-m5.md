# M5 實作計畫：托盤／開機自啟／設定／主題／打包

> 狀態：待確認（確認後才動工）
> 上層文件：[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)、[wsl-deck-mvp.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-mvp.md)、[wsl-deck-m4.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m4.md)
> 目標：依 handoff 第 7 節完成 M5，讓 App 可縮托盤、可開機自啟、可在 GUI 內完成設定、可切換主題，並產出免 Python 環境的 onedir 執行檔。

**Goal：** 補上托盤、開機自啟、設定、主題與打包，讓 WSL Deck 從「開發時可跑的 GUI」變成「日常可用的桌面工具」。

**Architecture：** 新增 `app/paths.py` 統一開發／凍結後的可寫路徑；`app/autostart.py` 只處理 `HKCU\...\Run`；`app/ui/theme.py` 以 Fusion ＋ QPalette 切換深淺色；`app/ui/tray.py` 包裝 `QSystemTrayIcon` 並以訊號驅動 `MainWindow`；`app/ui/settings_dialog.py` 只收集設定，寫入與套用由 `MainWindow` 負責。打包以 PyInstaller onedir 產出 `dist\WSL Deck\WSL Deck.exe`，提權子進程改走 exe 的 `--admin-job` 入口。

**Tech Stack：** Python 3.14.2、PySide6-Essentials 6.12.0、`winreg`、Windows PowerShell 5（提權）、PyInstaller 6.22.3（dev 依賴）、`unittest`。

---

## 0. 範圍

- 只做 handoff 第 7 節列出的 M5：托盤、開機自啟、設定對話框、主題、打包，以及為打包所需的提權入口調整。
- 一併處理 handoff 第 8 節的舊 `config.json` 鍵遷移（`preview_commands`、`minimize_to_tray`）。
- 不改 M1～M4 既有行為：卡片版面、詳情頁、網路規則流程、日誌抽屜格式都不變；只有主題會把卡片邊框改為 palette 顏色。
- 不做：單一實例互斥（見 §9 決策 7）、安裝程式、自動更新、簽章、多語系、M4 功能修正。
- 日誌抽屜已在 M2 完成，M5 只增加「進階模式」對命令列的顯示開關，不重做抽屜。

## 1. 工作區現況基線（2026-11-02）

### 1.1 版本控制

- `d:\VirtualMachiles\wsl` **不是 git repo**（`git status` 回傳 `fatal: not a git repository`）。
- 因此本次無法用 `git status` 判斷未提交變更；改以檔案時間戳與 SHA256 建立基線，並在動工前做一次快照（見 §8）。

### 1.2 測試與環境基線

```
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

- 實測結果：`Ran 42 tests ... OK`。
- Python 3.14.2；PySide6-Essentials 6.12.0；`.venv` 內**尚未安裝 PyInstaller**（`pip list` 只有 pip／PySide6／shiboken6）。
- `pyinstaller` 線上可取得 6.22.3（已確認）。

### 1.3 最近修改時間（判斷另一會話是否仍在動 M4）

| 時間 | 檔案 |
|------|------|
| 14:25 | `app/config.py`、`tests/test_config.py` |
| 14:28 | `app/ui/rule_dialog.py` |
| 14:29 | `app/ui/detail_page.py` |
| 14:34 | `app/network.py`、`app/ui/scan_dialog.py`、`tests/test_network.py` |
| 14:42 | `app/ui/main_window.py` |
| 14:44 | `app/admin.py`、`app/ui/network_panel.py` |
| 14:52 | `plans/wsl-deck-m4-acceptance.md`（另一會話產出的驗收文件） |
| 15:06 | `plans/wsl-mysql-tomcat-acceptance.md`（與本專案無關） |

判讀：M4 代碼在 14:44 後沒有再被改動，14:52 起另一會話在寫驗收文件。**目前沒有進行中的 M4 代碼修改**，但對方可能因 GUI 驗收失敗而回頭修 M4 檔案。

### 1.4 與進行中工作的檔案重疊

| 檔案 | M5 用途 | M4 會話可能改動 | 建議 |
|------|---------|-----------------|------|
| `app/ui/main_window.py` | 托盤、關窗、設定按鈕、進階模式 | 是（修網路／詳情頁 UI 問題） | **最後整合**；動工前重讀並比對 SHA256 |
| `app/admin.py` | 凍結後的 `--admin-job` 入口 | 是（修提權／netsh 問題） | 同上，變更只有 `run_admin_job` 的啟動命令 |
| `app/config.py` | 舊鍵遷移、新設定驗證 | 是（修端口規則驗證） | 遷移邏輯用獨立方法，避免改動既有驗證流程 |
| `app/ui/detail_page.py`、`app/network.py`、`app/ui/network_panel.py`、`app/ui/rule_dialog.py`、`app/ui/scan_dialog.py` | M5 不碰 | 是 | **M5 不動**，若需修改另開任務 |
| `app/ui/instance_card.py`（13:20）、`app/ui/backup_dialogs.py` | 主題 palette、共用對話框基底 | 否 | 可先做 |

### 1.5 現況程式缺口（對應 M5 要補的東西）

- `MainWindow` 沒有托盤、沒有 `closeEvent`；關窗即結束。
- 右下角齒輪 `_settings_btn` 目前 `setEnabled(False)`、tooltip「設定（M5 提供）」。
- `main.py` 沒有 `--silent`，也沒有 `--admin-job`；`ROOT` 以 `__file__` 計算，PyInstaller 凍結後會指向 `_internal`。
- `app/admin.py` 的提權命令固定用 `sys.executable -m app.admin`，凍結後會失效。
- `config.json` 仍是舊鍵（`preview_commands: true`、`minimize_to_tray: true`），缺 `theme`、`poll_interval`、`close_to_tray`、`advanced_mode`、`system_instances`。
- `DEFAULT_CONFIG` 已有新鍵，但 `Config.load()` 不補預設、也不遷移舊鍵。
- 卡片 QSS 的邊框寫死 `#cfd4da`、`#e1e5ea`，深色主題下會過亮。
- 專案沒有 `tray.py`、`settings_dialog.py`、`theme.py`、`autostart.py`、`paths.py`。

### 1.6 建議實作順序（降低與 M4 會話衝突）

1. **Phase A（不重疊）：** Task 1～4（`paths.py`、`autostart.py`、`config` 遷移、`theme.py`＋卡片 QSS）。
2. **Phase B（等 M4 收尾）：** Task 5～8（設定對話框、托盤、`MainWindow`、`main.py`）。動工前重跑 42 項測試、重讀 `main_window.py`、比對 SHA256（基線 `main_window.py` = `30365B484DC4`）。
3. **Phase C（可獨立驗證）：** Task 9～10（`admin.py` 凍結入口、PyInstaller 打包）。

若 M4 會話在 Phase B 期間仍修改 `main_window.py`，以對方的版本為底重新套用 M5 變更，不要整檔覆蓋。

### 1.7 基線 SHA256（前 12 碼，供動工前比對）

```
main_window.py    30365B484DC4      admin.py        884B1A287354
config.py         F4879A1EF176      instance_card.py 83F0DF5884FD
detail_page.py    45D80D41484F      network.py      16C99BBCFEE1
network_panel.py  F571934940AE      backup_dialogs.py 28146FBF0B10
test_config.py    F0D786EFB592
```

## 2. 檔案結構

```
wsl-deck/
  main.py                     # 修改：--silent、--admin-job、app_dir、主題、托盤啟動
  config.json                 # 首次啟動時由遷移自動補鍵（不手改）
  config.json.pre-m5.bak      # 遷移時自動產生的一次性備份
  requirements.txt            # 不變（仍只有 PySide6-Essentials）
  requirements-dev.txt        # 新增：pyinstaller==6.22.3
  WSL Deck.spec               # 新增：PyInstaller onedir 設定
  build.ps1                   # 新增：一鍵建置
  app/
    paths.py                  # 新增：app_dir()、is_frozen()
    autostart.py              # 新增：HKCU Run 鍵讀寫
    config.py                 # 修改：舊鍵遷移、新設定驗證
    admin.py                  # 修改：凍結後改用 --admin-job
    ui/
      app_icon.py             # 新增：程式繪製的 QIcon（托盤／視窗）
      theme.py                # 新增：Fusion ＋ 深／淺 palette
      dialog_base.py          # 新增：從 backup_dialogs 抽出的共用對話框基底
      tray.py                 # 新增：QSystemTrayIcon 與選單
      settings_dialog.py      # 新增：設定對話框
      main_window.py          # 修改：托盤、關窗、設定、進階模式
      instance_card.py        # 修改：邊框改用 palette
      backup_dialogs.py       # 修改：改用 dialog_base.DialogBase（行為不變）
  tests/
    test_config.py            # 修改：遷移與新設定驗證
    test_autostart.py         # 新增
    test_theme.py             # 新增
    test_paths.py             # 新增
```

## 3. 資料變更（`config.json`）

| 鍵 | 型別 | 預設 | 說明 |
|----|------|------|------|
| `distro_root` | str | 既有值 | 預設安裝目錄；設定可改 |
| `backup_root` | str | 既有值 | 預設備份目錄；設定可改 |
| `poll_interval` | int | `10` | 3–600 秒；設定可改 |
| `theme` | str | `"system"` | `system`／`dark`／`light` |
| `close_to_tray` | bool | `true` | 關窗縮托盤 |
| `autostart` | bool | `false` | 開機自啟；僅打包後可寫入 |
| `advanced_mode` | bool | `false` | 日誌抽屜顯示實際命令 |
| `confirm_destructive` | bool | `true` | 既有鍵，保留 |
| `system_instances` | list[str] | `["docker-desktop", "docker-desktop-data"]` | 前綴比對 |
| `log_file` | str | `"logs/wsl-deck.log"` | 相對 config 所在目錄 |
| `commands`、`port_forwards` | dict／list | 既有值 | 不變 |

一次性遷移（`Config.load()` 內、驗證前）：

- `preview_commands` → `advanced_mode`（新鍵不存在時才複製）
- `minimize_to_tray` → `close_to_tray`（同上）
- 刪除兩個舊鍵；補齊 `DEFAULT_CONFIG` 中缺少的鍵（`commands` 除外）
- 有變更時先把原檔複製成 `config.json.pre-m5.bak`（僅第一次），再寫回

新驗證（`Config._validate`）：

- `advanced_mode`、`confirm_destructive`、`close_to_tray`、`autostart` 必須是 bool
- `theme` ∈ `{"system", "dark", "light"}`
- `poll_interval` 必須是 3–600 的 int（排除 bool）
- `system_instances` 必須是非空字串的 list

## 4. UI 變更

### 4.1 托盤

- `QSystemTrayIcon`，圖標由 `app_icon()` 以 QPainter 繪製（32×32 圓角方塊＋白色「W」，多尺寸加入 QIcon）。
- 單擊（Trigger）或雙擊（DoubleClick）→ 顯示主視窗。
- 右鍵選單：

| 項目 | 行為 | 啟用條件 |
|------|------|----------|
| 顯示主視窗 | `showNormal` ＋ `activateWindow` ＋ `raise_` | 永遠 |
| 啟動預設 instance | 呼叫既有 `_start(name)`；成功後沿用 M4 的啟動後自動套用 | 存在非系統的預設 instance 且未執行 |
| 全部關機 | 先顯示主視窗，再走既有 `_shutdown_all()`（保留含 docker-desktop 的警告） | 有執行中 instance |
| 重新套用網路 | 先顯示主視窗，再走 `_auto_apply_all(silent_empty=True)`；沒有規則時托盤氣泡提示 | 永遠 |
| 結束 | 真正退出（`_quitting=True` → `tray.hide()` → `QApplication.quit()`） | 永遠 |

- tooltip 顯示「WSL Deck｜執行中 N 個」，於每次 `_on_distros` 更新選單狀態。
- 托盤不可用時（`QSystemTrayIcon.isSystemTrayAvailable() == False`）→ 不建立托盤，關窗即結束，行為與現在相同。

### 4.2 關窗與啟動

- `closeEvent`：
  - `_quitting` 為真、或 `close_to_tray == false`、或托盤不可用 → 接受關閉並 `QApplication.quit()`。
  - 其餘 → `event.ignore()` ＋ `hide()`；第一次縮托盤時顯示氣泡「WSL Deck 仍在背景執行…」，之後不再重複。
- `--silent`：建立視窗但不呼叫 `show()`；托盤可用時只留托盤圖標。托盤不可用時退回顯示視窗。
- `app.setQuitOnLastWindowClosed(False)` 只在托盤可用時設定，避免關窗被 Qt 直接結束。

### 4.3 設定對話框（右下角齒輪）

| 欄位 | 控制項 | 驗證／行為 |
|------|--------|-----------|
| 預設安裝目錄 | `QLineEdit` ＋「瀏覽…」 | 不可空白；不強制存在 |
| 預設備份目錄 | `QLineEdit` ＋「瀏覽…」 | 不可空白；不強制存在 |
| 狀態輪詢間隔 | `QSpinBox` 3–600，後綴「秒」 | 儲存後重啟輪詢 timer |
| 主題 | `QComboBox`：跟隨系統／深色／淺色 | 立即套用 |
| 關閉視窗縮到托盤 | `QCheckBox` | 立即生效 |
| 開機自啟 | `QCheckBox` | 開發模式禁用並顯示說明；打包後寫註冊表 |
| 進階模式 | `QCheckBox`：「在日誌顯示實際執行的命令」 | 切換後立即影響日誌抽屜 |
| 系統 instance 清單 | `QLineEdit`，逗號分隔 | 去重、去空白；前綴比對 |

- 對話框沿用 `backup_dialogs.py` 的視覺：最小寬度 560、`QFormLayout`、錯誤紅字、底部「取消／儲存」高度 32、手型游標。
- 儲存流程：先寫註冊表（僅當 `autostart` 有變且支援），成功才寫 `config.json`；config 寫入失敗時把註冊表回復原值並提示。
- 儲存成功後由 `MainWindow` 套用：主題、輪詢 timer、`refresh()`（讓 `system_instances` 立即反映在卡片）。

### 4.4 主題

- 一律使用 `Fusion` style，確保 QPalette 在 Windows 上被完整套用。
- `system` 以 `QApplication.styleHints().colorScheme()` 判斷；`Unknown`（例如 Windows 10 或未回報）視為淺色。
- 監聽 `colorSchemeChanged`：目前是 `system` 時自動重套。
- 卡片 QSS 的 `#cfd4da`／`#e1e5ea` 改為 `palette(mid)`／`palette(dark)`；hover 的 `#4a90e2` 保留（深淺色都清楚）。

## 5. 任務

### Task 1：`paths.py`（開發／凍結路徑）

**Files：** Create：`wsl-deck/app/paths.py`、`wsl-deck/tests/test_paths.py`

- [ ] **Step 1：先寫測試**

```python
"""執行路徑測試。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app import paths


class AppDirTest(unittest.TestCase):
    def test_dev_dir_is_project_root(self) -> None:
        self.assertEqual(paths.app_dir(), Path(__file__).resolve().parent.parent)

    def test_frozen_dir_is_exe_parent(self) -> None:
        with patch.object(paths.sys, "frozen", True, create=True), \
             patch.object(paths.sys, "executable", r"C:\Apps\WSL Deck\WSL Deck.exe"):
            self.assertEqual(paths.app_dir(), Path(r"C:\Apps\WSL Deck"))

    def test_is_frozen_default_false(self) -> None:
        self.assertFalse(paths.is_frozen())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2：實作**

```python
"""可寫路徑：開發模式與 PyInstaller onedir 皆適用。"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """config.json 與 logs 的所在目錄；凍結後是 exe 所在資料夾。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
```

- [ ] **Step 3：跑測試**

```
.\.venv\Scripts\python.exe -m unittest tests.test_paths -q
```

預期：3 項通過。

### Task 2：`autostart.py`（HKCU Run）

**Files：** Create：`wsl-deck/app/autostart.py`、`wsl-deck/tests/test_autostart.py`

- [ ] **Step 1：先寫測試**

```python
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
```

- [ ] **Step 2：實作**

```python
"""開機自啟：只支援打包後的 exe，避免指向會搬動的 .venv。"""

from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "WSL Deck"


def build_run_command(exe: str) -> str:
    return f'"{exe}" --silent'


def is_supported() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return str(value).strip() == build_run_command(sys.executable)


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        raise RuntimeError("開發模式不支援開機自啟，請使用打包後的 exe")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(
                key, VALUE_NAME, 0, winreg.REG_SZ,
                build_run_command(sys.executable),
            )
            return
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
```

- [ ] **Step 3：跑測試**

```
.\.venv\Scripts\python.exe -m unittest tests.test_autostart -q
```

預期：3 項通過（開發模式下）。

### Task 3：`config.py` 舊鍵遷移與新設定驗證

**Files：** Modify：`wsl-deck/app/config.py`、`wsl-deck/tests/test_config.py`

- [ ] **Step 1：先寫測試**（加在 `ConfigTest` 內；檔案頂端補 `import json`）

```python
    def test_migrate_legacy_keys(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy.pop("advanced_mode", None)
        legacy.pop("close_to_tray", None)
        legacy["preview_commands"] = True
        legacy["minimize_to_tray"] = False
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = Config(self.path)
        self.assertTrue(migrated.data["advanced_mode"])
        self.assertFalse(migrated.data["close_to_tray"])
        self.assertNotIn("preview_commands", migrated.data)
        self.assertNotIn("minimize_to_tray", migrated.data)
        self.assertTrue(
            self.path.with_name("config.json.pre-m5.bak").exists()
        )

    def test_missing_keys_filled_on_load(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        for key in ("theme", "poll_interval", "system_instances"):
            legacy.pop(key, None)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        reloaded = Config(self.path)
        self.assertEqual(reloaded.data["theme"], "system")
        self.assertEqual(reloaded.data["poll_interval"], 10)
        self.assertEqual(
            reloaded.data["system_instances"],
            ["docker-desktop", "docker-desktop-data"],
        )

    def test_invalid_theme_rejected(self) -> None:
        self.config.data["theme"] = "blue"
        with self.assertRaises(ConfigError):
            self.config.save()

    def test_invalid_poll_interval_rejected(self) -> None:
        for value in (1, 601, "10", True):
            with self.subTest(value=value):
                self.config.data["poll_interval"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_invalid_system_instances_rejected(self) -> None:
        for value in ("docker-desktop", ["docker-desktop", ""], [1]):
            with self.subTest(value=value):
                self.config.data["system_instances"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()
```

- [ ] **Step 2：實作遷移**

`app/config.py` 頂端補 `import shutil`，並在 `DEFAULT_CONFIG` 下方加入：

```python
LEGACY_KEYS = {
    "preview_commands": "advanced_mode",
    "minimize_to_tray": "close_to_tray",
}
MIGRATION_BACKUP_SUFFIX = ".pre-m5.bak"
```

`Config.load()` 改成：

```python
    def load(self) -> None:
        if not self.path.exists():
            self.data = json.loads(json.dumps(DEFAULT_CONFIG))
            self.save()
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置檔格式錯誤：{exc}") from exc
        if self._migrate():
            backup = self.path.with_name(self.path.name + MIGRATION_BACKUP_SUFFIX)
            if not backup.exists():
                shutil.copy2(self.path, backup)
            self.save()
        else:
            self._validate()

    def _migrate(self) -> bool:
        """補齊預設鍵並把 M5 前的舊鍵換成新鍵；回傳是否有變更。"""
        changed = False
        for old, new in LEGACY_KEYS.items():
            if old in self.data:
                if new not in self.data:
                    self.data[new] = bool(self.data[old])
                del self.data[old]
                changed = True
        for key, value in DEFAULT_CONFIG.items():
            if key == "commands":
                continue
            if key not in self.data:
                self.data[key] = json.loads(json.dumps(value))
                changed = True
        return changed
```

> 注意：`save()` 內會呼叫 `_validate()`，因此遷移寫回前已驗證；`else` 分支保留原本行為。

- [ ] **Step 3：實作新設定驗證**

在 `_validate()` 的 `port_forwards` 檢查前加入：

```python
        for key in ("advanced_mode", "confirm_destructive", "close_to_tray", "autostart"):
            value = self.data.get(key, DEFAULT_CONFIG[key])
            if not isinstance(value, bool):
                raise ConfigError(f"{key} 必須是布林值")
        theme = self.data.get("theme", DEFAULT_CONFIG["theme"])
        if theme not in ("system", "dark", "light"):
            raise ConfigError(f"theme 必須是 system／dark／light：{theme}")
        interval = self.data.get("poll_interval", DEFAULT_CONFIG["poll_interval"])
        if (
            not isinstance(interval, int)
            or isinstance(interval, bool)
            or not 3 <= interval <= 600
        ):
            raise ConfigError("poll_interval 必須是 3-600 的整數")
        instances = self.data.get("system_instances", DEFAULT_CONFIG["system_instances"])
        if not isinstance(instances, list) or not all(
            isinstance(item, str) and item.strip() for item in instances
        ):
            raise ConfigError("system_instances 必須是非空字串的陣列")
```

- [ ] **Step 4：跑測試**

```
.\.venv\Scripts\python.exe -m unittest tests.test_config -q
```

預期：原 10 項＋新增 5 項通過。

- [ ] **Step 5：實際遷移本專案 `config.json`**

```
.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.config import Config; c = Config(Path('config.json')); print(c.data['advanced_mode'], c.data['close_to_tray'], c.data['theme'])"
```

預期：`True True system`，且目錄出現 `config.json.pre-m5.bak`（舊鍵 `preview_commands` 被移除）。

### Task 4：`theme.py`、`app_icon.py` 與卡片 QSS

**Files：** Create：`wsl-deck/app/ui/theme.py`、`wsl-deck/app/ui/app_icon.py`、`wsl-deck/tests/test_theme.py`；Modify：`wsl-deck/app/ui/instance_card.py`

- [ ] **Step 1：先寫測試**

```python
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
```

- [ ] **Step 2：實作 `theme.py`**

```python
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
```

- [ ] **Step 3：實作 `app_icon.py`**

```python
"""以 QPainter 產生圖標，不依賴外部圖檔。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2d7ff9"))
        painter.drawRoundedRect(
            1, 1, size - 2, size - 2, size * 0.22, size * 0.22
        )
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(max(6, int(size * 0.58)))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
        painter.end()
        icon.addPixmap(pixmap)
    return icon
```

- [ ] **Step 4：卡片邊框改用 palette**

`app/ui/instance_card.py` 的 QSS 由：

```
border: 1px solid #cfd4da;
...
border-color: #e1e5ea;
```

改為：

```
border: 1px solid palette(mid);
...
border-color: palette(dark);
```

（`#4a90e2` 的 hover 邊框、`#9aa0a6` 的禁用文字、綠／紅圖標都不動。）

- [ ] **Step 5：跑測試**

```
.\.venv\Scripts\python.exe -m unittest tests.test_theme -q
```

預期：3 項通過。

### Task 5：`dialog_base.py` 抽取與 `settings_dialog.py`

**Files：** Create：`wsl-deck/app/ui/dialog_base.py`、`wsl-deck/app/ui/settings_dialog.py`；Modify：`wsl-deck/app/ui/backup_dialogs.py`

- [ ] **Step 1：把 `_DialogBase` 抽到 `dialog_base.py`**

- 內容為 `backup_dialogs.py` 現有 `_DialogBase` 原樣搬移，改名 `DialogBase`，並保留 `set_ok_text`、`show_error`、`add_info`、`_row_with_button`。
- `backup_dialogs.py` 移除該類別，改為 `from app.ui.dialog_base import DialogBase`，四個對話框的父類別改名為 `DialogBase`。
- 行為與外觀不變；不需要新測試，靠既有 42 項與 GUI 驗收確認。

- [ ] **Step 2：實作 `SettingsDialog`**

```python
"""設定對話框：只收集值，寫入與套用由 MainWindow 負責。"""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QLineEdit, QSpinBox,
)

from app.autostart import is_supported
from app.config import Config
from app.ui.dialog_base import DialogBase

THEME_LABELS = (
    ("跟隨系統", "system"),
    ("深色", "dark"),
    ("淺色", "light"),
)


class SettingsDialog(DialogBase):
    def __init__(self, config: Config, parent=None):
        super().__init__("設定", parent, width=580)
        self.set_ok_text("儲存")

        self._distro_edit = QLineEdit(str(config.get("distro_root", "")))
        self._form.addRow(
            "預設安裝目錄",
            self._row_with_button(
                self._distro_edit, "瀏覽…",
                lambda: self._browse(self._distro_edit),
            ),
        )
        self._backup_edit = QLineEdit(str(config.get("backup_root", "")))
        self._form.addRow(
            "預設備份目錄",
            self._row_with_button(
                self._backup_edit, "瀏覽…",
                lambda: self._browse(self._backup_edit),
            ),
        )

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(3, 600)
        self._poll_spin.setSuffix(" 秒")
        self._poll_spin.setValue(int(config.get("poll_interval", 10)))
        self._form.addRow("狀態輪詢間隔", self._poll_spin)

        self._theme_combo = QComboBox()
        for label, value in THEME_LABELS:
            self._theme_combo.addItem(label, value)
        index = self._theme_combo.findData(config.get("theme", "system"))
        self._theme_combo.setCurrentIndex(max(0, index))
        self._form.addRow("主題", self._theme_combo)

        self._tray_check = QCheckBox("關閉視窗時縮到托盤")
        self._tray_check.setChecked(bool(config.get("close_to_tray", True)))
        self._form.addRow("托盤", self._tray_check)

        self._autostart_check = QCheckBox("開機時自動啟動（啟動後進托盤）")
        self._autostart_check.setChecked(bool(config.get("autostart", False)))
        self._autostart_check.setEnabled(is_supported())
        self._form.addRow("開機自啟", self._autostart_check)
        if not is_supported():
            self.add_info("開機自啟只支援打包後的 exe；開發模式（.venv）下無法寫入登錄檔。")

        self._advanced_check = QCheckBox("在日誌顯示實際執行的命令")
        self._advanced_check.setChecked(bool(config.get("advanced_mode", False)))
        self._form.addRow("進階模式", self._advanced_check)

        self._system_edit = QLineEdit(
            ", ".join(config.get("system_instances", []))
        )
        self._form.addRow("系統 instance 清單", self._system_edit)
        self.add_info("以逗號分隔，採前綴比對；例如 docker-desktop 會涵蓋 docker-desktop-data。")

        self._ok_btn.clicked.connect(self._on_ok)

    def _browse(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "選擇資料夾", edit.text())
        if path:
            edit.setText(path)

    def values(self) -> dict:
        instances: list[str] = []
        for item in re.split(r"[,，]", self._system_edit.text()):
            name = item.strip()
            if name and name not in instances:
                instances.append(name)
        return {
            "distro_root": self._distro_edit.text().strip(),
            "backup_root": self._backup_edit.text().strip(),
            "poll_interval": int(self._poll_spin.value()),
            "theme": str(self._theme_combo.currentData()),
            "close_to_tray": self._tray_check.isChecked(),
            "autostart": self._autostart_check.isChecked(),
            "advanced_mode": self._advanced_check.isChecked(),
            "system_instances": instances,
        }

    def _on_ok(self) -> None:
        values = self.values()
        if not values["distro_root"] or not values["backup_root"]:
            self.show_error("預設安裝目錄與備份目錄不可空白")
            return
        if not values["system_instances"]:
            self.show_error("系統 instance 清單不可空白；至少保留 docker-desktop")
            return
        self.accept()
```

- [ ] **Step 3：匯入檢查**

```
.\.venv\Scripts\python.exe -c "from app.ui.settings_dialog import SettingsDialog; print(SettingsDialog.__name__)"
```

預期：`SettingsDialog`。

### Task 6：`tray.py`

**Files：** Create：`wsl-deck/app/ui/tray.py`

- [ ] **Step 1：實作**

```python
"""托盤圖標與右鍵選單。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.ui.app_icon import app_icon


class TrayController(QObject):
    show_requested = Signal()
    start_default_requested = Signal()
    shutdown_all_requested = Signal()
    reapply_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tray: QSystemTrayIcon | None = None
        self._start_action = None
        self._shutdown_action = None
        if not self._available:
            return

        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("WSL Deck")
        menu = QMenu()
        show_action = menu.addAction("顯示主視窗")
        show_action.triggered.connect(lambda: self.show_requested.emit())
        self._start_action = menu.addAction("啟動預設 instance")
        self._start_action.triggered.connect(
            lambda: self.start_default_requested.emit()
        )
        self._shutdown_action = menu.addAction("全部關機")
        self._shutdown_action.triggered.connect(
            lambda: self.shutdown_all_requested.emit()
        )
        reapply_action = menu.addAction("重新套用網路規則")
        reapply_action.triggered.connect(lambda: self.reapply_requested.emit())
        menu.addSeparator()
        quit_action = menu.addAction("結束")
        quit_action.triggered.connect(lambda: self.quit_requested.emit())

        self._menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._start_action.setEnabled(False)
        self._shutdown_action.setEnabled(False)
        self._tray.show()

    @property
    def available(self) -> bool:
        return self._available

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()

    def update_state(self, has_default: bool, default_running: bool, running: int) -> None:
        if self._tray is None:
            return
        self._start_action.setEnabled(has_default and not default_running)
        self._shutdown_action.setEnabled(running > 0)
        self._tray.setToolTip(f"WSL Deck｜執行中 {running} 個")

    def show_message(self, title: str, text: str) -> None:
        if self._tray is not None:
            self._tray.showMessage(title, text, app_icon(), 4000)

    def hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()
```

- [ ] **Step 2：匯入檢查（不建立托盤）**

```
.\.venv\Scripts\python.exe -c "from app.ui.tray import TrayController; print(TrayController.__name__)"
```

預期：`TrayController`。

### Task 7：`MainWindow` 整合（托盤、關窗、設定、進階模式）

**Files：** Modify：`wsl-deck/app/ui/main_window.py`

> 動工前先重讀本檔並比對 SHA256 `30365B484DC4`；若不同，先確認差異來源（可能是 M4 會話的修正）。

- [ ] **Step 1：匯入與初始化**

```python
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import QApplication

from app.autostart import is_supported, set_enabled as set_autostart
from app.ui.app_icon import app_icon
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import apply_theme
from app.ui.tray import TrayController
```

`__init__` 增加：

```python
        self._quitting = False
        self._tray_hint_shown = False
        self.setWindowIcon(app_icon())
        ...
        self._tray = TrayController(self)
        if self._tray.available:
            app = QApplication.instance()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
            self._connect_tray_signals()
```

`_settings_btn` 改為：

```python
        self._settings_btn.setToolTip("設定")
        self._settings_btn.setEnabled(True)
        self._settings_btn.clicked.connect(self._open_settings)
```

- [ ] **Step 2：托盤訊號與視窗還原**

```python
    @property
    def tray_available(self) -> bool:
        return self._tray.available

    def _connect_tray_signals(self) -> None:
        self._tray.show_requested.connect(self._restore_window)
        self._tray.start_default_requested.connect(self._tray_start_default)
        self._tray.shutdown_all_requested.connect(self._tray_shutdown_all)
        self._tray.reapply_requested.connect(self._tray_reapply)
        self._tray.quit_requested.connect(self._quit_app)

    def _restore_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_start_default(self) -> None:
        distro = next(
            (
                item for item in self._distros
                if item.is_default and not self._is_system(item.name)
            ),
            None,
        )
        if distro is None:
            self._restore_window()
            QMessageBox.information(
                self, "啟動預設 instance", "找不到可啟動的預設 instance。"
            )
            return
        if distro.running:
            self._restore_window()
            self._show_detail(distro)
            return
        self._start(distro.name)

    def _tray_shutdown_all(self) -> None:
        self._restore_window()
        self._shutdown_all()

    def _tray_reapply(self) -> None:
        self._restore_window()
        if not self._auto_apply_all(silent_empty=True):
            self._tray.show_message(
                "重新套用網路規則", "目前沒有需要重套的規則。"
            )

    def _quit_app(self) -> None:
        self._quitting = True
        self._tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()
```

- [ ] **Step 3：更新托盤狀態**

`_on_distros()` 在更新 `_shutdown_btn` 後加入：

```python
        default = next(
            (
                item for item in distros
                if item.is_default and not self._is_system(item.name)
            ),
            None,
        )
        self._tray.update_state(
            has_default=default is not None,
            default_running=bool(default and default.running),
            running=running,
        )
```

- [ ] **Step 4：關窗行為**

```python
    def closeEvent(self, event: QCloseEvent) -> None:
        if (
            self._quitting
            or not self.config.get("close_to_tray", True)
            or not self._tray.available
        ):
            self._quitting = True
            self._tray.hide()
            event.accept()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self._tray.show_message(
                "WSL Deck 仍在背景執行",
                "可從托盤圖標重新開啟，或選擇「結束」離開。",
            )
```

- [ ] **Step 5：設定套用**

```python
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        old = {key: self.config.get(key) for key in values}
        autostart_changed = bool(values["autostart"]) != bool(
            self.config.get("autostart", False)
        )
        if is_supported() and autostart_changed:
            try:
                set_autostart(bool(values["autostart"]))
            except (OSError, RuntimeError) as exc:
                QMessageBox.warning(self, "開機自啟設定失敗", str(exc))
                return

        self.config.data.update(values)
        try:
            self.config.save()
        except ConfigError as exc:
            self.config.data.update(old)
            if is_supported() and autostart_changed:
                try:
                    set_autostart(bool(old["autostart"]))
                except (OSError, RuntimeError):
                    logger.warning("回復開機自啟設定失敗")
            QMessageBox.warning(self, "設定未儲存", str(exc))
            return

        self._apply_settings()

    def _apply_settings(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, str(self.config.get("theme", "system")))
        interval = max(3, int(self.config.get("poll_interval", 10))) * 1000
        self._timer.start(interval)
        logger.info("設定已更新")
        self.refresh()

    def _watch_color_scheme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)

    def _on_color_scheme_changed(self, _scheme) -> None:
        if self.config.get("theme", "system") == "system":
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, "system")
```

`__init__` 末尾（`QTimer.singleShot(0, self.refresh)` 前）加入 `self._watch_color_scheme()`。

- [ ] **Step 6：進階模式過濾命令列**

```python
    def _append_log(self, message: str) -> None:
        if (
            not self.config.get("advanced_mode", False)
            and "管理員命令：" in message
        ):
            return
        self._log_view.appendPlainText(message)
        if "ERROR" in message:
            self._log_toggle.setChecked(True)
```

- [ ] **Step 7：`_auto_apply_all` 增加 `silent_empty`**

```python
    def _auto_apply_all(self, silent_empty: bool = False) -> bool:
        targets: list[tuple[str, list[dict]]] = []
        for distro in self._distros:
            if not distro.running or self._is_system(distro.name):
                continue
            rules = self.config.port_forwards_for(distro.name)
            if rules:
                targets.append((distro.name, rules))
        if not targets:
            if not silent_empty:
                logger.info("沒有需要重套的網路規則")
            return False
        logger.info("重新套用 %d 個 instance 的網路規則…", len(targets))
        self._run_operation(
            "重新套用網路規則",
            partial(apply_rules, targets),
            self._on_auto_apply_done,
            lambda _message: self.refresh(),
        )
        return True
```

（既有呼叫端 `QTimer.singleShot(0, self._auto_apply_all)` 與 `_on_distros` 不需修改。）

- [ ] **Step 8：編譯與測試**

```
.\.venv\Scripts\python.exe -m py_compile app\ui\main_window.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：`Ran 56 tests ... OK`（42＋`test_paths` 3＋`test_autostart` 3＋`test_theme` 3＋`test_config` 新增 5）。

> 這裡只驗證匯入與既有測試；托盤與關窗行為留到 §7 的 GUI 驗收。

### Task 8：`main.py` 入口

**Files：** Modify：`wsl-deck/main.py`

- [ ] **Step 1：改寫入口**

```python
"""WSL Deck 入口（含 --silent 與打包後的 --admin-job）。"""

from __future__ import annotations

import logging
import sys

from app.paths import app_dir


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["--admin-job"] and len(argv) == 3:
        from app.admin import main as admin_main
        return admin_main(argv[1:])

    silent = "--silent" in argv
    argv = [arg for arg in argv if arg != "--silent"]

    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.config import Config, ConfigError
    from app.logbus import setup_logging
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme

    app = QApplication([sys.argv[0], *argv])
    app.setApplicationName("WSL Deck")
    app.setOrganizationName("WSL Deck")

    try:
        config = Config(app_dir() / "config.json")
    except ConfigError as exc:
        QMessageBox.critical(None, "配置錯誤", str(exc))
        return 1

    setup_logging(config.resolve_path(config.data["log_file"]))
    apply_theme(app, str(config.get("theme", "system")))
    logging.getLogger(__name__).info("WSL Deck 啟動，配置：%s", config.path)

    window = MainWindow(config)
    if not (silent and window.tray_available):
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

> `--admin-job` 分支必須在任何 Qt import 之前；凍結後由提權子進程以 `WSL Deck.exe --admin-job <job> <result>` 呼叫。

- [ ] **Step 2：驗證開發模式啟動**

```
.\.venv\Scripts\python.exe -c "import main; print(main.main.__name__)"
```

預期：`main`（不要在此步驟實際開啟 GUI，會在沙箱被回收）。

### Task 9：`admin.py` 凍結入口

**Files：** Modify：`wsl-deck/app/admin.py`

- [ ] **Step 1：加入啟動器選擇**

```python
def _admin_launcher(job_path: Path, result_path: Path) -> tuple[str, str, str]:
    """回傳（執行檔, PowerShell ArgumentList, 工作目錄）。"""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        return exe, f'--admin-job "{job_path}" "{result_path}"', str(Path(exe).parent)
    project = Path(__file__).resolve().parent.parent
    return exe, f'-m app.admin "{job_path}" "{result_path}"', str(project)
```

`run_admin_job()` 內原本的：

```python
    project = Path(__file__).resolve().parent.parent
    arg_string = f'-m app.admin "{job_path}" "{result_path}"'
```

改成：

```python
    exe, arg_string, work_dir = _admin_launcher(job_path, result_path)
```

並把 PowerShell 腳本中的 `sys.executable` 改成 `exe`、`str(project)` 改成 `work_dir`。

- [ ] **Step 2：驗證開發模式不受影響**

```
.\.venv\Scripts\python.exe -c "import tempfile; from pathlib import Path; from app.admin import _admin_launcher; print(_admin_launcher(Path(tempfile.gettempdir()) / 'j.json', Path(tempfile.gettempdir()) / 'r.json'))"
```

預期：`('...python.exe', '-m app.admin "...j.json" "...r.json"', '...wsl-deck')`。

- [ ] **Step 3：實測一次空 job（會跳 UAC）**

由使用者在 PowerShell 手動執行（AI 沙箱無法完成 UAC）：

```powershell
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -c "from app.admin import run_admin_job; print(run_admin_job({'portproxy_delete': [], 'portproxy_add': [], 'firewall_add': [], 'firewall_delete': []}))"
```

預期：跳一次 UAC；允許後 `ok=True`，取消後 `denied=True`。

### Task 10：打包（PyInstaller onedir）

**Files：** Create：`wsl-deck/requirements-dev.txt`、`wsl-deck/WSL Deck.spec`、`wsl-deck/build.ps1`

- [ ] **Step 1：安裝 dev 依賴**

`requirements-dev.txt`：

```
pyinstaller==6.22.3
```

```
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

預期：安裝成功；若 PyInstaller 對 Python 3.14 報錯，先回報再改用 Python 3.13 建置 venv（見 §8 風險）。

- [ ] **Step 2：`WSL Deck.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["app.admin"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WSL Deck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WSL Deck",
)
```

- [ ] **Step 3：`build.ps1`**

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $root "build"
$dist = Join-Path $root "dist"

& "$root\.venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm --clean `
    --workpath $work `
    --distpath $dist `
    "$root\WSL Deck.spec"

$exe = Join-Path $dist "WSL Deck\WSL Deck.exe"
if (-not (Test-Path $exe)) {
    throw "建置失敗：找不到 $exe"
}

$config = Join-Path $dist "WSL Deck\config.json"
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $root "config.json") $config
}

Write-Host "完成：$exe"
```

- [ ] **Step 4：建置**

```
cd d:\VirtualMachiles\wsl\wsl-deck
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

預期：產出 `dist\WSL Deck\WSL Deck.exe`（約 80–120 MB 的 onedir），並複製 `config.json`。

- [ ] **Step 5：更新捷徑（依決策 5）**

若決定讓 `WSL Deck.lnk` 指向 exe：

```powershell
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut("d:\VirtualMachiles\wsl\wsl-deck\WSL Deck.lnk")
$lnk.TargetPath = "d:\VirtualMachiles\wsl\wsl-deck\dist\WSL Deck\WSL Deck.exe"
$lnk.Arguments = ""
$lnk.WorkingDirectory = "d:\VirtualMachiles\wsl\wsl-deck\dist\WSL Deck"
$lnk.IconLocation = "d:\VirtualMachiles\wsl\wsl-deck\dist\WSL Deck\WSL Deck.exe,0"
$lnk.Save()
```

- [ ] **Step 6：凍結版冒煙**

由使用者手動執行：

```powershell
& "d:\VirtualMachiles\wsl\wsl-deck\dist\WSL Deck\WSL Deck.exe" --silent
```

預期：沒有主視窗，托盤出現 WSL Deck；單擊托盤顯示主視窗；在詳情頁按「立即套用」仍只跳一次 UAC（代表 `--admin-job` 入口有效）。

## 6. 測試策略

### 6.1 自動測試（全部在 `.venv`）

| 測試檔 | 覆蓋 |
|--------|------|
| `tests/test_paths.py` | 開發／凍結路徑選擇 |
| `tests/test_autostart.py` | 自啟命令引號、開發模式拒寫 |
| `tests/test_theme.py` | `resolve_mode`、深色 palette 色值 |
| `tests/test_config.py`（擴充） | 舊鍵遷移、缺鍵補齊、新設定驗證 |

執行：

```
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：原 42 項＋新增 11 項以上全部通過；不得出現 `SKIP` 或依賴真實註冊表的測試。

### 6.2 不在自動測試範圍（以手動驗收）

- `QSystemTrayIcon`、`closeEvent`、`--silent`、主題即時切換、開機自啟註冊表、PyInstaller 產物與 UAC 子進程。
- 原因：托盤與註冊表屬系統整合，沙箱無法可靠模擬；且既有專案沒有 UI 測試基礎，不為 M5 引入 offscreen 測試框架。

## 7. 驗收步驟

> 只對測試 instance 操作；破壞性測試不得作用於 `ubuntu`、`node22`、`alms`、`docker-desktop`。

1. **單元測試**：§6.1 全部通過。
2. **設定持久化**：右下角齒輪 → 改輪詢間隔為 15 秒、主題改深色、關閉「關窗縮托盤」→ 儲存 → 重開 App，設定仍在。
3. **托盤與關窗**：開啟「關窗縮托盤」→ 按視窗關閉 → 視窗消失、托盤圖標仍在並出現一次氣泡 → 單擊托盤 → 視窗回來。
4. **托盤選單**：
   - 顯示主視窗：可用。
   - 啟動預設 instance：對非系統的預設 instance 可用；啟動後若該 instance 有規則，會自動跳一次 UAC 並回到「已套用」。
   - 全部關機：會先顯示主視窗並列出所有執行中 instance（含 docker-desktop）的警告。
   - 重新套用網路規則：有規則時跳一次 UAC；無規則時顯示托盤提示。
   - 結束：托盤與視窗都消失，工作管理員沒有殘留 `WSL Deck.exe`。
5. **`--silent`**：
   ```
   .\.venv\Scripts\python.exe main.py --silent
   ```
   預期：只出現托盤，主視窗不顯示；單擊托盤可開啟。關閉「關窗縮托盤」時，`--silent` 仍在托盤，因為只影響關窗行為。
6. **主題**：
   - 深色／淺色切換後，卡片、詳情頁摘要、表格、日誌抽屜都可讀；卡片邊框不過亮。
   - 選「跟隨系統」後在 Windows 設定切換深／淺色（或改 `HKCU\...\Personalize\AppsUseLightTheme`），App 應跟隨；Windows 10 回報 Unknown 時固定淺色屬預期。
7. **進階模式**：
   - 關閉時，日誌抽屜不顯示「管理員命令：…」。
   - 開啟時，套用網路規則後抽屜會顯示管理員命令。
   - `logs\wsl-deck.log` 不論開關都保留命令紀錄。
8. **開機自啟（打包後）**：
   - 安裝並執行 `dist\WSL Deck\WSL Deck.exe` → 設定勾選開機自啟 → 儲存。
   - `Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'WSL Deck'` 顯示 `"...\WSL Deck.exe" --silent`。
   - 手動執行該命令 → 只出現托盤，代表登入時的行為。
   - 重新開機（或登出再登入）→ 托盤自動出現；此時若要驗證 M4 規則，需再由托盤或 GUI 啟動 instance，啟動成功後會自動重套（一次 UAC）。
   - 取消勾選 → 儲存 → 登錄值消失。
9. **打包產物**：
   - `dist\WSL Deck\WSL Deck.exe` 可雙擊執行，不需 Python；`config.json`、`logs` 位於 exe 同層。
   - 關窗縮托盤、`--silent`、設定、主題、備份（M3）、網路套用（M4，一次 UAC）都可用。
   - 從 exe 執行「立即套用」成功，代表 `--admin-job` 生效。
10. **清理**：刪除測試 instance、測試備份、測試 portproxy 與防火牆規則；保留 `dist` 供日常使用。

## 8. 風險與回滾

| 風險 | 對策 |
|------|------|
| **專案沒有 git，改壞難以回復** | 動工前建立快照 `d:\VirtualMachiles\wsl\_m5-snapshots\<timestamp>\`，複製 `wsl-deck\app`、`main.py`、`config.json`、`tests`、`requirements*.txt`；驗收通過後可刪。若使用者同意，改為先 `git init`（決策 6） |
| 與另一會話的 M4 修正衝突 | Phase B 前重讀 `main_window.py`／`admin.py`／`config.py` 並比對 §1.7 SHA256；若已變動，以對方版本為底重套 M5 變更，不整檔覆蓋 |
| config 遷移刪除舊鍵後不可逆 | 遷移前自動複製 `config.json.pre-m5.bak`（僅第一次）；必要時改名還原 |
| 註冊表寫入失敗或殘留 | 設定先寫註冊表、成功才存 config；config 存檔失敗時回復註冊表；手動清除 `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "WSL Deck" /f` |
| 托盤不可用（Explorer 重啟、遠端工作階段） | `isSystemTrayAvailable()` 為假時退回「關窗即結束」；托盤圖標消失時重啟 App 或重登入 |
| `--silent` 啟動時若需顯示對話框（例如規則套用失敗） | 錯誤只寫日誌與托盤氣泡，不彈模態框；托盤觸發的操作會先 `_restore_window()` 再開對話框 |
| Fusion 樣式與原本 Windows 外觀略有差異 | 深色主題必須用 Fusion；淺色也統一用 Fusion 以免 palette 被原生樣式覆蓋（決策 2） |
| PyInstaller 對 Python 3.14 支援問題 | 先只安裝 6.22.3 並建置；若失敗，改用 3.13 建置專用 venv（`.venv-build`）或 Nuitka，需回報後再調整 |
| 凍結版提權子進程失效 | Task 9 同時保留開發／凍結兩條路徑；Task 10 Step 6 必測一次 UAC；失敗時退回「以管理員啟動 App」的提示 |
| onedir 體積與防毒誤判 | 約 80–120 MB 可接受；不開 UPX；若防毒隔離，加入白名單或改用目錄式部署 |
| 多實例（自啟＋手動再開）造成重複托盤 | 本計畫不做互斥（決策 7）；重複圖標時以「結束」逐一關閉，後續再評估 `QLocalServer` |
| 深色主題下仍有寫死顏色 | 只改卡片邊框；`#7f8c8d`、`#c0392b`、`#4a90e2` 等語意色在深淺色皆可讀，其餘沿用 palette |

**回滾方式（依變更類型）：**

1. 程式碼：還原 §8 快照中的 `app`、`main.py`、`tests`（或 git 回到上一個 commit）。
2. 設定：停用開機自啟；必要時以 `config.json.pre-m5.bak` 覆蓋 `config.json`。
3. 註冊表：`reg delete ... /v "WSL Deck" /f`。
4. 打包：刪除 `dist`、`build`、`WSL Deck.spec`、`build.ps1`、`requirements-dev.txt`；把 `WSL Deck.lnk` 還原為原目標 `pythonw.exe "d:\VirtualMachiles\wsl\wsl-deck\main.py"`。
5. 主題：把 `config.json` 的 `theme` 改回 `system`，或在設定切回跟隨系統。

## 9. 待拍板決策

1. **實作順序**：同意 §1.6 的 Phase A（新模組）→ Phase B（等 M4 收尾後整合 `MainWindow`）→ Phase C（打包）？或是等 M4 GUI 驗收全部通過後再一次性動工？
2. **主題樣式**：同意一律切到 `Fusion`（深／淺色都由 QPalette 控制，接受與目前 Windows 原生控制項略有差異）？或只深色用 Fusion、淺色保留原生樣式？
3. **托盤／exe 圖標**：同意用 `app_icon.py` 程式繪製（不新增圖檔、exe 使用 PyInstaller 預設圖標）？或要求產生 `.ico`（需額外 Pillow dev 依賴）並套用到 exe？
4. **開機自啟範圍**：同意只在打包後的 exe 支援（開發模式禁用並顯示說明）？或也要在開發模式寫入指向 `.venv\Scripts\pythonw.exe main.py --silent` 的登錄值？
5. **捷徑**：同意把既有 `WSL Deck.lnk` 改指向 `dist\WSL Deck\WSL Deck.exe`（不再保留開發用捷徑）？或另建一個 `WSL Deck (dev).lnk` 並保留原本捷徑？
6. **版本控制**：同意先 `git init` 並做一次基線 commit（回滾最可靠）？或只用 §8 的時間戳快照？
7. **單一實例**：M5 不做多實例互斥（可能出現兩個托盤圖標），可接受？或要把 `QLocalServer` 單一實例列入 M5？
8. **進階模式的顯示範圍**：目前僅控制日誌抽屜是否顯示「管理員命令：…」；是否也要把 `wsl.exe`／`netsh` 的完整命令都納入（需在資料層補命令日誌）？
9. **打包 `config.json`**：同意建置時若 `dist` 內沒有 `config.json` 就複製一份（沿用目前路徑與規則）？或讓 exe 首次啟動一律用預設值？

## 10. 確認清單

- [ ] 同意 M5 範圍＝handoff 第 7 節（托盤、開機自啟、設定、主題、打包）＋舊 config 鍵遷移。
- [ ] 同意新增 `paths.py`、`autostart.py`、`theme.py`、`tray.py`、`settings_dialog.py`、`app_icon.py`、`dialog_base.py`。
- [ ] 同意 `MainWindow` 只在 Phase B 修改，且動工前重讀並比對 SHA256，避免覆蓋 M4 會話的修正。
- [ ] 同意設定儲存順序：先寫註冊表、成功後才寫 `config.json`。
- [ ] 同意主題統一使用 Fusion ＋ QPalette，並把卡片邊框改為 palette 顏色。
- [ ] 同意打包為 PyInstaller onedir，提權改走 `--admin-job` exe 入口。
- [ ] 同意 §8 的快照回滾方式（或依決策 6 改為 git）。
- [ ] 回答 §9 的 9 個決策點；確認後才開始實作，完成後回報並等待 GUI 驗收。
