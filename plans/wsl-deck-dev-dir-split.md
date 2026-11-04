# 計畫：拆分「執行工作目錄」與「開發目錄」

> 目標：把 `D:\VirtualMachiles\wsl` 還原成純執行工作目錄（只放 WSL 實例、整機備份、快照），把原始碼、文件與 git 倉庫搬到新的開發目錄。GitHub `https://github.com/aqianglee/wsl.git` 已是最終來源，遠端 `main` 與本地 `bf166f4` 一致。

## 1. 現狀盤點

### 1.1 Git
- `origin` 已設定為 `https://github.com/aqianglee/wsl.git`；遠端 `main` = 本地 `bf166f4`（已同步）。
- 本地工作區乾淨（無未提交變更）。

### 1.2 執行工作目錄資產（留在 `D:\VirtualMachiles\wsl`）

| 項目 | 內容 | 大小 |
| --- | --- | --- |
| `Ubuntu-26.04\`、`ubuntu\`、`node22\`、`alms\`、`wsl-mysql\` | 五個 WSL 實例磁碟（`ext4.vhdx`） | 約 47 GB |
| `instances\` | 預留實例目錄（空） | 0 |
| `backups\` | 整機備份（`ubuntu.vhdx`、M6 vhdx、wsl-mysql TAR） | 6.3 GB |
| `snapshots\` | restic 快照倉庫 + `_tools\restic-linux-amd64` | 536 MB |
| `.screenshots\` | 空目錄 | 0 |
| `%sn  ; done` | 0 byte 垃圾檔（非備份，不動） | 0 |

### 1.3 開發資產（要搬走）

| 項目 | 內容 | 大小 |
| --- | --- | --- |
| `.git\` | 本地倉庫（2 commits） | 小 |
| `.gitignore` | 版控排除規則 | 1 KB |
| `plans\` | 19 份計畫文件 | 小 |
| `wsl-deck\` | 原始碼、測試、安裝器、`config.json`（未追蹤）、`.venv`、`build`、`dist`、`logs` | 約 416 MB |

> `wsl-deck\config.json` 內 `workspace_root` / `backup_root` / `snapshot_root` 都是絕對路徑指向 `D:\VirtualMachiles\wsl`，搬移後仍有效，無需改設定。

## 2. 方案（建議）

### 2.1 新開發目錄
`D:\workspaces\workspace-wsl-deck\wsl-deck`（`workspace-wsl-deck` 為專案外層，`wsl-deck` 為 repo 根，與 `WSL Deck` 命名一致）。

### 2.2 搬移方式：整棵搬移（同磁碟，瞬間完成）
保留 `.venv`、`build`、`dist`、本機 `config.json`，不必重新安裝依賴；搬完驗證 venv 可用，異常才重建。

### 2.3 目錄職責
- 開發目錄：git 倉庫、`plans\`、`wsl-deck\`（原始碼 + `.venv` + `dist`）、`.gitignore`、`.screenshots\`。
- 執行工作目錄：五個 distro 目錄、`instances\`、`backups\`、`snapshots\`、0 byte 垃圾檔；**不再有 `.git` 與原始碼**。

## 3. 執行步驟

1. 確認 `D:\workspaces\workspace-wsl-deck` 不存在（避免覆蓋）。
2. 建立 `D:\workspaces\workspace-wsl-deck\wsl-deck`，將下列項目 `Move-Item` 過去：
   - `.git`、`.gitignore`、`plans`、`wsl-deck`、`.screenshots`
3. 驗證倉庫：
   - `git -C D:\workspaces\workspace-wsl-deck\wsl-deck status --short`（除未追蹤的本計畫文件外應為空）
   - `git -C D:\workspaces\workspace-wsl-deck\wsl-deck log --oneline -3`、`git remote -v`
4. 驗證虛擬環境：`D:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck\.venv\Scripts\python.exe -c "import PySide6"`；失敗則重建 `.venv` 並 `pip install -r requirements-dev.txt`。
5. 驗證測試：於 `wsl-deck` 執行 `python -m unittest discover -s tests -q`（預期 129 項全過）。
6. 更新 `.gitignore`：確認 `/wsl-deck/config.json`、`/wsl-deck/{build,dist,logs,/.venv}` 規則在新目錄仍適用（規則為相對根目錄，無需改動）。
7. 提交本計畫文件（開發目錄內）。
8. 驗證執行目錄：`D:\VirtualMachiles\wsl` 只剩 §1.2 資產；`Test-Path .git` 為 `False`。
9. 冒煙啟動：`D:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck\.venv\Scripts\python.exe main.py`，確認能讀到 `workspace_root` 的五個實例。

## 4. 風險與回滾

| 風險 | 處理 |
| --- | --- |
| 搬移時 App 正在執行造成檔案鎖定 | 搬移前檢查並關閉 WSL Deck；`Move-Item` 失敗即停止 |
| `.venv` 搬移後失效（內含絕對路徑腳本） | 以 `.venv\Scripts\python.exe -c "import PySide6"` 驗證；失敗改為重建 |
| 誤把 VM 磁碟搬走 | 只搬 §1.3 清單，distro 目錄與 `backups` / `snapshots` 原地不動 |
| 遠端不一致 | 搬移前 `git fetch` 確認 `origin/main` = `bf166f4` |
| 執行目錄失去 `config.json` | 開發目錄保有 `wsl-deck\config.json`，內容指向執行目錄絕對路徑 |

回滾：把 `.git`、`.gitignore`、`plans`、`wsl-deck`、`.screenshots` 移回 `D:\VirtualMachiles\wsl` 即可。

## 5. 驗證清單

- [ ] `D:\workspaces\workspace-wsl-deck\wsl-deck` 是 git 倉庫，`main` @ `bf166f4`（或含計畫文件的新提交）
- [ ] `git status` 乾淨（`.gitignore` 生效，`config.json` / `.venv` / `dist` 未被追蹤）
- [ ] `python -m unittest discover -s tests -q` 全過
- [ ] `D:\VirtualMachiles\wsl` 無 `.git`、`plans`、`wsl-deck`、`.gitignore`
- [ ] `backups` / `snapshots` / 五個 distro 目錄原封不動
- [ ] 從開發目錄啟動 App，能列出 5 個實例

## 6. 已確認事項（2026-11-04）

- [x] 新開發目錄 `D:\workspaces\workspace-wsl-deck\wsl-deck`（使用者指定，已正規化 `D;`/`desk` 拼寫）
- [x] 採用整棵搬移（保留 `.venv` / `dist`），不重新 clone
- [x] 本計畫文件提交並推送 GitHub

## 7. 執行結果（2026-11-04）

- 已搬移：`.git`、`.gitignore`、`plans`、`wsl-deck` 至 `D:\workspaces\workspace-wsl-deck\wsl-deck`；`.screenshots` 為空目錄，搬移前已不存在。
- 倉庫完整：`git fsck` 無錯、79 個追蹤檔案、`origin` 指向 GitHub、`main` 基於 `bf166f4`。
- 虛擬環境搬移後可用：PySide6 `6.12.0`（需求為 `PySide6-Essentials==6.12.0`，原計畫誤寫 PyQt6）。
- 單元測試：`129` 項全過（`python -m unittest discover -s tests -q`）。
- `config.json` 解析正確：`root=D:/VirtualMachiles/wsl`，`instances`／`backups`／`snapshots` 皆指向執行工作目錄。
- 執行工作目錄 `D:\VirtualMachiles\wsl` 現只含 5 個 distro 目錄、`instances`、`backups`、`snapshots`；`wsl --list` 仍列出 5 個自建實例。
