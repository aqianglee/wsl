# 修復對話框高度：QScrollArea sizeHint 不回報內容高度

> 狀態：**已完成**

## 1. 目標

對話框高度跟隨內容：內容矮時自然高度，內容高時撐到「螢幕可用高度 − 120px」上限後滾動，footer 永遠完整可見。

## 2. 根因（已診斷）

- 離屏診斷：SettingsDialog 內容 `sizeHint` 高 **960px**，但 `QScrollArea.sizeHint` 只有 **288px**（Qt 預設值，不回報內容高度），對話框總高被壓成 345px ⇒ 出現捲軸、使用者要拖很長才能看完三張卡片。
- 之前設的 `setMaximumHeight` 只是上限，`sizeHint` 太小才是「沒什麼效果」的原因。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/dialog_base.py` | 新增內部類 `_ContentScrollArea(QScrollArea)`，覆寫 `sizeHint()`：`height = min(內容 sizeHint 高, maximumHeight)`，寬度沿用父類；`_build_base()` 改用此類。其餘不動。 |

## 4. 細節規格

```python
class _ContentScrollArea(QScrollArea):
    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        widget = self.widget()
        if widget is not None:
            hint.setHeight(min(widget.sizeHint().height(), self.maximumHeight()))
        return hint
```

- 對話框最終高度 ≈ `min(內容高度, 螢幕 − 120) + footer(57)`。
- 8 個子類對話框全部生效；寬度不變。

## 5. 驗證

1. `py_compile app\ui\dialog_base.py`；`unittest discover`（154 項）。
2. 離屏診斷重跑：scroll `sizeHint` 應 = `min(960, 680) = 680`，dialog 高 ≈ 737。
3. 離屏截圖：矮內容（備份對話框）維持自然高度。

## 6. 風險

| 風險 | 對策 |
|------|------|
| 內容為動態增長（如規則列表） | sizeHint 每次查詢即時計算，不受影響 |

回滾：`git checkout -- app/ui/dialog_base.py`。

## 7. 確認清單

- [x] 同意以自訂 `_ContentScrollArea.sizeHint()` 讓對話框高度跟隨內容（上限 螢幕−120）。

## 8. 實作與驗證結果

- `dialog_base.py`：新增 `_ContentScrollArea(QScrollArea)` 覆寫 `sizeHint()`（高＝`min(內容, maximumHeight)`），`_build_base()` 改用此類。
- 診斷重跑：scroll `sizeHint` 288 → **680**（= 上限），dialog `sizeHint` 345 → **737**；離屏截圖確認對話框明顯變高（目錄卡完整、一般卡露出）、footer 與主色儲存鈕完整可見。
- `py_compile` 通過；154 項測試全過。
