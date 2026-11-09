# 詳情頁重組：操作按鈕入卡、分組、圖標化

> 狀態：**已完成**（與日誌面板方案一起執行；內距依使用者要求統一 16px）

## 1. 目標

1. 詳情頁上方白色區域：加入標題（三態圖標 + instance 名稱），並把 10 顆操作鈕＋「設定」移入該區域底部，icon 在左、文字在右，分 5 組；「設定＋刪除」組靠右對齊，其餘靠左。
2. 網路規則改為同款白色卡片，標題「網路規則」；兩張卡片 padding、標題字級、圓角統一。
3. 套用 6 個新 SVG 圖標：主頁「新增 Instance」用 `ic_add.svg`；詳情頁備份／還原／快照／複製／刪除各用對應圖標。

## 2. 已核實事實

- [detail_page.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/detail_page.py)：summary `QFrame#summary`（palette(base)、1px mid 邊、radius 8、內距 14/12），其下是獨立 actions 列（10 顆 32px 高 QPushButton），再下是 `NetworkPanel`。
- [network_panel.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/network_panel.py)：`QGroupBox("網路規則")`，內含 QTableWidget＋5 顆按鈕＋說明文字；無卡片背景。
- 新圖標皆 `stroke="currentColor"` 線性風格，需走既有 `_svg_tinted_icon()` 上色（icons.py 已具備）。
- 主頁「+ 新增 Instance」在 main_window.py home bar，`primaryAction` 白字主色底。
- 詳情頁目前無「設定」鈕（設定在 TopBar）；InstanceSettingsDialog 由 main_window 處理。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/icons.py` | 新增 `add_icon()`（白色，給主色底按鈕）、`backup_icon()`、`restore_icon()`、`snapshot_icon()`、`copy_icon()`（皆 `_muted_color()`）、`delete_icon()`（`#e74c3c`）；皆走 `_svg_tinted_icon()`。 |
| `app/ui/detail_page.py` | summary 卡片重構：標題列（三態圖標 + 名稱）＋原資訊格＋分隔線＋分組操作列；卡片樣式統一（radius 10、1px rgba(128,128,128,30) 邊、內距 16）；新增「設定」鈕與 `settings_requested` 訊號。 |
| `app/ui/network_panel.py` | `QGroupBox` 改 `QFrame` 卡片（同款背景/邊/圓角/內距），頂部加標題列「網路規則」（字級與詳情卡標題一致）；內容不變。 |
| `app/ui/main_window.py` | 「新增 Instance」加 `add_icon()`（14px）；連接 `detail_page.settings_requested` 到現有 InstanceSettingsDialog 處理；TopBar 設定鈕保留。 |

## 4. 細節規格

### 4.1 卡片統一規格（summary／network 共用）
- `background: palette(base); border: 1px solid rgba(128,128,128,30); border-radius: 10px;`
- 內距統一 `16px` 四邊；標題 12pt 粗體 `palette(windowtext)`，標題與內容間距 10。
- 不疊陰影（詳情頁卡片平鋪即可，與表格白卡風格一致但不浮起）。

### 4.2 summary 卡結構（自上而下）
1. 標題列：三態圖標 18px（`forbidden_icon`/`heart_icon`/`heart_outline_icon`）＋名稱 12pt 粗體；右側留空。
2. 資訊格：現有 5 欄位不動（狀態／WSL 版本／磁盤大小／目前 IP／安裝路徑）。
3. 1px 淡分隔線 `rgba(128,128,128,45)`。
4. 操作列（32px 高按鈕，icon 16px 在左，間距 6；組間用 `QFrame#opsDivider` 1×22 豎線 + 兩側 8px）：
   - G1 啟動/終止、終端 → G2 Linux 檔案、安裝目錄 → G3 設為預設 → G4 備份、還原、快照、複製 → stretch → G5 設定、刪除（右對齊）。
5. 圖標對應：啟動 `power_start_icon`／終止 `power_stop_icon`、終端 `terminal_icon`、Linux 檔案 `linux_archive_icon`、安裝目錄 `install_dir_icon`、設為預設 `heart_outline_icon`、備份 `backup_icon`、還原 `restore_icon`、快照 `snapshot_icon`、複製 `copy_icon`、設定 `settings_themed_icon`、刪除 `delete_icon`。
6. 啟用邏輯不變；`set_distro()` 依 running 切換啟動/終止的文字與圖標；標題圖標依三態更新。

### 4.3 NetworkPanel
- 類別改為 `QFrame`（對外 API 不變），標題列「網路規則」12pt 粗體；原表格／按鈕／說明全部保留。
- 與 summary 卡同背景、邊框、圓角、內距。

### 4.4 主頁新增鈕
- `add_icon()`：`_svg_tinted_icon("ic_add.svg", "#FFFFFF")`，icon 14px，置於「新增 Instance」文字左側；按鈕其餘樣式不變。

## 5. 驗證

1. `py_compile` 四個檔案；`unittest discover`（154 項）。
2. 離屏 light/dark 截圖（預設／普通／系統 instance）：
   - summary 卡：標題圖標三態正確、操作列 5 組組＋豎線、設定/刪除靠右；
   - 執行中 vs 停止時啟動/終止圖標與文字切換；
   - 網路規則卡：白底圓角、標題字級與 summary 一致；
   - 主頁新增鈕出現白色 + 圖標。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| NetworkPanel 由 QGroupBox 改 QFrame 影響既有樣式 | 對外訊號與方法不變，僅外殼與標題實作改變 |
| 11 顆鈕＋分隔線在小視窗換行困難 | 操作列允許超出時由視窗寬度自然收合（按鈕固定高、不設最小總寬）；必要時使用者再決定是否兩行 |
| 系統 instance 多數按鈕禁用 | 沿用既有禁用邏輯，灰色 icon 由 disabled 樣式處理（`_muted_color` 圖標在 disabled 下仍可辨識） |

回滾：`git checkout -- app/ui/icons.py app/ui/detail_page.py app/ui/network_panel.py app/ui/main_window.py`。

## 7. 確認清單

- [x] 同意卡片規格：radius 10、1px 淡邊、內距統一 16px、無陰影。
- [x] 同意分組與對齊：G1~G4 靠左、設定+刪除靠右，組間 1×22 淡豎線。
- [x] 同意詳情頁內新增「設定」鈕（開啟同一個 InstanceSettingsDialog，TopBar 設定鈕保留）。
- [x] 同意刪除圖標用紅色 `#e74c3c`，其餘操作圖標用主題中性色；新增鈕用白色 +。
- [x] 同意網路規則改同款白卡，標題「網路規則」。

## 8. 實作與驗證結果

- `icons.py`：新增 `add_icon()`（白）／`backup_icon()`／`restore_icon()`／`snapshot_icon()`／`copy_icon()`（主題中性色）／`delete_icon()`（`#e74c3c`）。
- `detail_page.py`：summary 改 `QFrame#sectionCard`（radius 10、rgba(128,128,128,30) 邊、內距 16）；標題列三態圖標＋名稱 12pt 粗體；資訊格後 1px 分隔線；11 顆 32px 操作鈕（icon 16px 在左）分 5 組，組間 1×22 豎線，設定+刪除靠右；新增 `settings_requested`；啟動/終止文字與圖標隨狀態切換。
- `network_panel.py`：`QGroupBox` 改 `QFrame#sectionCard`，標題「網路規則」12pt 粗體，內距 16，內容不變。
- `main_window.py`：「新增 Instance」改白字 `add_icon()`（14px）＋文字；連接 `settings_requested` → `_open_instance_settings`。
- 驗證：`py_compile` 通過；154 項測試全過；離屏 light/dark 截圖確認標題三態、分組與靠右、啟動/終止圖標切換、網路卡標題、新增鈕白色 +。
