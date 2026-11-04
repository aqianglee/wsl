# M6 實作計畫：主頁視圖切換 ＋ Instance 設定

> 狀態：**待確認**（確認後才動工）
> 上層文件：[wsl-deck-m5.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m5.md)、[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)
> 目標：主頁可在「卡片」與「表格」兩種視圖間即時切換並記住選擇；詳情頁名稱列最右側新增「⚙ 設定」，可在此 Instance 內 UI 化調整 WSL 設定與維護磁碟。

**Goal：** 讓主頁在高密度掃視（表格）與直觀操作（卡片）之間自由切換，並把 `wsl.conf` 與 VHD 維護從命令行搬進 GUI。

**Architecture：** 新增 `app/ui/view_toggle.py`（純 UI 切換器）、`app/ui/instance_table.py`（表格牆）、`app/distro_settings.py`（`wsl.conf` 讀寫、使用者校驗、版本／Sparse／壓縮）、`app/ui/instance_settings_dialog.py`（設定對話框）；`app/ui/icons.py` 抽出既有 QPainter 圖標供卡片與表格共用；`MainWindow` 以 `QStackedWidget` 承載兩個 `QScrollArea`，切換只改索引，不動資料流。

**Tech Stack：** Python 3.14.2、PySide6-Essentials 6.12.0、`wsl.exe`、`fsutil`、`unittest`。

---

## 0. 已核實事實（2026-11-03）

| 項目 | 結論 | 來源 |
|------|------|------|
| 本機 WSL | 版本 3.0.3.0，核心 6.18.54.1-1 | `wsl.exe --version` |
| `wsl --manage` | 支援 `--set-sparse <true\|false>`、`--set-default-user <user>`、`--resize`、`--compact` | `wsl.exe --help` |
| 現有 instance | ubuntu、node22、alms、wsl-mysql、docker-desktop，全部 Stopped，Version 2 | `wsl.exe -l -v` |
| 註冊表 | 5 個 instance 的 `DefaultUid` 皆為 `0`；未見 Sparse 相關值 | `HKCU\...\Lxss` |
| Sparse 偵測 | `fsutil sparse queryflag <vhdx>` 可讀，目前 5 個 VHD 皆 `NOT set as sparse`；免管理員 | 實測 |
| `wsl.conf` | 支援 `[automount]`、`[network]`、`[interop]`、`[user]`；systemd 在 `[boot] systemd=true` | [Microsoft Learn：wsl-config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) |
| 生效時機 | `wsl.conf` 變更需終止 distro 後再啟動才生效（8 秒規則） | 同上 |
| 既有測試 | `Ran 56 tests ... OK`；`windows_port 8080` 被占用屬既有提示 | `.venv\Scripts\python.exe -m unittest discover -s tests -q` |

> 決策：預設使用者**只寫 `/etc/wsl.conf` 的 `[user] default`**，不呼叫 `wsl --manage --set-default-user`。理由：`wsl.conf` 是官方文件化的 per-distro 設定，與 systemd／automount／interop 共用同一讀寫路徑；避免兩處來源（註冊表 `DefaultUid`）互相覆蓋。寫入後註冊表可能仍顯示舊值，屬預期。

## 0.1 工作區基線（無 git，動工前比對）

| 檔案 | SHA256 前 12 碼 | 最後修改 |
|------|-----------------|----------|
| `app/ui/main_window.py` | `34C9D621F3AD` | 2026-11-02 17:47:07 |
| `app/ui/card_wall.py` | `D9FEEADA42BB` | 2026-11-02 13:21:04 |
| `app/ui/instance_card.py` | `62B08AF53303` | 2026-11-02 16:58:33 |
| `app/ui/detail_page.py` | `45D80D41484F` | 2026-11-02 14:29:23 |
| `app/config.py` | `405D76A255B1` | 2026-11-02 16:57:36 |
| `app/wsl.py` | `5743FD21CB45` | 2026-10-30 16:58:19 |
| `config.json` | `121F99EA9E5F` | 2026-11-02 17:51:02 |
| `tests/test_config.py` | `7DB2612714D5` | 2026-11-02 16:57:49 |

動工前建立快照 `d:\VirtualMachiles\wsl\_m6-snapshots\<timestamp>\`，複製 `wsl-deck\app`、`main.py`、`config.json`、`tests`；驗收通過後可刪除。

## 1. 範圍

**做：**

- 主頁第二行右側兩個圖標（列表／卡片）即時切換視圖；`view_mode` 持久化。
- 表格視圖：愛心／系統圖標、名稱、操作三列；操作照搬卡片功能與樣式，另加「詳情」。
- 詳情頁名稱列最右側「⚙ 設定」按鈕與 Instance 設定對話框。
- 常用設定：預設使用者、systemd、appendWindowsPath、automount。
- 進階維護：WSL 版本 1/2、Sparse VHD、磁碟壓縮。
- 設定對話框的執行狀態互斥、使用者存在性校驗、`wsl.conf` 備份與讀回驗證。

**不做：**

- 不改卡片牆本身的行為與外觀（僅把圖標函式抽到 `icons.py`，輸出點陣圖完全一致）。
- 不動全域設定對話框（右下角齒輪）、網路規則、備份／還原／複製／刪除流程。
- 不做 `.wslconfig`（全域）編輯、不做開機自啟與托盤調整。
- 不引入 UI 自動化測試框架；GUI 以手動驗收。
- 不為表格加入排序、搜尋、狀態篩選、右鍵選單。
- 不對系統 instance（docker-desktop）開啟設定。

## 2. 檔案結構

```
wsl-deck/
  config.json                          # 遷移時自動補 view_mode（不手改）
  app/
    config.py                          # 修改：view_mode 預設鍵與驗證
    wsl.py                             # 修改：run_wsl 支援 stdin（寫 wsl.conf 用）
    distro_settings.py                 # 新增：wsl.conf 讀寫、使用者校驗、版本／Sparse／壓縮
    ui/
      icons.py                         # 新增：heart／prohibition／play／stop／list／grid 圖標
      instance_card.py                 # 修改：改用 icons.py，刪除本地圖標函式
      view_toggle.py                   # 新增：兩顆互斥圖標按鈕
      instance_table.py                # 新增：表格牆（表頭 + 列 + 操作欄）
      detail_page.py                   # 修改：名稱列最右側「⚙ 設定」與 settings_requested
      instance_settings_dialog.py      # 新增：Instance 設定對話框
      main_window.py                   # 修改：第二行工具列、雙視圖堆疊、兩個牆的資料同步、設定流程
  tests/
    test_config.py                     # 擴充：view_mode
    test_distro_settings.py            # 新增：wsl.conf 解析／合併／驗證、Sparse 解析
```

## 3. 資料變更（`config.json`）

| 鍵 | 型別 | 預設 | 說明 |
|----|------|------|------|
| `view_mode` | str | `"card"` | `card`／`list`；切換即儲存；非法值回退 `card` |

- `DEFAULT_CONFIG` 增鍵後，`Config._migrate()` 會自動補齊，沿用既有 `config.json.pre-m5.bak` 備份機制。
- `_validate()` 新增：`view_mode` 必須是 `card` 或 `list`。
- **不新增** per-instance 設定鍵：Instance 設定的真相來源是 distro 內的 `/etc/wsl.conf`，不寫進 config.json。

## 4. UI 規格

### 4.1 主頁第二行：視圖切換

```
┌──────────────────────────────────────────────────────────┐
│ WSL Deck                    [+ 新增 Instance] [全部關機] │
│                                       [▤] [▦]            │  ← 新增第二行，靠右
├──────────────────────────────────────────────────────────┤
│ 表頭 / 卡片牆                                            │
```

- 新行高 32px，與頂列間距沿用 `layout.setSpacing(10)`；兩顆 32×32 `QToolButton`，間距 4px，靠右對齊「+ 新增 Instance」正下方。
- 互斥（`QButtonGroup` exclusive）；當前模式：藍底 `#2D7FF9` + 白色圖標 + tooltip「卡片視圖」／「表格視圖」；非當前：`palette(button)` 底 + 中性圖標。
- 圖標以 QPainter 繪製（沿用專案不引入圖檔的做法）：
  - 列表：三條 12×2 圓角橫線，左側各一個 2×2 方點。
  - 卡片：2×2 四個 6×6 圓角方塊。
- 點擊當前模式不做任何事；切換立即生效並寫入 `config.json`；寫入失敗時回退按鈕狀態並提示。
- 啟動時讀 `view_mode`，非法值當 `card`。

### 4.2 表格視圖

- 版面：表頭固定；列在 `QScrollArea` 內滾動；表頭右側預留與垂直滾動條等寬的間距，避免列與表頭錯位（`rangeChanged` 後以 `QTimer.singleShot(0, …)` 同步）。
- 表頭高 32px：第一列 40px 空白、第二列「名稱」、第三列「操作」（右對齊），底部 1px `palette(mid)` 分隔線。
- 列高 48px，平鋪：底部 1px 分隔線、懸停整行 `palette(midlight)`、無圓角、無陰影、無斑馬紋；整行手型游標。
- 三列：
  1. **圖標欄 40px**：預設 instance 顯示愛心（18px）；系統 instance 顯示禁止圖標（18px，tooltip 同卡片）；其餘空白。
  2. **名稱**：13pt 粗體，左對齊，垂直居中；tooltip 顯示 `name\nbase_path`。
  3. **操作欄固定 420px**：`詳情`、電源切換（26×26）、終端（26×26）、`Linux 檔案`、`安裝目錄`，按鈕高 40、間距 8；圖標、文字、QSS 與卡片完全一致。
- 操作行為：
  - `詳情`：`open_requested.emit(distro)`。
  - 電源：執行中顯示紅色停止圖標、點擊 `stop_requested`；已停止顯示綠色播放圖標、點擊 `start_requested`。
  - 終端／Linux 檔案／安裝目錄：沿用卡片訊號；`安裝目錄` 在 `base_path` 為空時禁用。
- 系統 instance：五個操作按鈕全部禁用，禁止游標，tooltip 統一為 `instance_card.SYSTEM_REASON`。
- 點擊列空白處或名稱 → 進入詳情頁；按鈕為獨立子控件，不觸發列點擊。
- 資料同步：`MainWindow._on_distros()` 同時更新 `card_wall` 與 `instance_table`；兩者 signals 連到同一組槽。

### 4.3 詳情頁「⚙ 設定」

- 位置：`top` 列 `addStretch(1)` 之後最右側；`QPushButton("⚙ 設定")`，高 32、最小寬 88，手型游標。
- 新增訊號 `settings_requested = Signal(str)`；`_emit_name` 風格沿用。
- 系統 instance：禁用 + 禁止游標 + tooltip「系統 instance 由上層工具（如 Docker Desktop）管理，不提供設定」。

### 4.4 Instance 設定對話框

沿用 `DialogBase`（寬 620）。內容：

```
Instance 設定 — <name>
┌ 常用設定 ──────────────────────────────────────────┐
│ 預設使用者   [____________________]  (例：root、ubuntu) │
│              ☑ 啟用 systemd（僅 WSL 2）                 │
│              ☑ 追加 Windows PATH 到 Linux PATH           │
│              ☑ 自動掛載 Windows 磁碟（/mnt/c 等）        │
└──────────────────────────────────────────────────────┘
┌ 進階維護（會終止／轉換此 instance）──────────────────┐
│ WSL 版本     [2 ▾]  [套用版本]                          │
│ Sparse VHD   目前：未啟用／已啟用／未知   [啟用／停用]   │
│ 磁碟壓縮     回收 VHD 未使用空間          [壓縮 VHD]     │
└──────────────────────────────────────────────────────┘
ℹ 變更需終止 instance 後重新啟動才生效。
[取消]                                              [儲存]
```

**狀態互斥矩陣：**

| 控制項 | 執行中 | 已停止 |
|--------|--------|--------|
| 讀取常用設定 | 執行（`cat /etc/wsl.conf` + `whoami`） | 不讀取 |
| 常用設定輸入／`儲存` | 可用 | 全部禁用，顯示「啟動 instance 後才能讀取／修改」 |
| `套用版本` | 禁用 | 可用 |
| `啟用／停用 Sparse` | 禁用 | 可用 |
| `壓縮 VHD` | 禁用 | 可用 |

- WSL 版本為 1 時：systemd 禁用並顯示「WSL 1 不支援 systemd」；Sparse／壓縮一併禁用並提示僅支援 WSL 2。
- 版本切換、Sparse、壓縮各自彈一次 `QMessageBox.warning` 二次確認，文案明講「可能需要數分鐘」「轉換失敗可能導致 instance 無法啟動，建議先備份」。
- 確認後關閉對話框，由 `MainWindow._run_operation()` 執行並顯示 `OperationDialog`；完成後 `refresh()`。
- 壓縮成功後顯示「已回收 X.XX GB」；版本切換成功後提示「已切換為 WSL N，instance 目前為停止狀態」。
- Sparse 目前狀態：`fsutil sparse queryflag <vhdx>`；輸出無法辨識時顯示「未知」，按鈕仍可執行（文字固定為「啟用 Sparse VHD」）。
- 使用者校驗：空白 → 行內錯誤「使用者名稱不可空白」；不存在 → 「instance 內找不到使用者 <name>」；兩者都不關閉對話框。
- 儲存成功：不終止、不重啟；提示「已儲存，下次啟動生效」並記錄日誌。

## 5. 資料層：`app/distro_settings.py`

```python
CONF_PATH = "/etc/wsl.conf"
CONF_TEMP = "/etc/wsl.conf.wsl-deck.tmp"
CONF_BACKUP = "/etc/wsl.conf.wsl-deck.bak"

@dataclass(frozen=True)
class InstanceSettings:
    default_user: str
    systemd: bool
    append_windows_path: bool
    automount: bool

def parse_conf(text: str) -> dict[str, dict[str, str]]        # 純函式，供測試
def set_conf_values(text: str, updates: dict[tuple[str, str], str]) -> str  # 保留註解／未知鍵
def read_settings(name: str) -> InstanceSettings              # 需執行中
def apply_settings(name: str, version: int, values: InstanceSettings) -> None
def user_exists(name: str, user: str) -> bool
def is_sparse(vhdx_path: str) -> bool | None
def set_sparse(name: str, enabled: bool) -> None
def compact_vhd(name: str, vhdx_path: str) -> int            # 回傳回收位元組
def set_version(name: str, version: int) -> None
```

關鍵行為：

- 解析：`[section]` 標題不分大小寫；`key=value` 去除首尾空白；`#`／`;` 註解與空行跳過但原樣保留。
- 合併：逐行改寫，命中同一 section 的既有 key 就取代；沒有就在該 section 最後一個非空行後插入；section 不存在就追加在檔尾。保留原本換行符（`\r\n`／`\n`）與檔尾換行。
- 寫入（需執行中）：先 `cp -n` 備份一次，再以 stdin 寫入 `CONF_TEMP`，`chmod 644`，`mv` 覆蓋；最後 `cat` 讀回並以 `parse_conf` 驗證目標鍵值。
- 讀取預設使用者：`[user] default` 優先；沒有時執行 `wsl -d <name> -- whoami`。
- 布林預設：systemd=false、appendWindowsPath=true、automount=true。
- 使用者校驗：`wsl -d <name> -u root -- id -u <user>`，退出碼 0 即存在（含 root）。
- Sparse：`wsl --manage <name> --set-sparse true|false`，timeout 600 秒。
- 壓縮：`wsl --manage <name> --compact`，timeout 600 秒；前後比較 `vhdx` 大小回傳差值。
- 版本：`wsl --set-version <name> <1|2>`，timeout 600 秒。
- `app/wsl.py` 的 `run_wsl(args, timeout=60, stdin_text=None)` 增參數；`stdin_text` 不為 `None` 時以 `input=` 傳入，其餘行為不變。

## 6. 任務拆解

### Task 1：`icons.py` 抽取（不改行為）

**Files：** Create `app/ui/icons.py`；Modify `app/ui/instance_card.py`

- 把 `_heart_pixmap`、`_prohibition_pixmap`、`_play_pixmap`、`_stop_pixmap` 原樣搬成公開函式 `heart_pixmap()`、`prohibition_pixmap()`、`play_pixmap()`、`stop_pixmap()`。
- `instance_card.py` 改為 import；刪除本地副本。
- 新增 `list_icon(active: bool)`、`grid_icon(active: bool)`：`QIcon` 內含 `Normal/On`（白色）與 `Normal/Off`（`#5f6368`）兩種點陣圖，供切換按鈕使用。
- 驗證：`python -c "from app.ui.instance_card import InstanceCard"`；卡片外觀與既有 56 項測試不變。

### Task 2：`config.py` 新增 `view_mode`

**Files：** Modify `app/config.py`、`tests/test_config.py`

- `DEFAULT_CONFIG` 加 `"view_mode": "card"`。
- `_validate()` 加：

```python
view_mode = self.data.get("view_mode", DEFAULT_CONFIG["view_mode"])
if view_mode not in ("card", "list"):
    raise ConfigError(f"view_mode 必須是 card／list：{view_mode}")
```

- 測試：缺鍵時補 `card`；`"list"` 合法；`"table"`、`1`、`None` 被拒。
- 驗證：`python -m unittest tests.test_config -q`。

### Task 3：`wsl.py` 支援 stdin

**Files：** Modify `app/wsl.py`

- `run_wsl(args, timeout=60, stdin_text=None)`；`subprocess.run(..., input=stdin_text)`。
- 既有呼叫端不變。
- 驗證：`python -m unittest tests.test_wsl_parse -q`。

### Task 4：`distro_settings.py` 與測試

**Files：** Create `app/distro_settings.py`、`tests/test_distro_settings.py`

- 先寫純函式測試：
  - `parse_conf` 解析多 section、忽略註解、大小寫。
  - `set_conf_values` 保留註解與未知鍵、更新既有鍵、插入缺失鍵、建立缺失 section、保留 CRLF。
  - 目標鍵讀回值正確；重複套用結果穩定（冪等）。
  - `is_sparse` 解析 `This file is set as sparse`／`NOT set as sparse`／未知輸出 → `None`。
- 再實作命令函式；命令函式不在單元測試中真的呼叫 `wsl.exe`（以 mock 或僅測純函式）。
- 驗證：`python -m unittest tests.test_distro_settings -q`。

### Task 5：`instance_table.py`

**Files：** Create `app/ui/instance_table.py`

- `InstanceTable(QWidget)` signals 與 `CardWall` 完全同名同參數：`open_requested(object)`、`start_requested(str)`、`stop_requested(str)`、`terminal_requested(str)`、`linux_files_requested(str)`、`install_dir_requested(str)`。
- `InstanceRow(QFrame)` 固定高 48，內含圖標欄、名稱、操作欄；`mousePressEvent` 左鍵發 `open_requested`。
- `set_distros(distros, system_check)`：建立／更新／移除列，順序沿用 `distros`。
- 空清單時僅顯示表頭；不特別做空狀態插畫。
- 驗證：`python -c "from app.ui.instance_table import InstanceTable"`。

### Task 6：`view_toggle.py` 與主頁整合

**Files：** Create `app/ui/view_toggle.py`；Modify `app/ui/main_window.py`

- `ViewToggle` 發出 `mode_changed(str)`；`set_mode(mode)` 同步按鈕狀態。
- `_build_main_page()`：
  - 頂列不變。
  - 新增第二行：`addStretch(1)` + `ViewToggle`。
  - 原本單一 `QScrollArea` 改為 `QStackedWidget`，內含兩個 `QScrollArea`（卡片、表格），各自承載 `CardWall`／`InstanceTable`。
- `_connect_signals()` 同時接表格牆六個訊號。
- `_on_distros()` 同時更新兩個牆。
- `_on_view_mode(mode)`：寫 `config.data["view_mode"]` → `save()`；失敗回退 toggle 並提示；成功切換 `QStackedWidget` 索引並記錄日誌。
- 啟動時套用已保存模式。
- 驗證：`python -m py_compile app\ui\main_window.py app\ui\view_toggle.py`。

### Task 7：詳情頁設定按鈕

**Files：** Modify `app/ui/detail_page.py`、`app/ui/main_window.py`

- `settings_requested = Signal(str)`。
- `top` 列最右側新增 `_settings_btn`；`set_distro()` 依 `is_system` 啟用／禁用並設定 tooltip；納入游標刷新。
- `MainWindow._connect_signals()` 連接 `_open_instance_settings`。
- 驗證：`python -m py_compile app\ui\detail_page.py`。

### Task 8：`instance_settings_dialog.py`

**Files：** Create `app/ui/instance_settings_dialog.py`

- 兩個 `QGroupBox`（常用設定／進階維護）插入 `DialogBase._layout` 的按鈕列之前。
- `maintenance_requested = Signal(str, object)`：`("version", int)`、`("sparse", bool)`、`("compact", None)`。
- 狀態互斥、布林預設、使用者校驗、二次確認全部照 §4.4。
- `values()` 回傳 `InstanceSettings`；`changed()` 與傳入值比較。
- 驗證：`python -c "from app.ui.instance_settings_dialog import InstanceSettingsDialog"`。

### Task 9：`MainWindow` 設定流程

**Files：** Modify `app/ui/main_window.py`

- `_open_instance_settings(name)`：
  - 非系統且執行中：`_run_task(read_settings)` → 成功後開對話框（帶目前值與 `is_sparse()`）；失敗顯示錯誤並記錄日誌。
  - 已停止：直接開對話框（`settings=None`，常用區禁用）。
- 儲存：`_run_operation("套用 Instance 設定", apply_settings)` → 成功提示「已儲存，下次啟動生效」→ `refresh()`。
- 維護：`_on_maintenance(kind, value)` 依類型呼叫 `set_version`／`set_sparse`／`compact_vhd`，全部走 `_run_operation`；壓縮結果顯示回收空間。
- 日誌：每次讀寫與維護都記錄（不含機密內容）。
- 驗證：`python -m py_compile app\ui\main_window.py`。

### Task 10：整合測試與手工驗收

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`，預期 56 + 新增約 10 項全過。
- 依 §8 逐項 GUI 驗收；破壞性操作只在新鮮測試 instance 上做。

## 7. 測試策略

| 檔案 | 覆蓋 |
|------|------|
| `tests/test_config.py`（擴充） | `view_mode` 補鍵、合法值、非法值 |
| `tests/test_distro_settings.py`（新增） | `wsl.conf` 解析、合併、冪等、CRLF、Sparse 輸出解析 |
| `tests/test_wsl_parse.py` | 既有解析不回歸（`run_wsl` 增參數不影響） |

不自動化：Qt 佈局、按鈕狀態、對話框互動、`wsl.exe` 實際寫入、`--compact`／`--set-version`（系統整合且耗時，沿用 M5 的做法以手動驗收）。

## 8. 驗收步驟

> 破壞性項目只在新建的臨時 instance（例如 `m6-test`）操作；不得作用於 `ubuntu`、`node22`、`alms`、`wsl-mysql`、`docker-desktop`。

1. **單元測試**：§7 全部通過。
2. **視圖切換**：主頁第二行右側出現兩顆圖標；點列表 → 表格；點卡片 → 卡片牆；當前模式藍色高亮；關閉 App 重開仍保持上次模式。
3. **持久化與回退**：手動把 `config.json` 的 `view_mode` 改成 `"table"` → 啟動應回退卡片且不崩潰。
4. **表格內容**：三列表頭；愛心只出現在預設 instance；系統 instance 顯示禁止圖標且五個操作全禁用；普通 instance 第一列空白。
5. **表格操作**：點空白處／名稱 → 詳情頁；點「詳情」按鈕 → 詳情頁；點電源 → 啟動或終止（狀態圖標隨之變化）；終端／Linux 檔案／安裝目錄與卡片一致。
6. **視窗縮放**：調整視窗寬度，表格列與表頭不錯位；列數超過可視高度時出現滾動條且表頭固定。
7. **設定入口**：詳情頁名稱列最右側出現「⚙ 設定」；系統 instance 為禁用＋禁止游標。
8. **狀態互斥**：執行中開啟設定 → 常用區可編輯、維護區三個按鈕禁用；停止後開啟 → 常用區禁用並提示、維護區可用。
9. **預設使用者**：在 `m6-test` 設為 root → 儲存 → 提示下次啟動生效 → 終止後執行 `wsl -d m6-test -- whoami` 應為 `root`；改回普通使用者同理；輸入不存在的使用者 → 行內錯誤且不寫入；distro 內 `/etc/wsl.conf.wsl-deck.bak` 存在。
10. **systemd**：WSL 2 的 `m6-test` 勾選 systemd → 儲存 → 終止重啟 → `systemctl --version` 有輸出；取消勾選後重啟應回到非 systemd。WSL 1 時該項禁用。
11. **appendWindowsPath／automount**：改為關閉 → 重啟 → `echo $PATH` 不含 `/mnt/c`；`mount` 不含 DrvFs 自動掛載；改回後恢復。
12. **版本切換**：對 `m6-test` 2→1→2 各一次（若 2→1 因 ext4 失敗則記錄為已知限制，不阻斷驗收）。
13. **Sparse／壓縮**：停止 `m6-test` → 啟用 Sparse → `fsutil sparse queryflag` 顯示 sparse；執行壓縮 → 完成後顯示回收空間，`磁盤大小` 更新；停用 Sparse 後旗標恢復。
14. **清理**：刪除 `m6-test`、其備份與暫存檔；確認 `config.json` 只多了 `view_mode`。

## 9. 風險與回滾

| 風險 | 對策 |
|------|------|
| 寫壞 `/etc/wsl.conf` 導致 distro 無法啟動 | 只改已知 section/key，逐行保留其餘內容；寫入前 `cp -n` 備份；寫入後讀回驗證；必要時 `wsl -d <name> -u root -- cp /etc/wsl.conf.wsl-deck.bak /etc/wsl.conf` |
| 兩處預設使用者來源不一致 | 只寫 `wsl.conf`；不呼叫 `--set-default-user`；對話框注明「下次啟動生效」 |
| 版本切換失敗或逾時 | 需停止才允許；二次確認明示風險；timeout 600 秒；失敗只回報，不改其他設定 |
| 壓縮時間過長 | 走 `OperationDialog`，不可取消；timeout 600 秒；完成後才刷新 |
| Sparse 狀態無法辨識 | 顯示「未知」，仍可執行；不以此阻擋操作 |
| 讀取設定時 distro 被外部終止 | 捕捉 `WslError`，提示重試；不寫半成品 |
| 表格與表頭錯位 | 表頭右側間距隨滾動條可見性同步（`rangeChanged` + `singleShot(0)`） |
| config 寫入失敗導致切換錯亂 | `_on_view_mode` 先保存再切換；失敗回退 toggle 狀態 |
| 無 git，改壞難回復 | 動工前 `_m6-snapshots\<timestamp>` 快照；回滾時覆蓋 `app`、`tests`、`config.json` |

## 10. 確認清單

- [ ] 同意主頁第二行靠右兩顆 32×32 互斥圖標，`view_mode` 寫入 `config.json`（預設 `card`）。
- [ ] 同意表格嚴格三列（圖標／名稱／操作）、行高 48px、平鋪＋分隔線＋懸停高亮、表頭固定。
- [ ] 同意操作欄＝詳情＋電源＋終端＋Linux 檔案＋安裝目錄，圖標與樣式完全照搬卡片。
- [ ] 同意第一列：預設愛心、系統禁止圖標、普通留空。
- [ ] 同意詳情頁名稱列最右側「⚙ 設定」，系統 instance 禁用。
- [ ] 同意設定範圍：預設使用者（自由輸入＋存在性校驗）、systemd、appendWindowsPath、automount、WSL 版本、Sparse、壓縮。
- [ ] 同意狀態互斥：需執行中的項在停止時禁用，需停止的項在執行中禁用；不自動終止。
- [ ] 同意儲存後不重啟，只提示「下次啟動生效」。
- [ ] 同意預設使用者只寫 `/etc/wsl.conf`，不寫註冊表 `DefaultUid`。
- [ ] 同意 §9 的快照回滾方式與 §8 的驗收範圍（破壞性測試只用臨時 instance）。

確認後才開始實作；完成後回報並等待 GUI 驗收。
