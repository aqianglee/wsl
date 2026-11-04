# M6.1 小計畫：設定圖標統一為視窗圖標藍 `#2D7FF9`

> 狀態：**待確認**
> 上層文件：[wsl-deck-m6-view-and-instance-settings.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m6-view-and-instance-settings.md)
> 目標：把「設定」相關圖標統一成程式圖標的藍色 `#2D7FF9`，不改動其他配色。

## 1. 已核實事實

- 視窗圖標由 [app_icon.py](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/app_icon.py#L9-L29) 以 QPainter 繪製：圓角方塊填 `#2d7ff9`，中央白色粗體「W」。
- 顏色值：`#2D7FF9`，RGB(45, 127, 249)。
- 右下角全域設定 FAB 的齒輪文字已經是 `#2D7FF9`（`main_window.py` 的 `settingsFab` QSS）。
- 詳情頁「⚙ 設定」按鈕目前用系統預設文字色。
- 設定對話框沒有單獨設定 `windowIcon`，沿用 Qt 預設行為。

## 2. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/icons.py` | 新增 `settings_pixmap(size, color=SETTINGS_ICON_COLOR)` 與 `settings_icon()`；常數 `SETTINGS_ICON_COLOR = "#2D7FF9"` |
| `app/ui/detail_page.py` | 「⚙ 設定」按鈕改為「設定」文字 + `settings_icon()` 圖標，圖標 16px，保持 32px 高、最小寬 88 |
| `app/ui/instance_settings_dialog.py` | `setWindowIcon(settings_icon())` |
| `app/ui/settings_dialog.py` | 同步 `setWindowIcon(settings_icon())`，保持兩個設定對話框一致 |

- 齒輪圖標以 QPainter 向量繪製（圓環 + 6 個圓角齒），不引入圖檔、不依賴字體是否支援 `⚙`。
- 按鈕文字改為中性色（跟隨後續 palette），只有圖標是藍色；hover 時沿用按鈕既有背景變化，不另外改色。
- 不改主視窗圖標本體、不改 `settingsFab`、不改表格／卡片任何圖標。

## 3. 驗證

1. `.\.venv\Scripts\python.exe -m py_compile app\ui\icons.py app\ui\detail_page.py app\ui\instance_settings_dialog.py app\ui\settings_dialog.py`
2. 離屏渲染詳情頁與兩個設定對話框，確認齒輪為藍色、標題列圖標為藍色、按鈕尺寸不變。
3. `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`，預期 71 項全過（本次無邏輯變更）。

## 4. 風險與回滾

| 風險 | 對策 |
|------|------|
| 16px 下齒輪線條糊成一團 | 以筆寬 `size*0.10`、圓環半徑 `size*0.24` 繪製，並在 16/24/32 三個尺寸下離屏檢查 |
| 按鈕文字與圖標間距不足 | 沿用現有 `setIconSize(16,16)` 與按鈕 padding，必要時把最小寬從 88 調到 96 |
| 標題列不顯示圖標（部分 Windows 主題） | 僅影響呈現，不改功能；必要時同時設定 `setWindowIconText` |

回滾：只需還原上述四個檔案（修改前快照已存在於 `_m6-snapshots\20261103-104503`）。

## 5. 確認清單

- [ ] 同意新增 `settings_icon()`（QPainter 齒輪，`#2D7FF9`）。
- [ ] 同意詳情頁按鈕改為「設定」+ 藍色齒輪圖標。
- [ ] 同意 **Instance 設定** 與 **全域設定** 兩個對話框都套用同一標題圖標。
- [ ] 同意不改其他圖標與配色。

確認後才動工。

## 6. 補充（2026-11-03）：右下角全域設定 FAB

**現象：** 實機截圖中右下角 40×40 FAB 仍是灰色立體齒輪，沒有變成 `#2D7FF9`。

**原因：** [main_window.py](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/main_window.py#L124-L146) 目前用 `setText("⚙")`（U+2699）。Windows 會以 Segoe UI Emoji 渲染這個字元，呈現彩色／灰色立體圖形，QSS 的 `color: #2D7FF9` 對 emoji 字形無效；先前只改了詳情頁按鈕，FAB 仍走舊路徑。

**變更：**

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | FAB 不再 `setText("⚙")`，改為 `setIcon(settings_fab_icon())`、`setIconSize(QSize(28, 28))`；28px 畫布、齒輪本體約 20px；移除 `SETTINGS_ICON_POINT_SIZE` 與對應 QFont 設定 |
| `app/ui/icons.py` | 新增 `settings_fab_icon()`：28/56px 畫布、`scale=0.85`，只供 FAB 使用；`settings_icon()` 維持原樣 |
| `app/ui/main_window.py`（QSS） | 移除 `color: #2D7FF9` 等文字色宣告，只保留背景、邊框、圓角與 hover 邊框 |

- 圖標仍為 QPainter 向量齒輪，與詳情頁按鈕、兩個設定對話框完全同源。
- FAB 尺寸維持 40×40、圓角 20、右下角位置不變。

**驗證：**

1. `python -m py_compile app\ui\main_window.py`
2. 離屏渲染主視窗，確認 FAB 內為藍色齒輪、大小與圓形底相符。
3. `python -m unittest discover -s tests -q`，預期 71 項全過。

**回滾：** 還原 `main_window.py` 即可（快照在 `_m6-snapshots\20261103-104503`）。

