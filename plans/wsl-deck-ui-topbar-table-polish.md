# UI 微調：TopBar 按鈕右置、主色統一、表格列與操作分區

> 狀態：**已完成（2026-11-06）**
> 目標：
> 1. TopBar 的 4 個按鈕（新增 Instance／全部關機／卡片／列表）全部靠右，標題留在最左。
> 2. 以 App 圖標色 `#2D7FF9` 作為全城主色，新增 Instance 按鈕用主色作背景（沿用現有藍底，改為引用統一常數）。
> 3. 表格每一行取消「整行點擊進詳情」，只保留「詳情」按鈕入口。
> 4. 操作欄 5 個按鈕分成 3 區，區間加淡色豎線：`詳情`｜`啟動/停止 + 終端`｜`Linux 檔案 + 安裝目錄`；豎線高 30px（按鈕 26px、整行 48px），兩側各 8px padding。

## 1. 已核實事實

- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py#L254-L288) 的首頁 bar 目前順序：`WSL Deck` → `+ 新增 Instance` → `全部關機` → `addStretch(1)` → `ViewToggle`；前三個靠左、toggle 靠右。
- 主色 `#2D7FF9` 目前硬編碼在三處：[main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py#L109-L128) 的 `primaryAction` QSS、[view_toggle.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/view_toggle.py#L29-L32) 的 `:checked`、[icons.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/icons.py#L24) 的 `SETTINGS_ICON_COLOR`；App 圖標本身也是 `#2d7ff9`。
- [instance_table.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_table.py#L294-L297) 的 `InstanceRow.mousePressEvent` 會在任何左鍵點擊時 `open_requested.emit`，等於整行可點；列建構時也設了 `Qt.PointingHandCursor`（L128），並在 QSS 有 `QFrame#instanceRow:hover` 背景高亮（L54-L56）。
- 操作欄 5 個按鈕在 `InstanceRow._build()`（L174-L220）：詳情 64px、電源 26px、終端 26px、Linux 檔案 100px、安裝目錄 100px，`ops` spacing 8；欄寬常數 `BUTTONS_WIDTH = 348`、`OPS_COLUMN_WIDTH = BUTTONS_WIDTH + COLUMN_PADDING * 2`（L39-L47）。
- 尺寸常數：`ROW_HEIGHT = 48`、`ICON_BUTTON_SIZE = 26`、`ICON_SIZE = 22`（[instance_card.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_card.py#L37-L39)）。
- 既有 154 項單元測試不涉及 UI，改動不影響邏輯測試。

## 2. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/theme.py` | 新增 `PRIMARY_COLOR = "#2D7FF9"`（App 圖標色）。 |
| `app/ui/main_window.py` | `TOP_BAR_STYLE` 改為 f-string 引用 `PRIMARY_COLOR`；首頁 bar 改為 `標題 → addStretch(1) → 新增 → 全部關機 → ViewToggle`，4 個按鈕全部靠右。 |
| `app/ui/view_toggle.py` | `VIEW_STYLE` 改為 f-string，`:checked` 底色／邊框用 `PRIMARY_COLOR`（值不變）。 |
| `app/ui/instance_table.py` | 移除 `InstanceRow.mousePressEvent` 整行點擊、`PointingHandCursor`、`instanceRow:hover` 背景；操作欄插入 2 條淡色豎線分成 3 區，更新 `BUTTONS_WIDTH`／`OPS_COLUMN_WIDTH`。 |
| `app/ui/icons.py` | `SETTINGS_ICON_COLOR` 改引用 `theme.PRIMARY_COLOR`（值不變）。 |

- 不改任何業務邏輯、卡片牆與詳情頁內容。

## 3. 細節規格

### 3.1 TopBar
- 首頁列：`WSL Deck`（左）→ `addStretch(1)` → `+ 新增 Instance`（主色底）→ `全部關機`（次要）→ `ViewToggle`（兩顆）。按鈕間距 8，toggle 與前面按鈕間另加 8px（沿用 layout spacing）。
- 「新增 Instance」維持 `#2D7FF9` 底＋白字，只是色值改引用 `PRIMARY_COLOR`。

### 3.2 主色
- `theme.PRIMARY_COLOR = "#2D7FF9"`；`main_window`、`view_toggle`、`icons` 三處改引用，視覺不變，之後換色只改一處。

### 3.3 表格整行
- 刪除 `mousePressEvent` override（整行不再進詳情）。
- 刪除列的 `setCursor(Qt.PointingHandCursor)`，恢復一般箭頭游標。
- 刪除 `QFrame#instanceRow:hover { background: palette(midlight); }`，避免看起來可點。
- 保留「詳情」按鈕（`open_requested`）與列 tooltip；保留列與列之間的 `border-bottom` 分隔。

### 3.4 操作欄分區
- 在 `ops` 加入 2 個 `QFrame#opsDivider`：
  - 詳情 → **線** → 電源、終端 → **線** → Linux 檔案、安裝目錄。
  - 尺寸 `1 × 30`，垂直置中（`Qt.AlignVCenter`），不沾滿 48px 行高。
  - 顏色 `rgba(128, 128, 128, 40)`（比現有欄位分隔線 `rgba(128,128,128,56)` 更淡）。
- 線兩側 padding：沿用 `ops` spacing 8 → 每條線左右各 8px 間距。
- 寬度重算：5 個按鈕 64+26+26+100+100 = 316，7 個元素共 6 個 8px 間距 = 48，豎線 2px → `BUTTONS_WIDTH = 366`，`OPS_COLUMN_WIDTH = 366 + 24 = 390`。
- `update_distro` 對 `self._buttons` 的啟用／tooltip 邏輯不變。

## 4. 驗證

1. `python -m py_compile app\ui\main_window.py app\ui\view_toggle.py app\ui\instance_table.py app\ui\icons.py app\ui\theme.py`
2. `python -m unittest discover -s tests -q`（預期 154 項全過）。
3. 離屏渲染 light／dark 主視窗（含表格視圖），確認：
   - 首頁 TopBar 只有標題在左，4 顆按鈕全在右且不擁擠；
   - 點擊列空白處不再觸發詳情（改以程式檢查：不再有 `mousePressEvent` 覆寫，且列游標為一般箭頭）；
   - 操作欄出現 2 條 30px 淡豎線，3 區塊間距一致，欄寬足夠不擠壓按鈕；
   - 深色主題下豎線仍然淡、不刺眼。

## 5. 風險與回滾

| 風險 | 對策 |
|------|------|
| 操作欄變寬導致名稱欄被壓縮 | `BUTTONS_WIDTH` 同步 +18px；表格本身有 `OPS_COLUMN_WIDTH` 固定欄寬，名稱欄 `stretch=1` 吸收 |
| 豎線看起來像欄位分隔線 | 用更淡的 `rgba(128,128,128,40)`、高度 30px、上下留白，與整列高度的第 5、6 條欄線區分 |
| 移除整行 hover 後，使用者不知道可點詳情 | 「詳情」按鈕本身有 hover 與 cursor；列 tooltip 保留 |
| 主色常數造成循環 import（icons→theme） | `theme.py` 只依賴 PySide6，沒有反向依賴，安全 |

回滾：`git checkout -- app/ui/main_window.py app/ui/view_toggle.py app/ui/instance_table.py app/ui/icons.py app/ui/theme.py`。

## 6. 確認清單

- [x] 同意 TopBar 4 顆按鈕全部靠右、標題最左。
- [x] 同意把 `#2D7FF9` 收斂成 `theme.PRIMARY_COLOR`（視覺不變）。
- [x] 同意表格取消整行點擊與 hover 高亮，只留「詳情」按鈕。
- [x] 同意操作欄用 2 條 30px 淡豎線分成 3 區、兩側各 8px。
- [x] 同意不改其他功能。

已依此計畫完成；豎線實際顏色 `rgba(128,128,128,32)`（light `#e1e1e1`／dark `#2c2e30`），比欄位分隔線更淡。
