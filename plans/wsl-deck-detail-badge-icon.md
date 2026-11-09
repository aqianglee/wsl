# 詳情頁 TopBar：系統標籤改圖標（或隱藏）

> 狀態：**已完成**（選定方案 A）

## 1. 目標

詳情頁 TopBar 名稱旁的文字標籤「系統 instance」調整。兩種做法，擇一：

- **方案 A（更換圖標，推薦）**：移除文字標籤，改用與首頁相同的三態圖標——系統＝紅禁止、預設＝紅實心愛心、普通＝灰空心愛心（18px），tooltip 分別為系統原因／預設 instance／普通 instance。
- 方案 B（純隱藏）：系統 instance 時不顯示任何標記，其餘也不加圖標。

## 2. 已核實事實

- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py)：
  - `_build_detail_bar()` L330-332：`_detail_badge` 是 `QLabel("系統 instance")`，objectName `detailBadge`，預設隱藏。
  - `_set_detail_bar()` L353-356：只在系統 instance 時 `setVisible(True)`，非系統一律隱藏。
  - QSS L104 有 `QLabel#detailBadge` 樣式（改圖標後可刪）。
- 首頁三態圖標已就位：`forbidden_icon()`／`heart_icon()`／`heart_outline_icon()`（icons.py），表格與卡片都在用。

## 3. 變更範圍（方案 A）

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | `_detail_badge` 由文字 QLabel 改為圖標 QLabel（18×18）；`_set_detail_bar()` 依三態設 pixmap 與 tooltip，永遠可見（非系統也要顯示愛心，和首頁一致）；刪除 `QLabel#detailBadge` 的 QSS。 |

若選方案 B：僅移除 `_detail_badge` 的建立與 `setVisible` 邏輯，刪 QSS。

## 4. 細節規格（方案 A）

```python
self._detail_badge = QLabel(row)
self._detail_badge.setFixedSize(18, 18)
```

`_set_detail_bar()`：

| 狀態 | 圖標 | tooltip |
|------|------|---------|
| 系統 | `forbidden_icon()` | `SYSTEM_REASON`（沿用現有常數） |
| 預設 | `heart_icon()` | 預設 instance |
| 普通 | `heart_outline_icon()` | 普通 instance |

- 圖標與名稱之間維持 8px 間距（layout spacing 不變）。
- 系統 instance 的「設定」鈕禁用邏輯不變。

## 5. 驗證

1. `py_compile app\ui\main_window.py`。
2. `unittest discover`（154 項）。
3. 離屏 light/dark 截圖：詳情頁分別以預設／普通／系統 instance 開啟，確認名稱旁圖標正確且與首頁一致。

## 6. 確認清單

- [x] 選方案 A（三態圖標，推薦，與首頁一致）。

## 7. 實作與驗證結果

- `main_window.py`：`_detail_badge` 改為 18×18 圖標 QLabel，永遠可見；`_set_detail_bar()` 依三態設 `forbidden_icon()`／`heart_icon()`／`heart_outline_icon()` 與對應 tooltip；刪除 `QLabel#detailBadge` QSS。
- 驗證：`py_compile` 通過；154 項測試全過；離屏 light/dark 截圖確認預設（紅實心愛心）、普通（灰空心愛心）、系統（紅禁止）三態圖標與 tooltip 正確。
