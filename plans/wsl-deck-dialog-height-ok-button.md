# 對話框高度放寬＋確定鈕主色

> 狀態：**已完成**

## 1. 目標

1. 對話框內容滾動區高度上限由「螢幕 65%」放寬為「螢幕可用高度 − 120px」（預留標題列＋footer＋視窗邊距），確保 footer 完整可見的前提下盡量用滿螢幕。
2. 對話框確定定鈕（儲存／建立／確定等）改主色背景＋白色文字；取消鈕維持原樣。

## 2. 已核實事實

- [dialog_base.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/dialog_base.py)：scroll 上限目前 `availableGeometry().height() * 0.65`；footer 高約 56px（12+32+12），OS 標題列約 30px；`_ok_btn` 目前無 objectName、無 QSS。
- 主色 `theme.PRIMARY_COLOR = "#2D7FF9"`，hover 深色 `#1F66CC` 已在 view_toggle 使用。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/dialog_base.py` | scroll 上限改 `availableGeometry().height() - 120`；`_ok_btn` `setObjectName("dialogOk")`；`DIALOG_STYLE` 以 f-string 加入 `QPushButton#dialogOk`（主色底、白字、圓角 7、hover `#1F66CC`、pressed 同 hover、disabled 灰底灰字）。 |

## 4. 驗證

1. `py_compile app\ui\dialog_base.py`；`unittest discover`（154 項）。
2. 離屏截圖（light/dark）：對話框變高、footer 完整可見；確定鈕主色白字、取消鈕原樣。

## 5. 風險

| 風險 | 對策 |
|------|------|
| 極矮螢幕（<300px）上限為負 | `max(200, 可用高度 - 120)` 保底 |

回滾：`git checkout -- app/ui/dialog_base.py`。

## 6. 確認清單

- [x] 同意高度上限改「螢幕可用高度 − 120px」。
- [x] 同意確定鈕主色背景＋白字（hover `#1F66CC`），取消鈕不變。

## 7. 實作與驗證結果

- `dialog_base.py`：scroll 上限改 `max(200, 可用高度 - 120)`；`_ok_btn` 設 `objectName("dialogOk")` 並以 f-string QSS 設主色底白字、hover/pressed `#1F66CC`、disabled 灰。
- 驗證：`py_compile` 通過；154 項測試全過；離屏截圖確認儲存鈕藍底白字、取消鈕原樣（離屏虛擬螢幕較矮，實機上限會更高）。
