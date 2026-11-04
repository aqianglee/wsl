# WSL Deck — 進度與下一步（M3／M4／M5）

> 用途：切換新對話時，先讀這份文件即可接續。
> 完整需求與決策見 [wsl-deck-mvp.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-mvp.md)。
> 調研背景見 [wsl-ui-research.md](file:///d:/VirtualMachiles/wsl/plans/wsl-ui-research.md)。

## 1. 目前狀態

- **M1 已完成**：專案骨架、`config.json`、WSL 資料層（註冊表＋`wsl.exe`）、單元測試。
- **M2 已完成**：卡片牆、詳情頁、啟停/終端/資料夾、系統 instance 唯讀、自動輪詢、日誌抽屜、全部關機、游標與視覺細節。
- **M3 已完成**：新增三步精靈、備份／還原／複製／刪除、模態進度框；右鍵選單已依回饋移除，備份／還原／複製／刪除只在詳情頁。
- **M4 已實作（待 GUI 驗收）**：詳情頁網路規則表、CRUD、掃描、一次 UAC 批次套用、啟動與 App 啟動自動重套；資料層與提權已完成端到端實測。
- **尚未開始**：M5（托盤／設定／打包）。
- 測試：42 項全部通過。
  ```
  cd d:\VirtualMachiles\wsl\wsl-deck
  .\.venv\Scripts\python.exe -m unittest discover -s tests -q
  ```

## 2. 如何啟動

開發時用專案內 `.venv`（已安裝 PySide6-Essentials 6.12.0，不影響全局）：

```powershell
d:\VirtualMachiles\wsl\wsl-deck\.venv\Scripts\pythonw.exe d:\VirtualMachiles\wsl\wsl-deck\main.py
```

或雙擊：

```
d:\VirtualMachiles\wsl\wsl-deck\WSL Deck.lnk
```

> 注意：若由 AI 工具的沙箱命令啟動，GUI 子進程會在命令結束時被回收，看起來像「視窗沒出現」。請由使用者自己在 PowerShell 或捷徑啟動。

## 3. 目前 UI 定案（請勿回退）

- 無 Tab。主視窗＝Instance 卡片牆；點卡片進詳情頁；設定齒輪在右下角（M5 才啟用）。
- 卡片三行：
  1. 左上：預設愛心（18×18 繪製）或系統禁止標識（18×18 繪製）；右上：啟動/終止（26×26，綠／紅圖標）與終端（26×26）。
  2. 名稱置中（18pt；名稱 >10 字元縮為 14pt）。
  3. 底部兩顆按鈕：Linux 檔案、安裝目錄；圖標＋文字同一行、居中，高度 40px、最小寬度 120px。
- 卡片高度 185px；名稱距圖標列 `addSpacing(20)`；卡片網格列間距 16px，多餘高度由底部空白列吸收。
- 卡片與按鈕都有邊框、背景與陰影；右上按鈕邊框不隨狀態變色。
- 卡片不提供右鍵選單；備份、還原、複製、刪除只從詳情頁操作（2026-11-02 依回饋移除右鍵選單）。
- 系統 instance（`docker-desktop` 前綴）顯示但全部操作禁用；禁止標識僅提示，不改游標。
- 所有按鈕：可用＝手型游標；禁用＝禁止游標。
- 全域：右上「+ 新增 Instance」（M3）、「全部關機」（有執行中才啟用，會警告含 docker-desktop）。
- 詳情頁：返回、摘要（每列兩組 label:value ≈ 3:7；第一列狀態＋WSL 版本、第二列磁盤大小＋目前 IP、第三列安裝路徑跨欄）、九個動作（啟動/終止、終端、Linux 檔案、安裝目錄、設為預設、備份、還原、複製、刪除）、網路區（M4）。
- 自動更新：開啟、視窗取得焦點、操作後、每 10 秒輪詢；沒有手動重新整理按鈕。
- 日誌：底部可折疊抽屜，錯誤自動展開。

## 4. 程式結構

```
wsl-deck/
  main.py
  config.json              # 執行時生成／保存偏好
  requirements.txt         # PySide6-Essentials==6.12.0
  app/
    config.py              # 配置、命令模板、端口規則
    wsl.py                 # 列表、啟停、IP、系統 instance 判定
    distro_ops.py          # 新增/備份/還原/複製/刪除、線上清單、驗證
    network.py             # 規則驗證、掃描、portproxy 狀態、套用編排
    admin.py               # 一次 UAC 的 netsh 批次
    shell.py               # 終端、Explorer
    logbus.py
    ui/
      main_window.py       # 卡片牆、詳情頁導航、全域動作、輪詢、日誌、M3/M4 編排
      card_wall.py         # 網格與換行
      instance_card.py     # 卡片（含繪製圖標）
      detail_page.py       # 詳情頁
      network_panel.py     # 網路規則表與操作按鈕
      rule_dialog.py       # 新增/編輯規則
      scan_dialog.py       # 掃描結果勾選
      wizard.py            # 新增 Instance 三步精靈
      backup_dialogs.py    # 備份/還原/複製/刪除對話框
      progress.py          # 不可取消的模態進度框
      workers.py           # 背景 TaskWorker（含 stage 訊號）
      cursors.py           # 手型／禁止游標
  tests/                   # 42 項測試
  logs/wsl-deck.log
  WSL Deck.lnk             # 開發期啟動捷徑
```

## 5. M3：新增／備份／還原／複製／刪除（已實作，待 GUI 驗收）

### 5.1 新增 Instance（三步精靈）

1. 來源：官方發行版／rootfs 或 tar／VHDX。
2. 選擇：官方用 `wsl --list --online`；檔案用檔案選擇器。
3. 命名與位置：名稱（官方固定；檔案可改）、安裝目錄（預設 `distro_root\<name>`）、版本（tar 可選 1/2；VHDX 固定 2）。

命令：

| 來源 | 命令 |
|------|------|
| 官方 | `wsl --install -d <name> --location <dir>`（支援時加 `--no-launch`） |
| tar/rootfs | `wsl --import <name> <dir> <file> --version <v>` |
| VHDX | `wsl --import <name> <dir> <file> --version 2 --vhd` |

- 執行前檢查：名稱重複、目錄非空、磁盤空間。
- 模態進度框（不可取消）；完成後刷新並可進入詳情頁。
- 本機 WSL 3.0.3.0 已確認支援 `--install --location`；失敗時提示可「安裝後用 `wsl --manage --move`」。

### 5.2 備份

- 預設 `backup_root\<instance>\<instance>-yyyyMMdd-HHmmss.vhdx`；可改資料夾／檔名。
- 格式預設 VHDX，可切 TAR。
- **實測：VHDX 匯出必須 `wsl --shutdown`**（僅 terminate 仍會 sharing violation）；因此 VHDX 備份會先關閉所有 WSL instance（含 docker-desktop），對話框已明示。TAR 可在執行中匯出。
- 模態進度框。

### 5.3 還原（只做覆蓋式）

- 來源預設在該 instance 的備份資料夾，可選 `.vhdx`／`.tar`。
- 必須先終止；預設勾選「先備份目前狀態」。
- 需輸入 instance 名稱。
- 流程：終止 → 以 TAR 備份現況 → `wsl --unregister` → `wsl --import`（依來源格式加 `--vhd`）。
- TAR 現況備份可在執行中匯出；VHDX 匯入會複製到安裝目錄，原備份檔保留。
- 失敗時用「現況備份」重新匯入；完整步驟寫入日誌。

### 5.4 複製

- 要求新名稱與目標目錄（預設 `distro_root\<newname>`）。
- 流程：以 TAR 匯出暫存 → 匯入新 instance → 刪暫存。
- 不複製端口規則。

### 5.5 刪除

- 需輸入名稱；預設勾選「先備份」（預設格式 TAR）。
- 備份完成 → 終止 → `wsl --unregister`；同步刪除 `config.json` 內該 instance 的端口規則。防火牆規則留待 M4。
- 系統 instance 禁用。

### 5.6 M3 驗收

GUI 手動驗收（只對測試 instance 操作）：

1. 用 `backups\ubuntu\ubuntu.vhdx` 新增 `wsl-deck-test`，3 步內完成，完成後自動進詳情頁。
2. 備份 → 修改內容 → 覆蓋式還原 → 回到備份時狀態。
3. 複製成另一個測試 instance，確認不帶端口規則。
4. 刪除需輸入名稱與預設備份；取消勾選備份才能直接刪。
5. 詳情頁四個按鈕都能開啟對話框；`docker-desktop` 按鈕全禁用。卡片不提供右鍵選單。
6. 完成後清理所有測試 instance 與測試備份。

### 5.7 M3 新增檔案

- `app/distro_ops.py`：建立／匯出／匯入／註銷與驗證、磁盤空間檢查。
- `app/ui/wizard.py`：三步精靈。
- `app/ui/backup_dialogs.py`：備份／還原／複製／刪除對話框。
- `app/ui/progress.py`：模態進度框。
- `app/ui/workers.py`：新增 stage 訊號。

### 5.8 M3 實作結果

- 已完成並以 `wsl-deck-test` 端到端驗證：VHDX 新增 → VHDX 備份 → 寫入標記 → 覆蓋式還原（標記消失）→ 複製 → 刪除（含備份）。
- 測試 instance、`backups\wsl-deck-test` 與 `backups\_tmp` 已清理。
- 實測行為：`--unregister` 會刪除整個安裝資料夾；`--import --vhd` 會複製來源 VHDX 到安裝目錄；TAR 可執行中匯出；VHDX 匯出需先 `wsl --shutdown`。
- GUI 尚未由使用者實際點擊驗收。
- 所有實際操作沿用 `TaskWorker`，UI 不直接拼命令。

## 6. M4：網路規則（已實作，待 GUI 驗收）

- 詳情頁「網路規則」區：
  - 規則表：Windows 端口、distro 端口、允許 LAN、啟用、狀態（已套用／待套用／待啟動／已停用）。
  - 操作：新增、編輯、刪除、立即套用、掃描監聽端口。
- 套用：確認 instance 執行中 → 取得 IP → `netsh interface portproxy add v4tov4` → 若允許 LAN 建立防火牆入站規則。
- 防火牆限 `profile=private`、`remoteip=localsubnet`；規則名稱 `WSL Deck <instance> <windows_port>`。
- 重套時機：App 啟動（多 instance 合併一次 UAC）、instance 啟動成功後、手動套用。
- instance 停止：規則保留並標記「待啟動」；不主動刪除轉發。
- 衝突：同一 Windows 端口只允許一條；套用前檢查非 portproxy 的 TCP 佔用並跳過。
- 掃描：未執行時先詢問是否啟動；`ss -tln` 失敗退回 `netstat -tln`；列出 TCP 端口供勾選。
- 提權：`admin.py` 以 PowerShell `Start-Process -Verb RunAs` 啟動自身副本，批次完成 portproxy＋防火牆，一次 UAC；取消時顯示原因。
- 驗收：新增「8080 → 80」→ 只跳一次 UAC → 同網段另一台可訪問 → 重開機自啟後仍有效（重開機部分待 M5）。

### 6.1 M4 實作結果

- 已用 `wsl-deck-test` 實測 `18080 → 8000`：
  - 一次 UAC 完成刪除舊項＋新增 portproxy＋防火牆規則。
  - `netsh interface portproxy show v4tov4` 顯示 `0.0.0.0 18080 → 192.168.163.232 8000`。
  - 防火牆規則為 `Private`、`LocalSubnet`、TCP 18080。
  - `http://127.0.0.1:18080`、`http://192.168.1.6:18080`、直連 distro IP 均回 200。
  - 規則狀態顯示「已套用」；清理 job 成功移除 portproxy 與防火牆。
- 測試 instance、portproxy、防火牆規則與測試備份已清理。
- 注意：本機目前網路 `Pisoft 4` 為 **Public**；同一台電腦以區網 IP 訪問可通，**其他裝置會被 private 防火牆規則阻擋**，需將網路設為 Private 才能做跨裝置驗收。
- GUI 尚未由使用者實際點擊驗收。

## 7. M5：托盤／設定／打包

- 托盤：`QSystemTrayIcon`；關窗縮托盤；選單：顯示主視窗、啟動預設 instance、全部關機、重新套用網路、結束。
- 開機自啟：`HKCU\...\CurrentVersion\Run`，以 `--silent` 啟動到托盤。
- 設定對話框：`distro_root`、`backup_root`、開機自啟、關窗縮托盤、輪詢間隔、主題（跟隨系統／深／淺）、進階模式（顯示命令）、系統 instance 清單。
- 主題：Qt palette 切換；卡片與按鈕沿用現有 QSS。
- 打包：PyInstaller onedir；捷徑改指向 exe；確認 autostart 指向 exe。
- 驗收：關窗縮托盤；開機自動進托盤；設定重啟後保留；產出資料夾＋exe，無需 Python 環境即可執行。

## 8. 已知注意事項

- 沙箱啟動 GUI 會被回收；請使用者自行啟動。
- `config.json` 可能還留有舊鍵（`preview_commands`、`minimize_to_tray`）；程式用 `Config.get()` 讀新鍵，M5 可做一次性遷移。
- 系統 instance 以名稱前綴判定（`docker-desktop` 等），可在設定維護。
- `wsl.exe` 輸出含空字元／本地化文字；以註冊表為主、CLI 狀態為輔。
- VHDX 匯出需先 `wsl --shutdown`；TAR 可在執行中匯出。`--import --vhd` 會把來源 VHDX 複製到安裝目錄；`--unregister` 會刪除整個安裝資料夾。
- `export_vhd` 命令模板已修正為 `--format vhd`（舊 `--vhd` 無效）。
- 提權用 PowerShell `Start-Process -Verb RunAs -Wait`；取消 UAC 回傳 `denied`，不會自動重試。
- `netsh` 刪除不存在的 portproxy／防火牆規則會回傳錯誤，屬正常清理 warning，不影響新增。
- 目前網路為 Public；跨裝置 LAN 驗收前需改成 Private。
- M5 打包後，提權子進程需從 `pythonw -m app.admin` 改為 exe 參數入口。
- 不複製 GPL 專案代碼，只參考功能設計。

## 9. 新對話接續方式

1. 先讀本文件與 [wsl-deck-mvp.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-mvp.md)、[wsl-deck-m3.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m3.md)、[wsl-deck-m4.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m4.md)。
2. 確認目前程式可啟動、42 項測試通過。
3. 由使用者完成 M4 GUI 驗收（規則 CRUD、掃描、一次 UAC、啟動重套）；跨裝置測試需先將網路設為 Private。
4. M4 驗收通過後，從 M5 開始：先寫 M5 實作計畫（托盤、自啟、設定、主題、打包），等使用者確認後再動工。
5. 建議測試 instance 名稱：`wsl-deck-test`；所有破壞性測試只作用於測試 instance。
