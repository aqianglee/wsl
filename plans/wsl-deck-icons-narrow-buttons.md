# 詳情頁 TopBar 按鈕收窄＋設定圖標改黑色

> 狀態：**已完成**

## 1. 目標

1. 詳情頁 TopBar 的「返回」「設定」兩顆按鈕目前過寬（返回 min-width 88、設定 min-width 96），收窄一點。
2. 兩處設定圖標（詳情頁「設定」鈕 16px、底部列右下齒輪鈕 20px）由主色 `#2D7FF9` 改為黑色系。

## 2. 已核實事實

- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py)：返回鈕 `setMinimumWidth(88)`（L317）；詳情頁設定鈕 `setMinimumWidth(96)`、icon 16px（L337-L340）；底部 `_settings_btn` 32×32、icon 20px（L395-L399）。三處都用 `settings_icon()`。
- [icons.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/icons.py)：`settings_icon()` 優先 `_svg_tinted_icon("ic_settings.svg", SETTINGS_ICON_COLOR)`，`SETTINGS_ICON_COLOR = PRIMARY_COLOR`；對話框視窗圖標（`settings_dialog.py`、`instance_settings_dialog.py`）也共用 `settings_icon()`。
- 深色主題純黑齒輪會看不清，因此「黑色」應跟隨主題：淺色用近黑、深色用近白（與 `_muted_color()` 同思路）。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | 返回鈕 `setMinimumWidth(88)` → 72；詳情頁設定鈕 `setMinimumWidth(96)` → 72。 |
| `app/ui/icons.py` | 新增 `settings_themed_icon()`（`ic_settings.svg` 用 `_muted_color()` 上色，隨主題黑/白）；`main_window.py` 兩顆設定鈕改用之。`settings_icon()` 維持主色不變，供對話框視窗圖標使用。 |
| `app/ui/main_window.py` | `_apply_settings()`／`_on_color_scheme_changed()` 內，與 `back_icon()` 一起重設兩顆設定鈕的 icon。 |

## 4. 細節規格

- 返回鈕：文字「返回」+ 16px 箭頭，min-width 72，高度 32 不變。
- 詳情頁設定鈕：文字「設定」+ 16px 齒輪，min-width 72，高度 32 不變。
- 底部設定鈕：32×32、icon 20px 不變，只換色。
- `settings_themed_icon()`：`_svg_tinted_icon("ic_settings.svg", _muted_color())`，缺失回退空 `QIcon`；淺色 `#5f6368`、深色 `#c9ced6`。
  - 若你想要「純黑/純白」（`#111` / `#f0f0f0`）而非灰調，確認時告知，只差一個色值。

## 5. 驗證

1. `py_compile` 四個檔案。
2. `unittest discover`（154 項）。
3. 離屏 light/dark 截圖：詳情列兩鈕明顯變窄；設定齒輪淺色主題為深色、深色主題為淺色，不再是主色藍。

## 6. 確認清單

- [x] 返回／設定鈕 min-width 88/96 → 72（若想更窄可再調，確認時告知數值）。
- [x] 兩處設定圖標改跟隨主題的近黑/近白（淺色 `#5f6368`、深色 `#c9ced6`），對話框視窗圖標維持主色不變。

## 7. 實作與驗證結果

- `icons.py`：新增 `settings_themed_icon()`（`ic_settings.svg` + `_muted_color()`）。
- `main_window.py`：返回鈕 88→72、詳情設定鈕 96→72；詳情設定鈕與底部齒輪鈕改用 `settings_themed_icon()`；`_apply_settings()`／`_on_color_scheme_changed()` 一併重設三個主題圖標。
- 驗證：`py_compile` 通過；154 項測試全過；離屏截圖確認兩鈕實測寬度 72，齒輪在淺色主題為深灰、深色主題為淺灰。
