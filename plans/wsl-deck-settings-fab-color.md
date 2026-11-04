# 設定按鈕圖示改為科技藍（純色）計畫

> 狀態：已確認（方案 A，`#2D7FF9`）
> 關聯：[wsl-deck-m5-settings-fab.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m5-settings-fab.md)

**Goal：** 把右下角懸浮設定按鈕的齒輪圖示改成純色科技藍，深淺色主題下都清楚且一致。

**Architecture：** 只改 [main_window.py](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/main_window.py) 中 `settingsFab` 的 QSS；不動版面、定位、尺寸。

---

## 1. 現況

- 齒輪目前用 `color: palette(button-text)`，淺色主題接近深灰、深色主題接近亮灰，沒有辨識色。
- hover 只把邊框改 `#4a90e2`、底色改 `palette(midlight)`。

## 2. 方案（預設 A）

### A. 圖示純色藍、按鈕底色不變（預設）

| 狀態 | 底色 | 圖示色 | 邊框 |
|------|------|--------|------|
| 一般 | `palette(button)` | `#2D7FF9`（科技藍） | `palette(mid)` |
| hover | `palette(midlight)` | `#4DA3FF`（提亮） | `#2D7FF9` |
| pressed | `palette(mid)` | `#1F66CC`（壓暗） | `#2D7FF9` |

### B. 按鈕整體純藍、齒輪白色（想要更搶眼時）

| 狀態 | 底色 | 圖示色 |
|------|------|--------|
| 一般 | `#2D7FF9` | `#FFFFFF` |
| hover | `#4DA3FF` | `#FFFFFF` |
| pressed | `#1F66CC` | `#FFFFFF` |

- 純色，不用漸層；仍以 QSS 寫死，不依賴 palette，深淺主題視覺一致。
- 顏色值集中在 QSS 內，若要調整隻改三個 hex。

## 3. 受影響檔案

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | `settingsFab` QSS 的 `color`／`background`／`border-color` |

## 4. 驗證

- `python -m unittest discover -s tests -q`（預期 56 OK）
- 離屏確認按鈕仍為 40×40、右／下間距 32
- 目視：淺色與深色主題下齒輪皆為清晰藍色；hover／按下有層次

## 5. 風險與回滾

- 風險：藍色在深色主題的深灰按鈕上對比稍低；hover 提亮可補足，必要時改方案 B。
- 回滾：把 `color` 改回 `palette(button-text)`、hover 邊框改回 `#4a90e2`。

## 6. 待你拍板

1. 採 **A（藍色齒輪）** 還是 **B（整顆藍色按鈕＋白齒輪）**？
2. 藍色用 `#2D7FF9` 可以嗎？或指定 `#0078D4`（Windows 藍）／`#0A84FF`（iOS 藍）／`#00A3FF`（偏青科技藍）？
