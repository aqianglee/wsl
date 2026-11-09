# 詳情 TopBar 精簡＋卡片標題順序調整

> 狀態：**已完成**（另依使用者回饋加大操作鈕 icon 與文字間距）

## 1. 目標

1. 詳情頁 TopBar 只保留「返回」鈕；移除名稱、三態圖標、設定鈕（詳情卡內已有標題與設定鈕，資訊重複）。
2. 詳情頁第一張卡片標題改為「名稱在前、圖標在後」。

## 2. 已核實事實

- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py)：`_build_detail_bar()` 依序放 返回鈕→`_detail_name`→`_detail_badge`→stretch→`_detail_settings_btn`；`_set_detail_bar()` 依三態設定圖標與啟用。
- [detail_page.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/detail_page.py)：卡片標題列為 `_badge`（18px）在前、`_name` 在後。
- 詳情卡內已有「設定」鈕（`settings_requested` → `_open_instance_settings`），功能與 TopBar 設定鈕完全相同。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | `_build_detail_bar()` 移除 `_detail_name`／`_detail_badge`／`_detail_settings_btn` 及 stretch；`_set_detail_bar()` 清空（或只留 no-op 並由 `_show_detail` 不再依賴其狀態）；同步移除主題切換時對 detail 設定鈕的重著色；未使用的 import（`forbidden_icon`、`heart_icon`、`heart_outline_icon`、`SYSTEM_REASON`、`QSize` 若僅此用途）一併清理。 |
| `app/ui/detail_page.py` | 標題列改為 `_name` 在前、`_badge` 在後（間距 8 不變）。 |

- 移除後 detail bar 只剩返回鈕，高度 56 不變，左側 24px 對齊不變。

## 4. 驗證

1. `py_compile app\ui\main_window.py app\ui\detail_page.py`；`unittest discover`（154 項）。
2. 離屏截圖（light/dark）：詳情 TopBar 只有返回鈕；卡片標題為「名稱 + 圖標」順序；詳情卡內設定鈕仍可開啟對話框。

## 5. 風險

| 風險 | 對策 |
|------|------|
| `_set_detail_bar` 被多處呼叫 | 改為 no-op 或同步更新呼叫點，確保無殘留引用 |
| TopBar 只剩返回鈕顯得空 | 屬使用者明確要求；右側留白即可 |

回滾：`git checkout -- app/ui/main_window.py app/ui/detail_page.py`。

## 6. 確認清單

- [x] 同意移除詳情 TopBar 的名稱、圖標、設定鈕（功能由卡內設定鈕承擔）。
- [x] 同意卡片標題改為名稱在前、圖標在後。

## 7. 實作與驗證結果

- `main_window.py`：詳情列只剩返回鈕；移除 `_detail_name`／`_detail_badge`／`_detail_settings_btn`／`_on_detail_settings`／`_set_detail_bar` 及主題重著色引用；清理 `forbidden_icon`／`heart_icon`／`heart_outline_icon`／`SYSTEM_REASON` import 與 `QLabel#detailName` QSS。
- `detail_page.py`：標題列改名稱在前、圖標在後；新增 `_spaced_icon()`（圖標右側補 4px 透明像素），11 顆操作鈕（含啟動/終止動態切換）統一加大 icon 與文字間距。
- 驗證：`py_compile` 通過；154 項測試全過；離屏 light/dark 截圖確認 TopBar 只剩返回鈕、標題順序與按鈕間距正確。
