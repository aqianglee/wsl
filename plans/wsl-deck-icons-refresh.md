# 圖標替換：設定／返回／普通 instance 愛心輪廓

> 狀態：**已完成**

## 1. 目標

1. 設定圖標改用 `assets/ic_settings.svg`（線性齒輪），取代目前 QPainter 繪製的實心齒輪。
2. 返回按鈕改用 `assets/ic_back.svg`（雪佛龍箭頭），取代目前文字裡的「←」。
3. 普通 instance（非系統、非預設）在表格列與卡片上都顯示 `assets/ic_heart_outline.svg`（空心愛心），不再留白。

## 2. 已核實事實

- 三個 SVG 已存在於 [assets](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/assets)：`ic_settings.svg`、`ic_back.svg`、`ic_heart_outline.svg`。
- 這三個 SVG 都用 `stroke="currentColor"`；Qt 的 SVG 渲染器不會解析 `currentColor`（會當成黑色），因此**不能直接 `QIcon.addFile`**，必須自行渲染後著色，否則深色主題下會看不見。
- [icons.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/icons.py) 目前：
  - `_svg_icon()`（L31）以 `QIcon.addFile` 載入固定顏色的 SVG。
  - `settings_pixmap()`（L220）用 QPainter 畫實心齒輪；`settings_icon()`（L258）只回傳它，顏色固定 `PRIMARY_COLOR`。
  - `heart_icon()`（L63）載入 `ic_heart_default.svg`（紅色實心愛心）。
  - `forbidden_icon()`（L97）載入 `ic_forbidden.svg`。
- [instance_table.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_table.py) 的 `InstanceRow.update_distro()`：系統 → `prohibition_pixmap()`、預設 → `heart_pixmap()`、其他 → **空 QPixmap**（40px 圖標欄留白）。
- [instance_card.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_card.py) 的 `update_distro()`（L245）：`_star` 只在 `is_default` 時可見、`_system_icon` 只在系統實例可見，普通實例兩個都隱藏 → 左上 18px 留白。
- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py) 的 `_build_detail_bar()`（L306）：返回鈕是 `QPushButton("← 返回")`，沒有 icon。
- 目前風格：其他圖標（電源、終端、硬碟等）都是固定顏色 SVG，不隨主題變色；僅圖標本身顏色已足夠在深淺主題下辨識。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/icons.py` | 新增 `_svg_tinted_pixmap()` / `_svg_tinted_icon()`（QSvgRenderer 渲染 + `CompositionMode_SourceIn` 上色）；`settings_icon()` 改為優先使用 `ic_settings.svg`（主色）並保留原 QPainter 回退；新增 `back_icon()`、`heart_outline_icon()`、`_muted_color()`。 |
| `app/ui/main_window.py` | 返回鈕改為 `QPushButton("返回")` + `back_icon()`（16px）；`_apply_settings()` 內重新設定返回鈕 icon，讓切換主題後箭頭顏色跟上。 |
| `app/ui/instance_table.py` | `update_distro()` 的三種狀態改用 `forbidden_icon()` / `heart_icon()` / `heart_outline_icon()` 的 18px pixmap；普通實例 tooltip 改「普通 instance」。 |
| `app/ui/instance_card.py` | `_star` 改為「非系統就顯示」：預設用實心愛心、普通用空心愛心，tooltip 分別為「預設 instance」「普通 instance」；系統仍顯示禁止圖標。 |

不改任何業務邏輯、按鈕尺寸與版面配置。

## 4. 細節規格

### 4.1 SVG 上色工具（icons.py）

```python
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

def _svg_tinted_pixmap(filename: str, size: int, color: str) -> QPixmap | None:
    path = _ASSETS_DIR / filename
    if not path.is_file():
        return None
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return None
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return pixmap
```

- `_svg_tinted_icon(filename, color, sizes=(16, 24, 32, 48, 64))`：逐尺寸產生 pixmap 後 `QIcon.addPixmap`。
- `_muted_color()`：依 `QApplication` palette 的 `Window` 亮度決定——深色主題 `#c9ced6`、淺色主題 `#5f6368`（沿用既有 `INACTIVE_ICON_COLOR` 風格）。

### 4.2 設定圖標

- `settings_icon()`：優先 `_svg_tinted_icon("ic_settings.svg", PRIMARY_COLOR)`；檔案缺失時回退現有 `settings_pixmap()` 迴圈，行為不變。
- 顏色維持主色 `#2D7FF9`，三個使用處（底部設定鈕 20px、詳情頁設定鈕 16px、對話框視窗圖標）都不用改。

### 4.3 返回圖標

- `back_icon()`：`_svg_tinted_icon("ic_back.svg", _muted_color())`；缺失時回傳空 `QIcon`（按鈕仍有「返回」文字，不會裸奔）。
- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py#L312-L318)：`QPushButton("返回")`、`setIcon(back_icon())`、`setIconSize(QSize(16, 16))`，高度 32、最小寬 88 不變。
- 在 `_apply_settings()`（已呼叫 `apply_theme` 之後）補一行 `self._back_btn.setIcon(back_icon())`，使主題切換後重新取色。

### 4.4 普通 instance 圖標

表格 `InstanceRow.update_distro()`：

| 狀態 | 圖標 | tooltip |
|------|------|---------|
| 系統 | `forbidden_icon()`（紅禁止） | `SYSTEM_REASON` |
| 預設 | `heart_icon()`（紅實心愛心） | 預設 instance |
| 普通 | `heart_outline_icon()`（空心愛心，灰） | 普通 instance |

- 尺寸統一 18×18（與現在一致）。

`heart_outline_icon()`：`_svg_tinted_icon("ic_heart_outline.svg", _muted_color())`；缺失時回傳空 icon（不誤用實心愛心）。

卡片 `InstanceCard.update_distro()`：

```python
self._system_icon.setVisible(is_system)
self._star.setVisible(not is_system)
if not is_system:
    icon = heart_icon() if distro.is_default else heart_outline_icon()
    self._star.setPixmap(icon.pixmap(QSize(18, 18)))
    self._star.setToolTip("預設 instance" if distro.is_default else "普通 instance")
```

- 系統實例維持「只顯示禁止圖標」，避免同時出現愛心與禁止。

## 5. 驗證

1. `python -m py_compile app\ui\icons.py app\ui\main_window.py app\ui\instance_table.py app\ui\instance_card.py`
2. `python -m unittest discover -s tests -q`（預期 154 項全過）
3. 離屏渲染 light / dark：
   - 底部與詳情頁設定鈕顯示線性齒輪（主色），不再是實心齒輪；
   - 詳情頁返回鈕左側是箭頭圖標 + 「返回」文字；
   - 表格：系統紅禁止、預設紅實心愛心、普通灰色空心愛心；
   - 卡片：左上角對應顯示實心／空心愛心；深色主題下空心愛心仍可見。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| `currentColor` SVG 渲染成黑色 | 一律經 `QSvgRenderer` + SourceIn 上色，不直接 `addFile` |
| QSvg 模組缺失 | 已確認 `.venv` 內 `PySide6.QtSvg` 可 import；缺失時回退舊 QPainter 齒輪與空 icon |
| 空心愛心被誤認為「預設」 | 預設仍是紅色實心，普通是灰色空心，並用 tooltip 區分 |
| 18px 下齒輪細節糊掉 | 設定鈕用 20px、對話框用 32px 以上，多尺寸 icon 由 Qt 自動挑選 |

回滾：`git checkout -- app/ui/icons.py app/ui/main_window.py app/ui/instance_table.py app/ui/instance_card.py`

## 7. 確認清單

- [x] 設定圖標改用 `ic_settings.svg`（維持主色）。
- [x] 返回鈕改為「箭頭圖標 + 返回」文字（保留文字，不是純圖標）。
- [x] 普通 instance 在表格與卡片都顯示灰色空心愛心，tooltip「普通 instance」。
- [x] 預設 instance 仍為紅色實心愛心、系統實例仍為紅色禁止圖標。
- [x] 主題切換後返回箭頭會重新取色。

## 8. 實作與驗證結果

- `icons.py`：新增 `_muted_color()`（依 palette Window 亮度決定 `#5f6368`/`#c9ced6`）、`_svg_tinted_pixmap()`/`_svg_tinted_icon()`（QSvgRenderer + SourceIn 上色）；新增 `back_icon()`、`heart_outline_icon()`；`settings_icon()` 優先 SVG、缺失回退 QPainter。
- `main_window.py`：返回鈕改 `QPushButton("返回")` + `back_icon()`（16px）；`_apply_settings()` 與 `_on_color_scheme_changed()` 重新設定 icon。
- `instance_table.py`：三態改用 `forbidden_icon()`／`heart_icon()`／`heart_outline_icon()`（18px）；普通 tooltip「普通 instance」。
- `instance_card.py`：`_star` 非系統即顯示，預設實心／普通空心，tooltip 分開。
- 驗證：`py_compile` 通過；`unittest discover` 154 項全過；離屏 light/dark 截圖確認表格三態圖標、卡片愛心、線性齒輪、返回箭頭均正常。
