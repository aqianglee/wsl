# Plan：WSL Deck 交接文檔（docs/handover/）

> 目的：專案由 AI 產出，接手人具備 Java 底子但不熟 Python 生態。交付一套可獨立閱讀的交接文檔，讓他能（1）看懂程式、（2）跑起來、（3）安全地改、（4）打包發布。
> 狀態：**待確認**，確認後才開始撰寫。

## 1. 已確認的決策

| 決策 | 結論 |
|------|------|
| 文件位置 | `docs/handover/`，拆成 6 份 |
| 正文語言 | 繁體中文；程式碼、命令、術語保留英文 |
| Python 速成比重 | 重點章節，約占全部篇幅三分之一 |
| 必寫模組 | 構建發布、故障排查、風險清單、AI 編碼風格（四項全要） |
| 圖表形式 | Mermaid 為主，關鍵處用純文字補充 |
| 技術債 | 單列一章，按影響分級，含對 AI 產碼品質的客觀評價 |
| 驗證範圍 | 只跑單元測試（已跑 135 項全通過）＋靜態核對腳本；不實跑打包、不啟動 GUI |

## 2. 產出物清單

寫入 `docs/handover/`，共 6 個檔案，總計約 1800–2100 行。

### 00-overview.md（約 150–200 行）

- 一句話定位與非目標（它能做什麼、刻意不做什麼）
- 一頁速覽表：GUI 框架、Python 版本、依賴、外部進程、產物形態、規模
- 5 分鐘跑起來：venv 路徑、測試命令、啟動命令、日誌位置
- 目錄地圖（樹狀圖 + 每個目錄一句話）
- 三條閱讀路徑：只想改 UI／只想改業務／只想打包發布
- 術語表：instance、distro、rootfs、vhdx、portproxy、restic、QSS、Signal/Slot 等中英對照
- 交接 checklist（環境、未驗收項、待辦）

### 01-python-primer.md（約 400–500 行）

- Java 視角差異總表（10 條以內，先給結論）
- 語言層逐條對照，每條都附本專案真實 `file:line` 例子：
  模組與套件、`__init__.py`、import 機制、venv/pip 對比 Maven、型別註解、dataclass 對比 POJO/Lombok、property、dunder、異常、`with`、推導式、lambda 閉包延遲綁定、可變預設參數、`if not x` 與 `x or default` 的坑、`_` 前綴慣例、GIL
- 工程工具鏈：unittest 對比 JUnit、`unittest.mock`、本專案沒有 lint／型別檢查／CI
- Qt 心智模型：QApplication 與事件迴圈對比 Swing EDT、Signal/Slot 對比監聽器、QRunnable/QThreadPool 對比 ExecutorService、物件樹 parent 與記憶體管理對比 GC、QSS 對比 CSS、`palette()` 主題變數

### 02-architecture.md（約 400–500 行）

- 分層圖（Mermaid）：`app/ui` 表現層 / `app/*` 業務層 / 外部進程
- 依賴方向規則，以及**兩個現實例外**（MainWindow 內直接做流程編排、`network.apply_rules` 延遲 import `admin`）
- 全部模組職責表（約 35 個 .py，一行一個）
- 啟動時序（Mermaid）：main → 單實例 → Config → 日誌 → 代理 → 主題 → 工作目錄 → MainWindow
- 刷新輪詢時序（Mermaid）：QTimer → refresh → TaskWorker → Signal → `_on_distros`
- 提權時序（Mermaid）：apply_rules → build_admin_job → run_admin_job → PowerShell RunAs → `app.admin.main` → result JSON 回寫
- 資料模型：Distro、Snapshot、InstanceSettings、PortProxyEntry、WorkspacePaths
- 配置模型：DEFAULT_CONFIG、`_migrate`、`_validate`、原子寫入、LEGACY_KEYS
- MainWindow 的隱含狀態機（`_refresh_busy`、`_current`、`_pending_cleanup`、`_auto_apply_done` 等欄位語義）
- 擴充點清單：新增一個動作/按鈕要動哪些檔案

### 03-build-release.md（約 250–300 行）

- 環境準備與開發運行（`pythonw` 啟動的原因）
- 測試命令與目前結果
- PyInstaller onedir：spec 逐欄位解釋、`hiddenimports=["app.admin"]` 為什麼必須、`datas` 圖示
- `build.ps1`：為何把 `$ErrorActionPreference` 改成 Continue（PowerShell 5.1 把 stderr 當終止錯誤）
- Inno Setup：`config.json` 用 `onlyifdoesntexist`、Excludes 的用意
- `build-zip.ps1`：版本號從哪來、為何預設排除 config.json 與 logs
- 版本號唯一來源與升版步驟
- 凍結前後行為差異表：`app_dir()`、開機自啟只支援 exe、提權子進程命令變化、`sys.executable` 語義
- 發布 checklist
- 明示「本次交接未實跑打包」

### 04-troubleshooting.md（約 200–250 行）

- 統一表格格式：現象／可能原因／排查命令／處理方式
- 分五組：啟動類、WSL 資料類、備份還原與快照類、網路與防火牆類、打包類
- 日誌位置、UI 日誌抽屜與檔案日誌的差異
- `config.json` 校驗失敗、`.pre-m5.bak` 遷移備份的處理
- 每個條目都要能指回原始碼位置或 plans 文件

### 05-risks-conventions.md（約 300–350 行）

- 破壞性操作清單（逐條標影響面與不可逆性）：`--unregister` 刪整個安裝目錄、VHDX 匯出需 `--shutdown`、還原失敗回滾、刪除預設備份、portproxy 全域、防火牆僅 private、代理改全進程環境變數、restic 整機還原的排除項
- 權限模型：哪一步需要 UAC、取消 UAC 如何在 UI 呈現
- 資料安全：`repo.pass` 明文存放、備份未加密
- 技術債分級：
  - P1 拖慢接手（MainWindow 1200+ 行上帝類、狀態欄位過多）
  - P2 引發故障（業務層直接拼 shell 字串、部分 `except` 只記日誌、異常訊息直接顯示給使用者、無型別檢查/CI）
  - P3 風格（重複的 subprocess 樣板、註解與 UI 文案繁簡不一、常數散落）
  - 每條給：症狀、影響面、建議改法、改動風險
- AI 產碼特徵與應對（條列，不帶情緒）
- 編碼約定（本專案既成事實）：註解與 UI 文案繁體、自訂異常類型、日誌格式、耗時操作必須走 TaskWorker、Config 是配置唯一入口、業務層禁止 import UI、不用 emoji、QSS 用 `palette(...)`
- 繼續用 AI 協作的建議：先寫 plan、`plans/` 命名規範、每次改動必跑測試命令

## 3. 撰寫順序

1. `00-overview.md`：先立骨架與術語，後續章節引用它
2. `02-architecture.md`：架構是其他章節的參照點
3. `01-python-primer.md`：例子要與架構章一致
4. `03-build-release.md`
5. `04-troubleshooting.md`
6. `05-risks-conventions.md`：最後寫，彙總前面發現的問題

## 4. 驗收標準

- 每個技術論斷都能指回 `file:line` 或命令輸出，不出現「大概」「應該是」
- 所有命令標註「已實測／未實測」；測試結果引用實際輸出（135 tests OK）
- 讀者只讀 `00` + `02` 就能說出「啟動→輪詢→提權」三條主鏈
- 不出現簡繁混排；引用程式原文時保留原樣
- 不修改任何原始碼；只新增 `docs/handover/` 六個檔案

## 5. 明確不做

- 不跑 `build.ps1`、`build-installer.ps1`、`build-zip.ps1`（不產生 `build/`、`dist/` 垃圾）
- 不啟動 GUI（AI 沙箱啟動的 GUI 會被回收，無法作為證據）
- 不操作任何真實 WSL instance、不改 `config.json`、不觸發 UAC
- 不改動既有 `plans/*.md` 內容

## 6. 需要你確認的小項

1. 舊文件 [wsl-deck-handoff.md](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/plans/wsl-deck-handoff.md) 內容已過時（路徑仍寫 `d:/VirtualMachiles/wsl`）。建議只在該檔頂端加一行「已歸檔，請看 `docs/handover/00-overview.md`」，不改其餘內容。
2. `docs/handover/` 不另寫 README，由 `00-overview.md` 兼任索引。
3. 文件內會引用 `plans/wsl-deck-mvp.md` 等既有計畫作為需求來源，但不複製其全文。
