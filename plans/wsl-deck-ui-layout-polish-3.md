# UI 對齊與表格卡片化

> 狀態：**已完成**
> 目標：
> 1. TopBar／中間內容／FooterBar 左右 padding 統一為 **24px**；只保留這一層 content padding，卡片牆、表格、詳情頁都去掉多餘的 container margin。表格卡片左右緣、標題、右上按鈕、Footer 全部對齊同一條 24px 基準線。
> 2. TopBar 四個按鈕分區：`新增 + 全部關機` 一區｜`卡片/列表膠囊` 一區，中間以 1 條豎線分隔；兩顆互斥鈕合併成膠囊。
> 3. 表格「詳情」改為 link 樣式：主色文字、無邊框，hover 才出現按鈕感。
> 4. 表格改為白色圓角卡片＋浮動陰影；表頭與內容行等高（48px）、文字加粗加黑、表頭底色用目前背景色。

## 1. 已核實事實

- 目前左右 padding 不一致：TopBar/BottomBar/日誌為 16，主頁面（[main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py#L338-L343)）16 + 表格內距 `TABLE_MARGIN=12` ⇒ 表格實際距視窗 28；卡片牆 16+12=28；詳情頁 20。
- [instance_table.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_table.py)：
  - `HEADER_HEIGHT = 32`、`ROW_HEIGHT = 48`；表頭文字 `_header_font()` 10pt 粗體、顏色 `#7f8c8d`；表頭背景透明（頁面底色）。
  - 表格本體是 `header + 內層 QScrollArea`，無卡片背景；列背景透明、列高 48。
  - 詳情鈕用 `QPushButton#rowAction`（有邊框、palette(button) 底），尺寸 64×26。
  - 表格放在主頁面的外層 `QScrollArea` 中，`InstanceTable` 自己有內層滾動區。
- [view_toggle.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/view_toggle.py#L20-L34)：兩顆 32×32 按鈕，間距 4，各自有 1px 邊框＋圓角 7；`:checked` 為主色。
- 詳情頁內容邊距 `(20, 12, 20, 16)`（[detail_page.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/detail_page.py#L49-L56)）。
- 主色常數 `theme.PRIMARY_COLOR = "#2D7FF9"` 已存在。

## 2. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | 新增 `CONTENT_MARGIN = 24`，TopBar／BottomBar／日誌面板沿用；主頁面左右 margin 改 0（垂直維持 12）；TopBar 在「全部關機」與膠囊之間插入 1 條分區豎線。 |
| `app/ui/card_wall.py` | 卡片牆內距 12 → 24（移除 page 的 16 後，卡片左緣仍在 24）。 |
| `app/ui/detail_page.py` | 內容左右 margin 20 → 24。 |
| `app/ui/view_toggle.py` | 兩鈕間距 0、去掉間隔，左鈕只留左圓角、右鈕只留右圓角，合併成膠囊；hover／checked 樣式同步。 |
| `app/ui/instance_table.py` | `TABLE_MARGIN` 12 → 0（表格不再有外 margin）；新增 `QFrame#tableCard`（`palette(base)` 白底、圓角 10、1px 淡邊、QGraphicsDropShadowEffect）；表頭高 48、底色 `palette(window)`、文字 `palette(windowtext)` 11pt 粗體；詳情鈕改 `#detailLink` link 樣式；滾動區 viewport 透明。 |

- 不改任何業務邏輯與卡片內容。

## 3. 細節規格

### 3.1 對齊（CONTENT_MARGIN = 24，只保留這一層）
- TopBar 兩列 `contentsMargins` 改 `(24, 8, 24, 8)`；BottomBar 改 `(24, 6, 24, 6)`；日誌面板改 `(24, 8, 24, 0)`。
- 主頁面 layout 改 `(0, 12, 0, 12)`；`CardWall` 內距改 `(24, 12, 24, 12)`；`DetailPage` 改 `(24, 12, 24, 16)`。
- 表格：`TABLE_MARGIN = 0`，`InstanceTable` 根 layout 只留陰影空間 `(0, 8, 0, 8)`；白卡左右緣 = 視窗 24px ⇒ 與標題／右上按鈕／Footer 對齊。表頭與列的欄位內容也從卡片內緣開始，不再有 12px 外 margin（總計就是 24px）。

### 3.2 TopBar 分區
- 順序：`WSL Deck` → stretch → `+ 新增 Instance` → `全部關機` → **豎線** → `ViewToggle`（膠囊）。
- 豎線：`QFrame#topBarDivider`，`1 × 32px`、垂直置中，顏色 `rgba(128, 128, 128, 50)`；豎線兩側各留 10px（layout spacing 10）。
- 「新增 + 全部關機」之間維持 8px，屬同一區。

### 3.3 膠囊切換
- `ViewToggle` layout spacing 0、margin 0；兩顆 32×32。
- 左鈕 `QToolButton#viewToggleLeft`：`border-top-left-radius: 7; border-bottom-left-radius: 7;` 右上／右下 0，`border-right: none`。
- 右鈕 `QToolButton#viewToggleRight`：鏡像（左側 0 圓角、`border-left: none`）。
- 未選中：底 `palette(button)`、邊框 `palette(mid)`；hover 底 `palette(midlight)`；
- 選中：底與邊框 `PRIMARY_COLOR`、圖標白；hover 主色加深 `#1F66CC`。
- 兩鈕合併後外觀為單一膠囊（64×32）。

### 3.4 表格卡片
- 結構：`InstanceTable`（透明）→ `QFrame#tableCard`（`palette(base)` 底、`border: 1px solid rgba(128,128,128,30)`、`border-radius: 10px`）→ `header` + `QScrollArea`。
- 陰影：`QGraphicsDropShadowEffect`（blur 24、offset (0, 4)、`rgba(0,0,0,45)`），套在 `tableCard`；上下留 8px、左右留 24px 的空間，陰影不被裁切。
- 表頭：`QFrame#tableHeader`，固定高度 `ROW_HEIGHT = 48`，背景 `palette(window)`（目前頁面底色），上圓角 10；文字 11pt 粗體、`palette(windowtext)`；只保留底部 1px `rgba(128,128,128,65)` 分隔線；`_apply_header_margin` 只保留右側 scrollbar gutter。
- 首欄／末欄不畫外側豎線，避免與卡片圓角邊重疊；欄與欄之間的豎線維持。
- 內容：`QScrollArea` viewport 與 rows host 透明（露出卡片白底）；列高 48、列間底部 1px `rgba(128,128,128,45)` 不變。
- 深色主題：卡片用 `palette(base)` `#1b1d20`、表頭 `palette(window)` `#202225`（沿用既有深色規則，不以純白刺眼）。

### 3.5 詳情 link
- `QPushButton#detailLink`：`background: transparent; border: 1px solid transparent; border-radius: 7px; color: PRIMARY_COLOR; padding: 4px 10px;` 尺寸維持 64×26。
- `:hover`：底 `palette(button)`、邊框 `palette(mid)`（主色文字不變）。
- `:pressed`：底 `palette(midlight)`。
- `:disabled`：`color: #9aa0a6; border-color: transparent; background: transparent`。
- 其他 4 顆操作鈕樣式不變（仍是有框按鈕）。

## 4. 驗證

1. `python -m py_compile app\ui\main_window.py app\ui\view_toggle.py app\ui\instance_table.py app\ui\card_wall.py app\ui\detail_page.py`
2. `python -m unittest discover -s tests -q`（預期 154 項全過）。
3. 離屏渲染 light／dark（1000×700）：
   - 幾何檢查：TopBar 標題 x=24、表格卡片左右緣 x=24／976、BottomBar 齒輪右緣距邊 24，全部一致；
   - 表頭與列高皆 48，表頭字粗且為深色；
   - 詳情鈕常態無邊框、主色文字；模擬 hover 截圖應出現底色與邊框；
   - TopBar 1 條豎線、右側膠囊（兩鈕合併無縫）；
   - 卡片圓角與陰影可見，深色主題下不刺眼。

## 5. 風險與回滾

| 風險 | 對策 |
|------|------|
| 卡片陰影被外層 scroll viewport 裁切 | 卡片距 viewport 左右 24px、上下 8px，blur 24 的擴散約 12px，不會被裁 |
| 膠囊接縫出現雙線 | 左鈕 `border-right: none`、右鈕 `border-left: none`，只保留外輪廓 |
| 表頭改 48 後內容區變矮 | 表頭與列等高屬需求，內容區由內層 scroll 吸收 |
| 深色主題白卡片刺眼 | 卡片走 `palette(base)`、表頭走 `palette(window)`，不硬編碼白色 |
| 外層與內層雙重 scroll 造成陰影或滾動異常 | 外層 QScrollArea 不滾動（內容交給內層），陰影留在內距內 |

回滾：`git checkout -- app/ui/main_window.py app/ui/view_toggle.py app/ui/instance_table.py app/ui/card_wall.py app/ui/detail_page.py`。

## 6. 確認清單

- [x] 同意左右 padding 全部統一成單一 24px（TopBar／內容／Footer／表格卡片外緣），去掉卡片牆與表格的額外 container margin。
- [x] 同意首欄／末欄不畫外側豎線（避免與白卡圓角衝突），保留欄間豎線。
- [x] 同意 TopBar 用 1 條豎線分成 2 區（新增+全部關機｜膠囊）。
- [x] 同意「詳情」改主色 link、hover 才有按鈕外觀。
- [x] 同意表格白底圓角＋陰影，表頭 48px、粗黑字、底色用目前頁面背景色。
- [x] 同意深色主題下卡片改用 `palette(base)` 深色（不強制純白）。
- [x] 同意不改其他功能。

## 7. 實作與驗證結果

- 對齊基準：`CONTENT_MARGIN = 24`；主頁面 `(0, 12, 0, 12)`、CardWall `(24, 12, 24, 12)`、DetailPage `(24, 12, 24, 16)`、TopBar `(24, 8, 24, 8)`、BottomBar `(24, 6, 24, 6)`、日誌 `(24, 8, 24, 0)`。
- 表格：`TABLE_MARGIN` 移除，`InstanceTable` 根 layout 只留陰影空間 `(24, 12, 24, 12)`；`QFrame#tableCard` 白底＋圓角 10＋1px 淡邊＋QGraphicsDropShadowEffect（blur 24、offset (0,4)、rgba(0,0,0,45)）。
- 表頭：48px、`palette(window)` 底色、11pt 粗體 `palette(windowtext)`、只留底部 1px 線；首欄／末欄外側豎線已移除。
- 詳情鈕：`QPushButton#detailLink`，主色文字、透明邊框，hover 才出現底色與邊框。
- 滾動區：viewport 與 rows host 不填底色（`setAutoFillBackground(False)`，且必須在 `setWidget` 之後設定，否則會被 QScrollArea 重新開啟）。
- 驗證：`py_compile` 通過；`unittest discover` **154 項全過**；離屏 light／dark 截圖確認：
  - 標題 x=24、表格卡片 24…976、TopBar 膠囊 912…976、BottomBar 齒輪右緣 976，全部同一條基準線；
  - 表頭與列皆 48px；淺色卡片 `#ffffff`、表頭 `#efefef`；深色卡片 `#1b1d20`、表頭 `#202225`；
  - 膠囊左右鈕 32+32 無縫合併；TopBar 分區豎線 1×32 可見；
  - 詳情頁 summary 卡片 24…976。
