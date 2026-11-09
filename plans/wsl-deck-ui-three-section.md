# 主視窗改為三段式 UI

> 狀態：**已完成（2026-11-06）**
> 目標：主視窗改為「頂部工具列 / 中間保留現有色 / 底部狀態列」三段式；頂部依首頁／詳情頁切換內容，底部兩頁共用。
> 已確認：深色主題 bar 用 `#1b1d20`（palette base）、詳情頁頂部 bar ＝「← 返回 + instance 名稱 + 系統標籤 + 設定」。

## 1. 已核實事實

- 主視窗只由 [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py) 組裝：
  - `central` 的 VBox 目前只有 `_stack` + 日誌抽屜（L123-L129）。
  - 狀態文字掛在 `statusBar()`（L131-L132）；設定是浮在右下角的 `settingsFab`，用 `_position_settings_btn()` 手動 `move()`，`resizeEvent` 每次重算（L133-L162、L333-L338、L1481-L1483）。
  - 首頁 `_build_main_page()` 有一列「WSL Deck + 新增 Instance + 全部關機」（L189-L211），第二列是右對齊的 `ViewToggle`（L213-L219）。
  - 日誌抽屜＝「日誌」arrow toggle + 150px `QPlainTextEdit`（L268-L297）。
- [detail_page.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/detail_page.py#L49-L85) 自帶一列：`← 返回`、`_title`、`_system_badge`、右側「設定」；`set_distro()` 會更新 `_title`／`_system_badge`／`_settings_btn` 狀態（L195-L233）。
- 主題切換只換 palette（[theme.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/theme.py)）：light 標準 palette `Base=#FFFFFF`、`WindowText` 黑；dark `Base=#1b1d20`、`window=#202225`、`WindowText=#e6e6e6`。
- 現有測試（`wsl-deck/tests`）沒有任何一項引用 `MainWindow`、`statusBar`、`_settings_btn` 或 `ViewToggle`。
- 目前 config `theme=light`、`view_mode=list`。

## 2. 新結構

```
MainWindow
└─ central (VBox, margins 0, spacing 0)
   ├─ TopBar       背景 palette(base)：light #FFFFFF / dark #1b1d20，高 56，底線 1px rgba(128,128,128,70)
   │   ├─ 首頁列：  [WSL Deck] [+ 新增 Instance] [全部關機] ───stretch─── [卡片/列表切換]
   │   └─ 詳情列：  [← 返回] [instance 名稱] [系統標籤] ───stretch─── [⚙ 設定]
   ├─ Middle       QStackedWidget（首頁卡片牆／列表、詳情頁）＝沿用目前顏色與邊距
   ├─ LogPanel     QPlainTextEdit，預設隱藏，高 150
   └─ BottomBar    背景 palette(base)，高 48，頂線 1px rgba(128,128,128,70)
       [▸ 日誌] ───────── [狀態文字置中] ───────── [⚙]
```

- 首頁／詳情頁用同一條 BottomBar，不隨頁面切換。
- TopBar 用內部 `QStackedWidget` 放兩列，切換頁面時 index 0／1。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | 新增 `_build_top_bar()`（含 `_home_bar`／`_detail_bar` 兩列與 `_top_stack`）、`_build_bottom_bar()`、`_build_log_panel()`；central 依序放 top bar / stack / log panel / bottom bar。移除 `statusBar()`、浮動 FAB、`_position_settings_btn()`、`resizeEvent()`、`SETTINGS_BUTTON_SIZE`、`SETTINGS_ICON_SIZE`、`SETTINGS_BUTTON_MARGIN`。首頁移除標題列與 toggle 列，只留 `_wall_stack`。新增 `_set_detail_bar()`，在 `_show_detail`／`_on_distros` 更新詳情列。 |
| `app/ui/detail_page.py` | 移除 `_build()` 最上方一列（返回鈕、`_title`、`_system_badge`、`_settings_btn`）與 `back_requested`／`settings_requested` 訊號；`set_distro()` 移除對應更新。 |
| `app/ui/view_toggle.py` | **不改**（現有 QSS 用 palette，放在 palette(base) 的 bar 上深／淺主題都清楚）。 |
| `app/ui/icons.py` | **不改**（日誌開關沿用 `Qt.ArrowType`，箭頭顏色由 palette 自動跟隨）。 |

- 不改卡片、表格、網路面板、對話框、托盤、任何業務邏輯。
- 詳情頁內容其餘版面（summary／動作列／網路面板）保持不動，只少掉最上面那列。

## 4. 細節規格

### 4.1 Top bar
- 容器 `QWidget#topBar`：`setFixedHeight(56)`，VBox `contentsMargins(0,0,0,0)`，內含 `QStackedWidget`。
- QSS：`QWidget#topBar { background: palette(base); border: none; border-bottom: 1px solid rgba(128,128,128,70); }`；兩列 row widget 背景透明、`contentsMargins(16, 8, 16, 8)`、`spacing 8`。
- 首頁列：
  1. 標題 `WSL Deck`：18pt 粗體，`palette(windowtext)`。
  2. `+ 新增 Instance`：主要按鈕 `QPushButton#primaryAction`：底 `#2D7FF9`、白字、圓角 6、高 32、左右 padding 14；hover `#1F66CC`；disabled 底 `#A9C7F5`。
  3. `全部關機`：次要按鈕 `QPushButton#secondaryAction`：透明底、`1px solid palette(mid)`、`palette(windowtext)`、圓角 6、高 32；hover `palette(midlight)`；disabled 字 `#9aa0a6`。
  4. `addStretch(1)`。
  5. `ViewToggle`（既有元件，靠右）。
- 詳情列：
  1. `← 返回`：`secondaryAction`，高 32、最小寬 88。
  2. `_detail_name`：16pt 粗體，`palette(windowtext)`。
  3. `_detail_badge`：沿用詳情頁原樣式（`color #7f8c8d; border 1px #bdc3c7; radius 4; padding 2px 6px`），系統 instance 才顯示。
  4. `addStretch(1)`。
  5. `設定`：`settings_icon()` + 16px 圖標，高 32、最小寬 96；系統 instance 停用，tooltip 沿用原文案。
- 返回鈕連到 `_show_main`；設定鈕連到 `_open_instance_settings(self._current.name)`。

### 4.2 Bottom bar
- `QWidget#bottomBar`，`setFixedHeight(48)`，`contentsMargins(16, 6, 16, 6)`。
- QSS：`background: palette(base); border: none; border-top: 1px solid rgba(128,128,128,70);`。
- `QGridLayout` 三欄：第 0 欄最小寬 120（日誌開關靠左）、第 1 欄 stretch 1（狀態文字置中）、第 2 欄最小寬 120（設定鈕靠右）。
- 左：`_log_toggle`＝`QToolButton#logToggle`，checkable、`ToolButtonTextBesideIcon`、文字「日誌」、`Qt.RightArrow`；扁平、`color: palette(windowtext)`、hover 底 `palette(midlight)`、圓角 6、高 30。
- 中：`_status_label`，字色 `#7f8c8d`，`Qt.AlignCenter`；文字沿用「共 N 個 instance，執行中 N 個｜更新於 HH:MM:SS」。
- 右：`_settings_btn`＝`QToolButton#bottomSettings` 32×32、`settings_icon()` 20px、tooltip「設定」；扁平、hover 底 `palette(midlight)`、圓角 6；無陰影、無手動定位。

### 4.3 日誌面板
- `_log_view` 放在 stack 與 bottom bar 之間的外層容器（`contentsMargins(16, 8, 16, 0)`，背景透明），`setFixedHeight(150)` 不變，Consolas 不變。
- QSS：`QPlainTextEdit#logView { background: palette(base); border: none; }`。
- 預設隱藏；`_on_log_toggled` 只做 `setVisible` + `setArrowType(Down/Right)`；`ERROR` 自動展開行為保留。

### 4.4 深／淺主題
- bar 背景一律 `palette(base)`：light 為純白 `#FFFFFF`、dark 為 `#1b1d20`（比中間 `#202225` 略深）；文字用 `palette(windowtext)`，分隔線用中性半透明灰，深淺主題都不需額外分支。
- 藍色主按鈕 `#2D7FF9`、藍色齒輪圖標、狀態文字 `#7f8c8d` 兩主題共用。

## 5. 驗證

1. `python -m py_compile app\ui\main_window.py app\ui\detail_page.py`
2. `python -m unittest discover -s tests -q`（wsl-deck 目錄，預期全過）。
3. 離屏渲染（`QT_QPA_PLATFORM=offscreen`）分別以 light／dark palette 建 `MainWindow`，抓首頁與詳情頁圖，確認：
   - 首頁頂部單列：標題／新增／全部關機／兩顆切換；
   - 詳情頁頂部：返回／名稱／系統標籤／設定，且內容不再重複標題列；
   - 兩頁底部都只有「日誌／狀態文字／齒輪」，狀態文字置中；
   - bar 顏色 light=#FFFFFF、dark=#1b1d20，中間內容顏色與改版前一致；
   - 展開日誌時面板出現在底部 bar 上方。
4. 實機啟動一次，確認新增／全部關機／視圖切換／日誌／設定／返回都能點。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| QSS `border` 作用在 topBar 容器時被子元件覆蓋 | 只設 `border-bottom`，子列一律透明背景、不加邊框 |
| 詳情頁移除頂列後，返回／設定入口消失 | 入口移到 TopBar 詳情列，並在 `_show_detail`、`_on_distros` 兩個路徑都更新名稱與停用狀態 |
| 深色主題下主按鈕與 bar 對比不足 | `#2D7FF9` 配白字在 `#1b1d20` 上對比 ≥ 3:1；次要按鈕用 `palette(mid)` 邊框維持可見 |
| 日誌面板夾在 stack 與 bottom bar 之間，展開時挤压內容 | 固定 150px，屬預期行為；中間 `_stack` 本來就會縮 |

回滾：只改動 2 個檔案，`git checkout -- app/ui/main_window.py app/ui/detail_page.py` 即可還原。

## 7. 確認清單

- [x] 同意 TopBar 分「首頁列／詳情列」，BottomBar 兩頁共用。
- [x] 同意詳情頁原本的返回／名稱／系統標籤／設定整列搬到 TopBar，詳情頁內不再重複。
- [x] 同意 bar 背景用 `palette(base)`（light 純白、dark `#1b1d20`）。
- [x] 同意「新增 Instance」為藍色主要按鈕、「全部關機」為次要按鈕。
- [x] 同意設定鈕由右下角浮動 FAB 移到 BottomBar 右側。
- [x] 同意不改其他功能與版面。

已依此計畫完成，驗證結果見第 5 節。
