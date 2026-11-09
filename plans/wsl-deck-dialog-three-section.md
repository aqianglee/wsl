# 對話框三段式與分組卡片化

> 狀態：**已完成**

## 1. 目標

1. 詳情頁操作列：移除 G4（備份／還原／快照／複製）與 G5（設定／刪除）之間的淡豎線（截圖紅框標記處）。
2. 「設定」（SettingsDialog）與「Instance 設定」（InstanceSettingsDialog）改三段式設計：
   - 上方 modal header：白底（`palette(base)`）、標題、底部 1px 分隔線；
   - 中間 content：維持目前 `palette(window)` 底色，**分組改卡片設計**（與詳情頁白卡一致）；
   - 下方 modal footer：白底、頂部 1px 分隔線、取消／儲存靠右。

## 2. 已核實事實

- [detail_page.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/detail_page.py)：4 個左側組別迴圈每組後都 `addWidget(_ops_divider(...))`，最後一條豎線在 stretch 之前 → 即截圖紅框位置。
- [dialog_base.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/dialog_base.py)：`DialogBase` 目前是單一 `QVBoxLayout`（form + error + 按鈕列），`self._layout`、`self._form`、`add_info()`（插到按鈕列前）、`_ok_btn/_cancel_btn` 為公開 API。
- 8 個子類共用 DialogBase：`SettingsDialog`、`InstanceSettingsDialog`、`BackupDialog`、`RestoreDialog`、`CloneDialog`、`DeleteDialog`、`SnapshotCreateDialog`、`RestorePathDialog`——基底改三段式後全部自動生效。
- 分組目前：`SettingsDialog` 無分組（一串表單列）；`InstanceSettingsDialog` 用 3 個 `QGroupBox`（常用設定／網路隔離（C 方案）／進階維護），以 `self._layout.insertWidget(i, group)` 插入。
- 卡片樣式已有共識：`QFrame#sectionCard`（`palette(base)`、1px `rgba(128,128,128,30)`、radius 10）＋ 12pt 粗體標題 ＋ 內距 16。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/detail_page.py` | 分組豎線只加在 G1｜G2｜G3 之後；G4 與 G5 之間不加（由 stretch 分隔）。 |
| `app/ui/dialog_base.py` | 重構為三段式：根 layout margins 0、spacing 0 → `QFrame#dialogHeader`（白底、標題 QLabel 14pt 粗體、底線 `rgba(128,128,128,45)`、內距 (20,14)）→ 內容容器（`self._layout`，margins (20,16,20,16)、spacing 12，含 `self._form` 與 `self._error`）→ `QFrame#dialogFooter`（白底、頂線、按鈕列 (20,12) 靠右）。新增共用卡片 helper：`CARD_STYLE`、`card_title_font()`、`make_card(parent, title) -> tuple[QFrame, QVBoxLayout]`。`add_info()` 改為插入到 `self._error` 之前；公開 API（`_ok_btn`／`_cancel_btn`／`set_ok_text`／`show_error`／`add_info`／`_form`／`_layout`）不變。 |
| `app/ui/settings_dialog.py` | 內容改 3 張卡片：**目錄**（工作目錄、骨架、instance／備份／快照目錄、保留策略＋info）、**一般**（輪詢間隔、主題、托盤、開機自啟＋info、進階模式、系統 instance 清單＋info）、**SOCKS5 代理**（啟用、主機、埠、測試＋info）。資訊文字放入對應卡片底部。 |
| `app/ui/instance_settings_dialog.py` | 3 個 `QGroupBox` 改 `make_card()`（標題沿用：常用設定／網路隔離（C 方案）／進階維護）；頂部灰字 info 維持在內容區頂端；運行提示 info 維持內容區底部。 |
| 其餘 6 個子類 | 不改程式碼，僅驗證三段式外觀正常（它們內容是單一表單，不加分組卡片）。 |

## 4. 細節規格

- Header：`QFrame#dialogHeader { background: palette(base); border-bottom: 1px solid rgba(128,128,128,45); }`；標題 `QFont 14pt bold`、`palette(windowtext)`；內距 `(20, 14, 20, 14)`。
- Footer：`QFrame#dialogFooter { background: palette(base); border-top: 1px solid rgba(128,128,128,45); }`；內距 `(20, 12, 20, 12)`；按鈕列 spacing 8、右對齊（沿用 96×32）。
- Content：`palette(window)` 底（預設）；margins `(20, 16, 20, 16)`、卡片間距 12。
- 卡片：`make_card()` 建立 `QFrame#sectionCard`＋標題 QLabel（12pt 粗體）＋內容 `QVBoxLayout`（內距 16、spacing 10）；卡片內的表單用 `QFormLayout` 加進內容 layout。`InstanceSettingsDialog` 原 `QFormLayout(group)` 直接移到卡片內。
- 深色主題：header/footer 跟 `palette(base)`（#1b1d20）、卡片同色、分隔線 rgba 自動變淡，不硬編碼白色。
- 視窗標題（`setWindowTitle`）保留，供工作列／Alt-Tab 使用；header 顯示同一標題文字。

## 5. 驗證

1. `py_compile` 四個檔案；`unittest discover`（154 項全過）。
2. 離屏截圖（light/dark）：
   - 詳情頁：G4 與 G5 之間無豎線，其餘 3 條保留；
   - 兩個設定對話框：header 白底＋標題、3 張圓角卡片、footer 白底按鈕靠右；
   - 抽驗一個舊對話框（如 BackupDialog）三段式外觀無異常。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| `add_info` 插入位置改變影響子類訊息順序 | 統一插到 `_error` 之前，維持「先加的在上面」語義；截圖抽驗 |
| SettingsDialog 分組後表單行對齊改變 | 每張卡片內各自 `QFormLayout`，標籤欄寬由 Qt 自動處理 |
| `_layout.insertWidget(i, ...)` 索引語義 | InstanceSettingsDialog 改用 append（順序固定：info→常用→網路→維護→提示） |

回滾：`git checkout -- app/ui/detail_page.py app/ui/dialog_base.py app/ui/settings_dialog.py app/ui/instance_settings_dialog.py`。

## 7. 確認清單

- [x] 同意移除詳情頁 G4｜G5 之間的豎線。
- [x] 同意兩個設定對話框改三段式（白 header／卡片 content／白 footer），且 8 個 DialogBase 子類一併換三段式外觀。
- [x] 同意 SettingsDialog 分 3 張卡片（目錄／一般／SOCKS5 代理），InstanceSettingsDialog 3 個 GroupBox 改卡片。
- [x] 同意深色主題 header/footer 用 `palette(base)` 深色而非純白。

## 8. 實作與驗證結果

- `detail_page.py`：分組豎線只保留 G1｜G2｜G3 之後 3 條，G4 與 G5 之間改由 stretch 分隔。
- `dialog_base.py`：重構三段式——`QFrame#dialogHeader`（`palette(base)`、標題 14pt 粗體、底線）→ 內容容器（margins (20,16)、spacing 12）→ `QFrame#dialogFooter`（`palette(base)`、頂線、按鈕靠右）；新增 `CARD_STYLE`／`card_title_font()`／`make_card()`；`add_info()` 改插到 `_error` 之前；公開 API 不變。
- `settings_dialog.py`：內容改 3 張卡片（目錄／一般／SOCKS5 代理），資訊文字放入對應卡片底部，新增 `_info_label()` helper。
- `instance_settings_dialog.py`：3 個 `QGroupBox` 改 `make_card()`（標題沿用），其餘邏輯不變。
- 驗證：`py_compile` 通過；154 項測試全過；離屏 light/dark 截圖確認兩個對話框 header/卡片/footer 結構、詳情頁 G4｜G5 間無豎線。
