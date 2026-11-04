# Plan：WSL Deck — GUI-first MVP（v2）

> 狀態：待確認（確認後才動工）
> 本版依 2026-10-30 需求訪談重寫，取代先前「配置為中心」的版本。
> 調研背景見 [wsl-ui-research.md](file:///d:/VirtualMachiles/wsl/plans/wsl-ui-research.md)

## 1. 定位

- 個人自用的 Windows GUI，管理 WSL instance；低頻使用、不想記參數。
- 三個等權重場景：新增／備份還原、啟停與終端、端口轉發。
- **不以配置文件為操作入口**：所有功能都是按鈕或圖標；`config.json` 只保存偏好與規則。

## 2. 資訊架構

```
主視窗（Instance 卡片牆）
├─ 頂部：App 名稱｜新增 Instance｜全部關機
├─ 卡片網格：每個 instance 一張卡
├─ 右下角齒輪：設定對話框
└─ 底部：可折疊日誌抽屜

Instance 詳情頁（點卡片進入）
├─ 返回
├─ 摘要：狀態、大小、路徑、目前 IP
├─ 動作列：啟動/終止、終端、Linux 檔案、安裝目錄、備份、還原、複製、刪除
└─ 網路規則區：規則列表、新增、掃描監聽端口

新增 Instance 精靈（3 步）
```

沒有 Tab；網路是「每個 instance 自己的」，因此放在詳情頁，不設全域網路頁。

## 3. 主頁：Instance 卡片牆

### 卡片內容

- 名稱（置中）＋ 狀態色條：綠＝執行中、灰＝已停止；預設 instance 加小星標。
- 右上角兩個圖標：啟動/終止（依狀態切換同一位置）、終端。
- 底部兩個「圖標＋文字」按鈕：`Linux 檔案`（開啟 `\\wsl$\<name>\`）、`安裝目錄`（開啟 Windows BasePath）。
- 點卡片空白處 → 進入詳情頁；點圖標不觸發跳頁。
- 右鍵選單（圖標＋文字）：備份、還原、複製、刪除。

### 系統 instance

- `docker-desktop`、`docker-desktop-data` 等系統 instance **顯示但全部操作禁用**（圖標灰化，右鍵選單不出現）。
- 判定：名稱前綴 `docker-desktop`；可在進階設定維護清單。

### 全域動作

- 右上：`+ 新增 Instance`、`全部關機`。
- `全部關機` 執行前確認框列出所有執行中的 instance（含 docker-desktop），明確警告會一併終止。
- 無「重新整理」按鈕。

### 狀態更新

- 開啟 App、視窗重新獲得焦點、每次操作完成後自動重讀。
- 每 10 秒定時輪詢（可在設定調整）。
- 排序：預設 instance 最前，其餘依名稱。

## 4. Instance 詳情頁

單欄由上到下：

1. `← 返回` 與 instance 名稱。
2. 摘要：狀態、WSL 版本、大小、BasePath、目前 IP（未執行顯示「未執行」）。
3. 動作列（八項，與右鍵選單行為一致）：啟動/終止、終端、Linux 檔案、安裝目錄、備份、還原、複製、刪除。
4. 網路規則區：
   - 規則表：Windows 端口、distro 端口、允許 LAN、啟用、狀態（已套用／待套用／待啟動）。
   - 按鈕：新增規則、編輯、刪除、立即套用、掃描監聽端口。
   - 掃描：instance 未執行時先詢問是否啟動；用 `ss -tln`，失敗退回 `netstat -tln`；列出 TCP 端口，勾選後才加入規則。
   - 不列出 Windows 主機完整網路資訊；僅在新增規則時檢查 Windows 端口是否已被佔用。

## 5. 新增 Instance 精靈

三步：

1. **來源**：官方發行版／rootfs 或 tar／VHDX。
2. **選擇**：
   - 官方：`wsl --list --online` 清單。
   - 檔案：檔案選擇器（`.tar`、`.tar.gz`、`.vhdx`）。
3. **命名與位置**：名稱（官方固定不可改；檔案來源可改）、安裝目錄（預設 `distro_root\<name>`）、版本（tar 可選 1/2，vhdx 固定 2）。

執行：

| 來源 | 命令 |
|------|------|
| 官方 | `wsl --install -d <name> --location <dir>`（支援時加 `--no-launch`；失敗提示可安裝後用 `wsl --manage --move`） |
| rootfs/tar | `wsl --import <name> <dir> <file> --version <v>` |
| VHDX | `wsl --import <name> <dir> <file> --version 2 --vhd` |

- 全程模態進度框；完成後刷新並可選擇直接進入詳情頁。
- 名稱重複、目錄非空、磁盤空間不足都在執行前檢查。

## 6. 備份／還原／複製／刪除

### 備份

- 預設路徑：`backup_root\<instance>\<instance>-yyyyMMdd-HHmmss.vhdx`（可改路徑與檔名）。
- 格式預設 VHDX，可切 tar。
- 若 instance 執行中，提示「執行中也可匯出快照；建議先終止以確保一致」。
- 模態進度框，不提供中途取消。

### 還原（只做覆蓋式）

- 只作用於目前選中的 instance；來源預設開在該 instance 的備份資料夾，可選 `.vhdx` 或 `.tar`。
- 必須先終止 instance（若執行中，確認後代為終止）。
- 預設勾選「先備份目前狀態」，存到同一備份資料夾。
- 需手動輸入 instance 名稱才能執行。
- 流程：備份現況 → `wsl --unregister` → 複製備份到安裝目錄 → `wsl --import ...`（依格式加 `--vhd`）。
- 失敗時盡量以「現況備份」重新匯入，並在日誌保留完整步驟。

### 複製

- 要求新名稱與目標目錄（預設 `distro_root\<newname>`）。
- 流程：匯出暫存檔 → 匯入新 instance → 刪除暫存檔。
- 不複製端口規則（避免端口衝突）。
- 模態進度框；大型 instance 會提示預估時間與所需空間。

### 刪除

- 需輸入 instance 名稱。
- 預設勾選「先備份」，備份完成才執行 `wsl --unregister`。
- 同步刪除該 instance 的端口規則與對應防火牆規則。
- 系統 instance 禁用。

## 7. 網路與防火牆

- 規則欄位：Windows 端口、distro 端口、允許 LAN（預設勾選）、啟用。
- 套用流程：確認 instance 執行中 → 取得目前 IP → `netsh interface portproxy add v4tov4` → 若允許 LAN，建立防火牆入站規則。
- 防火牆範圍：`profile=private remoteip=localsubnet`，只對本地網段開放，不對 Public 開放；規則名稱 `WSL Deck <instance> <windows_port>`。
- 重套時機：App 啟動、instance 啟動成功後、開機自啟後、手動按「立即套用」。
- instance 停止時：規則保留但標記「待啟動」，不寫入指向舊 IP 的 portproxy。
- 衝突檢查：同一 Windows 端口只允許一條規則；套用前檢查 Windows 端是否已被其他程式佔用。

## 8. 權限

- 平時普通權限。
- 只有寫入 portproxy／防火牆時按需提權：以 `runas` 啟動自身副本，批次完成所有變更；一次 UAC。
- 使用者拒絕 UAC 時，顯示原因與「以管理員重啟」選項，不重複彈窗。

## 9. 托盤與開機自啟

- 關閉視窗＝縮到托盤，不退出。
- 托盤右鍵選單：顯示主視窗、啟動預設 instance、全部關機、重新套用網路規則、結束。
- 開機自啟：寫入 `HKCU\...\CurrentVersion\Run`，以 `--silent` 啟動到托盤；可在設定關閉。
- 開機後若有啟用中的網路規則，自動重新套用。

## 10. 設定（齒輪對話框）

- 預設 distro 目錄、備份目錄。
- 開機自啟、關窗縮托盤。
- 狀態輪詢間隔（預設 10 秒）。
- 主題：跟隨系統／深色／淺色。
- 進階模式：顯示實際執行的命令（預設關閉）。
- 系統 instance 清單（進階）。

## 11. 日誌

- 主頁底部可折疊抽屜，預設收起。
- 發生錯誤自動展開，顯示完整命令與 stderr，附「複製」按鈕。
- 日誌同時寫入 `logs/wsl-deck.log`。

## 12. 視覺與語言

- 繁體中文介面。
- 主題可切換；卡片狀態以左側色條表示（綠／灰），預設 instance 小星標。
- 視窗最小 900×600；卡片以網格排列，隨視窗寬度換行。

## 13. 不在 MVP（下一批）

- 遷移／壓縮 VHDX、任務排程、USB（usbipd-win）、`.wslconfig` 圖形化、SSH 遠端、Docker 映像來源、批次多選操作。

## 14. 技術架構

- Python 3.14 + PySide6-Essentials 6.12，安裝於專案 `.venv`（不影響全局）。
- 模組：

```
wsl-deck/
  main.py
  config.json
  app/
    config.py        # 偏好、規則、命令模板
    wsl.py           # wsl.exe、註冊表、狀態/IP
    network.py       # portproxy、防火牆、端口掃描
    admin.py         # runas 提權批次
    logbus.py
    ui/
      main_window.py     # 卡片牆、頂部列、日誌抽屜
      instance_card.py   # 單張卡片
      detail_page.py     # 詳情頁
      wizard.py          # 新增三步精靈
      backup_dialogs.py  # 備份/還原/複製/刪除
      settings_dialog.py
      tray.py
      progress.py        # 模態進度框
  tests/
```

- 背景工作用 `QThreadPool`；UI 以 signal 更新。
- 所有 WSL 呼叫集中於 `wsl.py`／`network.py`，UI 不直接拼命令。

## 15. 關鍵命令對照

| 操作 | 命令／API |
|------|-----------|
| 列表 | `wsl.exe -l -v` + `HKCU\...\Lxss`（BasePath、預設 GUID） |
| 啟動 | `wsl.exe -d <name> -- true` |
| 終止 | `wsl.exe --terminate <name>` |
| 全部關機 | `wsl.exe --shutdown` |
| 設預設 | `wsl.exe --set-default <name>` |
| 註銷 | `wsl.exe --unregister <name>` |
| 匯入 tar／vhd | `wsl.exe --import <name> <dir> <file> --version <v> [--vhd]` |
| 匯出 tar／vhd | `wsl.exe --export <name> <file> [--vhd]` |
| 官方安裝 | `wsl.exe --install -d <name> --location <dir>` |
| 線上清單 | `wsl.exe --list --online` |
| distro IP | `wsl.exe -d <name> -- hostname -I` |
| 端口掃描 | `wsl.exe -d <name> -- sh -c "ss -tln 2>/dev/null || netstat -tln"` |
| 端口轉發 | `netsh interface portproxy add/delete/show v4tov4` |
| 防火牆 | `netsh advfirewall firewall add/delete rule name="WSL Deck <name> <port>" dir=in action=allow protocol=TCP localport=<port> profile=private remoteip=localsubnet` |

## 16. 里程碑

| 里程碑 | 內容 | 驗收 |
|--------|------|------|
| M1（已完成） | 骨架、config、資料層、基礎列表 | 能列出 4 個 instance；測試通過 |
| M2 | 卡片牆、詳情頁導航、啟停/終端/兩個資料夾、系統 instance 禁用、自動輪詢 | 卡片狀態正確；點圖標不跳頁；docker-desktop 不可操作 |
| M3 | 新增三步精靈（三來源）、備份/還原/複製/刪除 | 用 `ubuntu.vhdx` 3 步新增；備份還原往返成功；刪除有雙重保護 |
| M4 | 網路規則 CRUD、掃描、UAC 批次、重套 | 8080→80 規則可用；LAN 另一台可訪問；重開機後自啟重套有效 |
| M5 | 托盤、自啟、設定、主題、日誌抽屜、onedir 打包 | 關窗縮托盤；開機進托盤；設定持久化；產出資料夾＋exe |

每個里程碑完成後回報並等待確認。

## 17. MVP 驗收標準

1. 用 `backups\ubuntu\ubuntu.vhdx` 新增 instance，不輸入命令、不查文檔，3 步內完成。
2. 外部終端啟動/停止 instance，10 秒內卡片狀態更新。
3. 詳情頁新增「8080 → 80」規則，只跳一次 UAC；同一局域網另一台裝置可訪問。
4. 重開機後自啟 App 自動重套規則，LAN 訪問仍有效。
5. 備份 `node22` → 修改內容 → 覆蓋式還原，回到備份時狀態；還原前自動備份了現況。
6. 刪除必須輸入名稱且預設先備份；取消備份後才能直接刪。

## 18. 風險與對策

- `--install --location` 依 WSL 版本而異（本機 3.0.3.0 支援）；失敗時引導改用 `--move`。
- VHDX 匯入是否複製檔案需在 M3 實測；還原流程一律先複製備份到安裝目錄，避免直接使用備份檔。
- 執行中匯出 VHDX 的一致性需實測；若失敗則要求先終止。
- 防火牆 `profile=private` 在 Public 網路上不生效；UI 需提示網路設定檔狀態。
- `wsl.exe` 輸出含空字元與本地化文字；解析以註冊表為主、CLI 狀態為輔。
- PyInstaller onedir 體積約 80–120MB；可接受，必要時再評估 Nuitka。
- 不複製 GPL 專案代碼，僅參考功能設計。

## 19. 已預設、可再改

- App 名稱暫定「WSL Deck」。
- 終端優先使用 Windows Terminal，找不到時退回 `wsl.exe`。
- 預設排序：預設 instance 最前，其餘名稱排序。
- 卡片不顯示版本與大小；大小與路徑在詳情頁。

## 20. M2.1 卡片改版（已確認）

依試用回饋調整：

- 移除卡片左側灰色豎紋（狀態色條），改為普通單一邊框。
- 卡片改為三行：第一行圖標（左上愛心標識／系統禁用標識、右上啟動/終止與終端）、第二行置中名稱、第三行按鈕；愛心與禁止標識同為 18×18 繪製圖標，大小與位置一致。
- 名稱置中、放大（18pt；名稱超過 10 字元時縮為 14pt）。
- 右上角為啟動/終止與終端兩個方形圖標按鈕（26×26）；啟動圖標為綠色、停止圖標為紅色；按鈕邊框顏色不隨狀態改變。
- 不再顯示狀態文字：以啟動/終止圖標本身表示狀態（綠=可啟動、紅=可終止）。
- 卡片底部置中兩顆大按鈕：Linux 檔案、安裝目錄；圖標與文字同一行，統一高度 40px、最小寬度 120px。
- 卡片高度 185px；名稱在圖標列下方再下移 30px，多餘高度留在名稱與按鈕之間；卡片與四顆按鈕都有邊框、背景與陰影。
- 卡片網格列間距固定 16px；多餘的垂直空間由底部空白列吸收，避免第一排與第二排被拉開。
- 系統 instance 在左上角顯示禁止標誌（僅作禁用提示，不改游標）；滑鼠懸停時說明「由 Docker Desktop 等上層工具管理，不提供操作」，四顆按鈕全部淡化禁用。
- 全域按鈕與詳情頁按鈕統一最小高度 32px。
- 所有按鈕啟用時顯示手型游標，禁用時顯示禁止游標。
- 右鍵選單不變（M3 才加入備份/還原/複製/刪除）。


