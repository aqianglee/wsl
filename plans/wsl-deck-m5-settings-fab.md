# 設定按鈕改為右下角懸浮大按鈕（FAB）實作計畫

> 狀態：待確認（確認後才動工）
> 上層文件：[wsl-deck-m5.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m5.md)
> 目標：把右下角齒輪從狀態列小按鈕改成懸浮固定的大按鈕，視覺更醒目，且與視窗右側、下側邊距相等。

**Goal：** 讓「設定」入口成為主視窗右下角固定懸浮的圓形大按鈕，圖示約為目前 4 倍，並在視窗縮放、切換頁面時保持定位。

**Architecture：** 不再把按鈕放進 `QStatusBar`，改為 `MainWindow` 的直接子元件，以 `resizeEvent` 重新計算位置並 `raise_()` 保持最上層；尺寸與邊距集中為模組常數，樣式仍以 `palette(...)` 寫在 QSS，深淺色主題皆適用。

**Tech Stack：** Python 3.14、PySide6 6.12、`QToolButton`、QSS palette。

---

## 1. 現況

- [main_window.py](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/main_window.py#L105-L114) 目前：
  - `_settings_btn` 是 `QToolButton`，文字 `⚙`，`setAutoRaise(True)`，放進 `statusBar().addPermanentWidget(...)`。
  - 按鈕尺寸由狀態列高度決定（約 20–22 px），圖示約 14–16 px，位置貼齊狀態列右緣，與視窗右側／下側距離不相等（下側多了狀態列高度）。

## 2. 設計

### 2.1 尺寸與邊距（模組常數，置於 `main_window.py` 頂端，與既有 `logger` 放在一起）

```python
SETTINGS_BUTTON_SIZE = 40      # 按鈕直徑
SETTINGS_ICON_POINT_SIZE = 16  # 齒輪字級
SETTINGS_BUTTON_MARGIN = 32    # 與視窗右側、下側相同的邊距
```

- 按鈕固定 40×40，圓角 20（正圓）。
- 圖示以 `QFont` 指定 `setPointSize(16)`；維持文字 `⚙`，不新增圖檔。
- 需要再放大時只改常數即可。

### 2.2 定位（懸浮固定）

- 建立時改為 `QToolButton(self)`，**不再**加入狀態列。
- 新增私有方法：

```python
def _position_settings_btn(self) -> None:
    size = SETTINGS_BUTTON_SIZE
    margin = SETTINGS_BUTTON_MARGIN
    self._settings_btn.move(
        max(0, self.width() - size - margin),
        max(0, self.height() - size - margin),
    )
    self._settings_btn.raise_()
```

- 覆寫 `resizeEvent`：先 `super().resizeEvent(event)`，再呼叫 `_position_settings_btn()`。
- `__init__` 末端（`QTimer.singleShot(0, self.refresh)` 前）先呼叫一次 `_position_settings_btn()`，確保首次顯示就定位。
- 按鈕 `setFixedSize(64, 64)`、`setToolTip("設定")`，保留 `refresh_cursor()`。

### 2.3 樣式（QSS，深淺色皆用 palette）

```python
self._settings_btn.setObjectName("settingsFab")
self._settings_btn.setStyleSheet(
    """
    QToolButton#settingsFab {
        background: palette(button);
        border: 1px solid palette(mid);
        border-radius: 32px;
        color: palette(button-text);
    }
    QToolButton#settingsFab:hover {
        background: palette(midlight);
        border-color: #4a90e2;
    }
    QToolButton#settingsFab:pressed {
        background: palette(mid);
    }
    """
)
```

- 亦比照卡片加上輕微陰影（`QGraphicsDropShadowEffect`，blur 12、offset 0/3、alpha 60），強化「懸浮」感；若你不需要可去掉。

### 2.4 版面關係

- 按鈕為懸浮覆蓋層，會蓋在日誌抽屜右下角與狀態列上方（"悬浮固定" 即此效果），不改動既有版面尺寸。
- 若你希望完全不遮住日誌文字，可改為在日誌抽屜下方保留 64+16 px 空白；預設**不保留**，維持現有版面。

## 3. 受影響檔案

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | 新增 3 個常數；改寫 `_settings_btn` 建立與樣式；新增 `_position_settings_btn()`、`resizeEvent()`；`__init__` 末端呼叫定位 |

不改其他檔案；不動狀態列文字。

## 4. 實作步驟

- [ ] **Step 1：常數** 在 `logger = logging.getLogger(__name__)` 後加入三個常數。
- [ ] **Step 2：改建立方式** 將 `_settings_btn` 段改為：`QToolButton(self)`、`setObjectName("settingsFab")`、`setFixedSize(...)`、字級、QSS、陰影、`setToolTip`、`clicked.connect(self._open_settings)`、`refresh_cursor`；**移除** `statusBar().addPermanentWidget(...)`。
- [ ] **Step 3：定位方法** 新增 `_position_settings_btn()`；在 `__init__` 的 `self._watch_color_scheme()` 前呼叫一次。
- [ ] **Step 4：resizeEvent** 在既有 `changeEvent` 之後新增 `resizeEvent`，呼叫 `super()` 與 `_position_settings_btn()`。
- [ ] **Step 5：驗證**
  - `python -m py_compile app/ui/main_window.py`
  - `python -m unittest discover -s tests -q`（預期仍 56 項 OK）
  - 離屏檢查幾何（不開 GUI）：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -c "from pathlib import Path; from PySide6.QtWidgets import QApplication; from app.config import Config; from app.ui.main_window import MainWindow, SETTINGS_BUTTON_SIZE, SETTINGS_BUTTON_MARGIN; app=QApplication([]); w=MainWindow(Config(Path('config.json'))); w.resize(1000,680); b=w._settings_btn; print(b.size().width(), b.x(), b.y()); print('RIGHT_GAP', w.width()-b.x()-b.width()); print('BOTTOM_GAP', w.height()-b.y()-b.height())"
```

  預期：`64 ...`、`RIGHT_GAP 16`、`BOTTOM_GAP 16`。

## 5. 驗收步驟（手動）

1. 啟動 App（或打包 exe），右下角出現直徑約 64 px 的圓形齒輪按鈕。
2. 目測與視窗右緣、下緣間距相等；縮放視窗後仍貼齊右下角、不被內容蓋住。
3. 懸停與按下有背景變化；點擊可開啟設定對話框。
4. 深色／淺色主題下按鈕底色、邊框、圖示皆清楚。
5. 日誌抽屜展開時按鈕浮在最上層，不影響捲動與點擊其他控制項。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| 按鈕遮住日誌抽屜右下角文字 | 需要時改用「保留底部空白」方案（§2.4），只調整 log drawer 容器下緣 margin |
| 高 DPI 縮放下圓角看起來不圓 | 直徑與圓角固定 px，Qt 會等比縮放；必要時以 `SETTINGS_BUTTON_SIZE / 2` 動態計算 |
| 未預期的 resize 時序造成初始偏移 | `__init__` 末端與 `resizeEvent` 都呼叫同一支定位方法，且 `show()` 前後皆已覆蓋 |
| 回滾 | 改回 `statusBar().addPermanentWidget(self._settings_btn)`、移除常數與兩個方法；或由 `_m5-snapshots\20261102-165631` 還原 |

## 7. 已定案參數（2026-11-02 使用者指示）

1. 按鈕直徑 **40 px**、圖示字級 **16pt**、邊距 **32 px**。
2. 接受懸浮按鈕**覆蓋在日誌抽屜右下角上方**。
3. 保留輕微陰影（blur 6）。
