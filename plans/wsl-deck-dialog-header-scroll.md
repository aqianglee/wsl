# 對話框去 Header＋內容高度限制

> 狀態：**已完成**

## 1. 目標

1. 移除所有對話框的 modal header（白底標題列）；視窗標題（`setWindowTitle`）保留。
2. content 不再隨內容無限撐高：包進 `QScrollArea`，最大高度約螢幕可用高度的 65%，超出改滾動，footer 永遠可見。

## 2. 已核實事實

- [dialog_base.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/dialog_base.py)：根 layout 目前為 header（QFrame#dialogHeader）→ content（QWidget，含 `_form`/`_error`）→ footer（QFrame#dialogFooter）；`root.addWidget(content, 1)` 讓內容自由伸展，內容過高時整個對話框被撐高、footer 可能被推出可視區。
- 8 個子類共用 DialogBase；header 移除後無其他程式碼引用 header 元件。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/dialog_base.py` | 移除 header QFrame 與標題 QLabel、`QFrame#dialogHeader` QSS；content 改放 `QScrollArea`（`setWidgetResizable(True)`、無邊框、背景透明），捲軸需要時才出現；scroll area `setMaximumHeight(round(螢幕可用高度 * 0.65))`，內容矮時維持自然高度（不強制撐大）。 |

- 其他檔案不動；子類對話框（設定／Instance 設定／備份等）自動生效。

## 4. 細節規格

- Header 移除後，頂部只剩原生視窗標題列（OS 提供），內容從 20px margin 開始。
- `QScrollArea`：
  - `setFrameShape(QFrame.NoFrame)`、viewport 背景透明（露出 `palette(window)` 底色）；
  - 水平捲軸一律關閉（`Qt.ScrollBarAlwaysOff`），寬度由對話框決定；
  - 垂直捲軸 `ScrollBarAsNeeded`。
- 高度上限：`QGuiApplication.primaryScreen().availableGeometry().height() * 0.65`（例如 1080p 螢幕約 670px），使用者縮小視窗時 footer 始終在可視範圍內；`QDialog` 本身維持可調整大小。

## 5. 驗證

1. `py_compile app\ui\dialog_base.py`；`unittest discover`（154 項）。
2. 離屏截圖（light/dark）：
   - 兩個設定對話框頂部無白 header 標題列；
   - 將 Instance 設定對話框內容撐到超過上限時出現垂直捲軸、footer 可見；
   - 內容矮時（如備份對話框）高度自然、無多餘捲軸區。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| 滾動區內卡片陰影/圓角被裁 | 卡片無陰影（dialog 內），圓角在內距內不會被裁 |
| `setWidgetResizable` 影響內容寬度 | 內容寬度跟隨 scroll viewport，扣除捲軸寬約 12px，可接受 |

回滾：`git checkout -- app/ui/dialog_base.py`。

## 7. 確認清單

- [x] 同意移除 modal header（保留 OS 視窗標題）。
- [x] 同意 content 包 QScrollArea、最大高度約螢幕 65%，超出滾動、footer 永遠可見。

## 8. 實作與驗證結果

- `dialog_base.py`：移除 `QFrame#dialogHeader` 與標題 QLabel 及對應 QSS；content 改放無框透明 `QScrollArea`（水平捲軸關閉、垂直 AsNeeded、content 與 viewport 透明），最大高度＝螢幕可用高度 × 0.65。
- 驗證：`py_compile` 通過；154 項測試全過；離屏截圖確認無 header、內容出現垂直捲軸、footer 白底按鈕可見（8 個子類自動生效）。
