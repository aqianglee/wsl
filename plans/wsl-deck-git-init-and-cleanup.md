# 計畫：建立本地 Git 倉庫 + 清理安全備份

> 目標：在 `D:\VirtualMachiles\wsl` 建立可回滾的本地 git 倉庫（只納入原始碼與計畫文件），並刪除 M5–M7 期間為「改壞可回滾」而產生的**程式碼快照**。依使用者確認：**只刪程式碼備份，保留所有執行個體（VM）備份與快照**。

## 1. 現狀盤點

### 1.1 倉庫狀態
- `D:\VirtualMachiles\wsl` 目前**不是** git 倉庫；全工作區無任何 `.gitignore`。
- git 版本 `2.43.0.windows.1`；全域 `user.name` / `user.email` **未設定**（直接 commit 會失敗）。

### 1.2 備份與快照（判定）

| 項目 | 內容 | 大小 | 判定 |
| --- | --- | --- | --- |
| `backups\ubuntu\ubuntu.vhdx` | 2023 年的 Ubuntu 20.04 匯入來源映像，`plans\wsl-mysql-tomcat-acceptance.md`、`wsl-deck-mvp.md` 的驗收流程直接依賴 | 2.51 GB | **保留**（不是安全備份，是測試素材） |
| `backups\Ubuntu-26.04\Ubuntu-26.04-20261103-180708.vhdx` | M6 測試前的整機備份 | 2.26 GB | **保留**（執行個體備份，依確認不刪） |
| `backups\wsl-mysql\wsl-mysql-20261104-114610.tar` | 今日 11:46 的整機 TAR 備份 | 1.35 GB | **保留**（執行個體備份，依確認不刪） |
| `backups\_tmp\` | 空目錄 | 0 | **保留**（非程式碼備份） |
| `wsl-mysql\Ubuntu-26.04-20261103-180708.vhdx` | `wsl-mysql` 現役 instance 磁碟 | 2.45 GB | **保留**（執行中的 instance） |
| `_m5-snapshots\` | M5 動工前程式快照（app/tests/config） | 0.5 MB | **刪除** |
| `_m6-snapshots\` | M6 動工前程式快照 | 0.5 MB | **刪除** |
| `wsl-deck\_m7-snapshots\` | M7 動工前程式快照（含 SHA256SUMS） | 0.1 MB | **刪除** |
| `wsl-deck\config.json.pre-m5.bak` | M5 配置遷移的一次性備份（程式自動產生） | 1 KB | **刪除**（config 已完成遷移，不會再被引用） |
| `snapshots\Ubuntu-26.04\`（`repo\` + `repo.pass`） | M7 驗證留下的 restic 測試倉庫（2 份測試快照） | 0.5 GB | **保留**（執行個體快照，依確認不刪） |
| `snapshots\_tools\restic-linux-amd64` | App 快照功能的執行期依賴（首次自動下載） | 26 MB | **保留** |
| `%sn  ; done`（根目錄） | 先前 shell 誤產生的 0 byte 檔 | 0 | **保留**（非備份，不在本次範圍） |

合計釋放約 **1.1 MB**（僅程式碼快照）。

### 1.3 納入版控的內容
`wsl-deck\` 的 Python 原始碼、測試、安裝器腳本、計畫文件 `plans\*.md`。

## 2. 方案：在 `D:\VirtualMachiles\wsl` 建倉庫

理由：程式（`wsl-deck\`）與決策文件（`plans\`）屬於同一專案；在根目錄建單一倉庫可避免嵌套 repo，並用 `.gitignore` 擋掉 VM 磁碟與備份，不讓 40 GB 級二進位進版控。

### 2.1 `.gitignore` 內容（新建於根目錄）

```gitignore
# WSL 執行個體與虛擬磁碟（含整機備份）
/instances/
/backups/
/snapshots/
/ubuntu/
/node22/
/alms/
/Ubuntu-26.04/
/wsl-mysql/
*.vhdx
*.tar
*.tar.gz

# 動工前的程式快照（已清理，防止再被納入）
/_m*-snapshots/
/wsl-deck/_m*-snapshots/

# 開發產物與本機狀態
/wsl-deck/.venv/
/wsl-deck/build/
/wsl-deck/dist/
/wsl-deck/logs/
__pycache__/
*.pyc
/wsl-deck/config.json
/wsl-deck/config.json.*.bak
*.lnk
/.screenshots/
```

> `backups/ubuntu/ubuntu.vhdx` 與 `snapshots/_tools/` 因此不會被追蹤，但仍留在磁碟上供驗收與 App 執行使用。

### 2.2 追蹤白名單（`git add` 逐一指定，不用 `git add -A`）

- `plans\*.md`（18 份文件）
- `wsl-deck\app\`（含 `ui\`）
- `wsl-deck\tests\`
- `wsl-deck\installer\`（`WSL Deck.iss`、`make_app_icon.py`、`WSL Deck.ico`）
- `wsl-deck\main.py`、`build.ps1`、`build-installer.ps1`、`requirements.txt`、`requirements-dev.txt`、`WSL Deck.spec`

預期 tracked 檔案約 58 個、總量 < 1 MB。

## 3. 執行步驟

1. 新建根目錄 `.gitignore`（內容如 2.1）。
2. `git init -b main`（路徑 `D:\VirtualMachiles\wsl`）。
3. 依 2.2 白名單 `git add`，再 `git status --short` / `git diff --cached --stat` 確認不含二進位大檔。
4. 首次提交（不寫入 git config，採單次 `-c` 參數；身份依確認）：
   ```powershell
   git -c user.name="aqianglee" -c user.email="695182311@qq.com" commit -m "chore: 初始化本地倉庫（WSL Deck 原始碼與計畫文件）"
   ```
5. 驗證：`git log --oneline -1`、`git status`（clean）、`git ls-files | Measure-Object`。
6. 依 1.2 判定為「刪除」的程式碼快照（`_m5-snapshots`、`_m6-snapshots`、`wsl-deck\_m7-snapshots`、`config.json.pre-m5.bak`）逐項刪除，使用 DeleteFile 工具；每項刪除後確認 `Test-Path` 為 False。
7. 收尾驗證：`backups`、`snapshots` 內容完全未變（`ubuntu.vhdx`、`_tools`、restic 倉庫、TAR 備份都還在）。
8. `git status` 應仍為 clean（被刪項目都在 ignore 範圍）。

## 4. 風險與回滾

| 風險 | 處理 |
| --- | --- |
| 刪除不可逆 | 刪除前原始碼已由 git 首個 commit 完整保存；本次僅刪程式碼快照，執行個體備份一律不動 |
| 誤刪驗收素材 | 明確保留 `backups\` 全部內容（含 `ubuntu.vhdx`、整機備份、TAR）與 `snapshots\` 全部內容 |
| 誤把 VM 磁碟納入版控 | 以白名單 add + `.gitignore` 雙重保護，提交前檢查 `--stat` |
| commit 身份缺失 | 用單次 `-c user.name/user.email`（aqianglee / 695182311@qq.com），不修改全域或 repo config |
| `.gitignore` 規則失效 | 全部使用以 `/` 開頭的路徑規則（只匹配根目錄），實例目錄與備份目錄皆在根層，不會誤傷原始碼 |

回滾：若需還原程式碼，`git reset --hard HEAD` 即可回到提交時狀態；被刪備份本身不可回滾。

## 5. 驗證清單

- [ ] `git rev-parse --is-inside-work-tree` → `true`，預設分支 `main`
- [ ] `git ls-files` 不含 `*.vhdx`、`*.tar`、`config.json`、`*.lnk`
- [ ] `git status --porcelain` 為空
- [ ] `Test-Path` 對 4 個刪除項（`_m5-snapshots`、`_m6-snapshots`、`wsl-deck\_m7-snapshots`、`wsl-deck\config.json.pre-m5.bak`）回 `False`
- [ ] `backups` 與 `snapshots` 檔案數量、大小與清理前一致
- [ ] `wsl-deck\tests` 單元測試不受影響（可選執行 `python -m unittest discover -s tests -q`）

## 6. 已確認事項（2026-11-04）

- [x] 倉庫根目錄為 `D:\VirtualMachiles\wsl`，分支 `main`
- [x] 採用 `.gitignore` 與追蹤白名單
- [x] **只刪程式碼備份**；`backups\`、`snapshots\` 內所有執行個體備份與快照一律保留（含 1.35 GB wsl-mysql TAR）
- [x] 保留 `backups\ubuntu\ubuntu.vhdx`、`snapshots\_tools\`、`wsl-mysql\*.vhdx`
- [x] 以 `aqianglee <695182311@qq.com>` 身份提交（單次 `-c`，不寫 git config）
- [x] 首次提交訊息 `chore: 初始化本地倉庫（WSL Deck 原始碼與計畫文件）`

## 7. 執行結果（2026-11-04）

- 倉庫：`main` 分支，root commit `40335e7`，追蹤 79 個檔案（16,236 行）。
- 已刪除 4 項程式碼快照：`_m5-snapshots\`、`_m6-snapshots\`、`wsl-deck\_m7-snapshots\`、`wsl-deck\config.json.pre-m5.bak`。
- 執行個體備份與快照未變：`backups\` 3 個檔案 6,266 MB、`snapshots\` 42 個檔案 536 MB。
- `git status` 僅剩根目錄 `%sn  ; done`（0 byte 非備份垃圾檔，未納入版控）。
