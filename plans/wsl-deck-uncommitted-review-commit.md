# 未提交變更：審查與分批提交

> 狀態：**已確認**

## 1. 目標

1. 以 `git diff HEAD`（fixed point = `HEAD`，commit `70612d5`）審查目前工作區未提交的 13 個已修改檔＋9 個未追蹤 SVG＋13 份計畫文件。
2. 依「Standards（代碼規範）／Spec（計畫符合度）」兩軸輸出審查結果。
3. 一次性提交全部變更（分批會造成中間態無法執行），在 commit message 中逐項列清楚本次優化。

## 2. 已核實事實

- `git status`：13 個 `M`（`wsl-deck/WSL Deck.spec`、`app/ui/` 下 12 個 py）、13 個未追蹤計畫文件、9 個未追蹤 SVG。
- 規模：`+859 / −323`。
- 目前狀態：`.venv` 下 `unittest discover` **154 項全數通過**（1.057s）。
- 規範文件：`docs/handover/05-risks-conventions.md`、`docs/handover/02-architecture.md`（repo 根目錄無 `CODING_STANDARDS.md`／`CONTRIBUTING.md`）。
- 規格來源：`plans/` 下 13 份未追蹤計畫（本次 UI 迭代）。

## 3. 變更摘要（按主題）

| 主題 | 檔案 | 內容 |
|------|------|------|
| 圖標資產 | `icons.py`、`theme.py`、`assets/*.svg`、`WSL Deck.spec` | 新增 9 個 SVG；`QSvgRenderer` 渲染後 `SourceIn` 上色；新增 `back/add/backup/restore/snapshot/copy/delete/heart_outline/settings_themed` 等 icon；`PRIMARY_COLOR` 收斂主色；打包改收整個 `assets` 目錄 |
| 三段式佈局 | `main_window.py`、`view_toggle.py`、`card_wall.py` | 新增 TopBar（首頁列／詳情列 `QStackedWidget`）、BottomBar（日誌鈕＋狀態＋設定鈕）、日誌面板獨立；移除浮動設定 FAB 與 `resizeEvent` 定位；卡片牆左右內距 24px；視圖切換改膠囊樣式 |
| 詳情頁 | `detail_page.py`、`instance_card.py` | 摘要區改圓角卡片、名稱＋三態徽章（系統／預設／一般）；操作列分類分組＋豎線；設定鈕移入詳情卡；返回鈕移到 TopBar；卡片之星改空心愛心 |
| 表格 | `instance_table.py` | 外層圓角卡片＋陰影；表頭等高 48px、背景 `palette(window)`；詳情改連結樣式、移除整列點擊；操作區分三區加豎線；`BUTTONS_WIDTH` 348→366 |
| 對話框 | `dialog_base.py`、`settings_dialog.py`、`instance_settings_dialog.py`、`network_panel.py` | 內容區可滾動（上限「可用高度 − 120」）＋固定 footer；確定鈕主色；`QGroupBox` 全面改 `sectionCard` 卡片；設定對話框重組為「目錄／一般／SOCKS5」三卡 |
| 文件 | `plans/*.md`（13） | 本次迭代計畫 |

## 4. 審查結果

### Standards（規範軸）

硬違規：
- `detail_page.py` `_make_action(text, icon, parent)` 缺型別註解（05 §6.2）。
- `dialog_base.py` `_ContentScrollArea` 類別後僅 1 空白行（PEP8 E305）。
- 尺寸魔數重複：`QSize(18, 18)` 徽章在 3 檔共 6 次；`pad=4`、`setFixedSize(1, 32)` 未常數化（05 §6.6）。
- 顏色硬編碼：`#1F66CC/#1A5BB3/#A9C7F5/#9aa0a6/#4a90e2/#7f8c8d/#e74c3c/#c9ced6` 散落 5 檔；`PRIMARY_COLOR` 只收斂 `#2D7FF9`（05 P3-3 只做一半）；`rgba(128,128,128,30~70)` α 值無語意常數。
- `icons.py` `add_icon` 用 `"#FFFFFF"`，未重用既有 `ACTIVE_ICON_COLOR`。
- `view_toggle.py` 用 `%` 插值，其餘新 QSS 用 f-string。

判斷性（異味）：
- Duplicated Code／Repeated Switches：三態徽章邏輯在 3 處各自實作，宜抽 `badge_for()`。
- `CARD_STYLE` 三份（`detail_page`／`network_panel`／`dialog_base`）、`_title_font` 三份。
- `icons.py` 10 個單行 wrapper 可用映射表；新圖標缺 QPainter 回退（02 §3.2 既有做法）。
- `main_window.py` 主題切換兩處重貼 back/settings icon，宜抽 `_apply_themed_icons()`。
- `settings_dialog` `removeItem(self._form)` 硬拔基底表單，兩套表單並存。
- 命名不一致：`_badge`／`_star`／`_icon`；`theme.py` 註解「全城」應為「全域」。
- `settings_fab_icon()` 已無呼叫者（死碼）；icon 每次 refresh 重繪 5 個 pixmap 無快取。

### Spec（計畫軸）

- 未實作／只做一半：`network_panel` 標題與內容間距仍 8（計畫要求 10）；`instance_settings_dialog` 仍用 `insertWidget(1/2/3)`（計畫風險對策寫「改用 append」）；`view_toggle` 未用 f-string。
- 範圍蔓延：`WSL Deck.spec` 改收整個 assets（13 份計畫未列）；新增 `:pressed` 樣式與 TopBar 常數化屬額外重構。
- 疑似實作有誤：表格根 margin 為 `(24,12,24,12)`，計畫 §3.1 寫 `(0,8,0,8)`、§7 又寫 24/12（計畫自相矛盾）；詳情卡 11 顆鈕在 `_build()` 一次性取色，主題切換後不重著色。
- 無誤項：24px 對齊、10px 圓角、返回鈕 72px、footer 固定、`BUTTONS_WIDTH=366`、豎線尺寸。

> 以上問題本次**不修改**（僅記錄），除非另行確認。

## 5. 提交方案（單一 commit）

分批提交會讓中間態缺 `PRIMARY_COLOR`／icon API 而無法執行，故改為**一次提交全部變更**，並在 commit message 內按「圖標與主題／三段式佈局／詳情頁／表格／對話框／計畫」逐項列出優化。

納入檔案：

- `app/ui/`：`icons.py`、`theme.py`、`main_window.py`、`view_toggle.py`、`card_wall.py`、`detail_page.py`、`instance_card.py`、`instance_table.py`、`dialog_base.py`、`settings_dialog.py`、`instance_settings_dialog.py`、`network_panel.py`
- `assets/*.svg`（9）、`WSL Deck.spec`
- `plans/*.md`（13 份既有計畫＋本計畫）

提交訊息標題：`feat(ui): 三段式佈局、SVG 圖標與卡片化對話框`

## 6. 驗證

1. 提交前：`unittest discover`（已跑，154 項 OK）。
2. 提交前：`python -m py_compile` 12 個變更 `.py` 檔。
3. 提交後：`git status` 應為 clean、`git log --stat -1` 核對內容。

## 7. 風險與回滾

| 風險 | 對策 |
|------|------|
| 打包 spec 改收整個 `assets` 目錄，可能帶入非必要檔案 | 目前 `assets/` 僅圖標資源；若日後增大再收窄 |
| 分批提交中間狀態不可執行 | 依序提交，#1 先提供被依賴常數；僅本地 commit，不 push |

回滾：`git reset --soft HEAD~6`（保留變更）或逐批 `git revert`。

## 8. 確認清單

- [ ] 同意「6 個主題 commit」分批方案（順序如上）。
- [ ] 同意第 4 節審查發現**本次不修**，僅記錄於本計畫。
- [ ] 同意僅建立本地 commit，不 push 遠端。
