# WSL Deck 交接文檔 · 總覽

> 讀者：具備 Java 經驗、但不熟 Python 與 Qt 生態的接手人。
> 撰寫基準：2026-11-05，對應工作目錄 `d:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck`。
> 驗證聲明：本文所有「已實測」項目皆在本次交接中實際執行過；未實測項目會明確標註。
> 本套文件共 6 份，索引見文末。

---

## 1. 這個專案是什麼

**WSL Deck 是一個 Windows 桌面 GUI，用來管理 WSL（Windows Subsystem for Linux）的多個 Linux 發行版實例。**

它把散落在命令列的 `wsl.exe` 操作，包成一個可視化工具：

| 能力 | 對應的底層 | 入口 |
|------|-----------|------|
| 列出／啟停實例、看 IP 與磁碟大小 | `wsl.exe --list --verbose`＋註冊表 | 卡片牆／表格 |
| 新增實例（官方線上、tar/rootfs、VHDX） | `wsl --install`／`wsl --import` | 三步精靈 |
| 備份／還原／複製／刪除 | `wsl --export`／`--import`／`--unregister` | 詳情頁 |
| 增量快照（去重、按策略清理、校驗、單路徑還原） | restic（Linux 靜態二進位，首次使用時下載） | 詳情頁 → 快照 |
| 改寫 `/etc/wsl.conf`、設定預設使用者／systemd | `wsl -u root -- sh -c` | Instance 設定 |
| Windows 端口轉發＋防火牆 | `netsh portproxy`／`netsh advfirewall`（需 UAC） | 詳情頁 → 網路規則 |
| 托盤常駐、開機自啟、深淺主題 | `QSystemTrayIcon`／`HKCU\...\Run`／Qt palette | 托盤／設定 |

### 非目標（刻意不做）

- 不管理 Docker Desktop 自身的生命週期；`docker-desktop*` 這類系統實例只顯示、全部操作禁用。
- 不做差異式（diff）還原，還原一律是「先備份現況 → 註銷 → 重新匯入」的覆蓋式流程。
- 不內建 SSH／檔案傳輸，只用 `explorer.exe` 與 `wt.exe` 開啟外部程式。
- 不支援 Linux／macOS；程式大量依賴 `winreg`、`netsh`、`powershell.exe`。

---

## 2. 一頁速覽

| 項目 | 事實 |
|------|------|
| GUI 框架 | PySide6-Essentials（Qt 6 官方 Python 綁定），只用 QtCore／QtGui／QtWidgets／QtNetwork |
| Python | 3.14.2（`.venv` 實測）；原始碼用 `from __future__ import annotations` 與 `X \| None` 語法 |
| 執行時依賴 | 只有一個：`PySide6-Essentials==6.12.0`（[requirements.txt](../../wsl-deck/requirements.txt)） |
| 開發期依賴 | `pyinstaller==6.22.3`（[requirements-dev.txt](../../wsl-deck/requirements-dev.txt)） |
| 程式規模 | `app/`＋`main.py`＋`tests/` 共 9,593 行 Python |
| 單元測試 | 135 項，`unittest`，約 1 秒跑完，全部通過（本次已實測） |
| 外部進程 | `wsl.exe`、`netsh`、`powershell.exe`、`curl.exe`、`fsutil`、`explorer.exe`、`wt.exe`、restic |
| 打包形態 | PyInstaller onedir → `dist\WSL Deck\WSL Deck.exe`；再用 Inno Setup 出安裝包、或用 PowerShell 出 zip |
| 設定檔 | 執行目錄下的 `config.json`（開發期＝應用根目錄；打包後＝exe 同層） |
| 日誌 | `logs/wsl-deck.log`（相對 `config.json` 所在目錄），同時鏡射到底部「日誌」抽屜 |
| 版本號 | 唯一來源是 [installer/WSL Deck.iss](../../wsl-deck/installer/WSL%20Deck.iss) 的 `#define MyAppVersion` |

> **注意**：倉庫內的 `config.json` 目前把 `workspace_root` 指向 `D:\VirtualMachiles\wsl`，這是舊路徑。它已被 `.gitignore` 忽略，屬於本機狀態而非程式碼；接手後應在「設定」對話框改成自己的路徑。

---

## 3. 五分鐘跑起來

以下命令都在**應用根目錄** `wsl-deck\wsl-deck` 執行（PowerShell）。

### 3.1 確認環境

```powershell
.\.venv\Scripts\python.exe -V                # 應顯示 Python 3.14.2
.\.venv\Scripts\python.exe -c "import PySide6; print(PySide6.__version__)"   # 應顯示 6.12.0
```

若 `.venv` 不存在（例如換機器），重建方式見 [03-build-release.md](./03-build-release.md#1-開發環境)。

### 3.2 跑測試（已實測，約 1 秒）

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
# 實測輸出：Ran 135 tests in 1.032s / OK
```

測試全程使用 mock，不會呼叫真實 `wsl.exe`、不碰註冊表、不觸發 UAC。

### 3.3 啟動 GUI（已實測，但需由你手動啟動）

```powershell
.\.venv\Scripts\pythonw.exe main.py
```

- 用 `pythonw.exe` 而非 `python.exe`，才不會多出一個黑色主控台視窗。
- 若從 AI 工具／CI 的沙箱命令啟動，GUI 子進程會在命令結束時被回收，看起來像「視窗沒出現」。這是啟動方式的問題，不是程式 bug。
- 應用根目錄另有 `WSL Deck.lnk` 開發期捷徑（`.lnk` 被 git 忽略）。

### 3.4 看日誌

```powershell
Get-Content .\logs\wsl-deck.log -Tail 50
```

UI 底部「日誌」抽屜顯示的是同一份日誌（時間只到秒，格式 `HH:MM:SS 訊息`），錯誤會自動展開抽屜。

---

## 4. 目錄地圖

```
wsl-deck\                     ← git 倉庫根（plans/、docs/、.git 在此）
├── plans/                    ← 開發歷程文件（需求、里程碑、修補計畫）
├── docs\handover\            ← 本套交接文件
└── wsl-deck\                 ← 應用根目錄（以下所有命令都在這裡執行）
    ├── main.py               ← 唯一入口；處理 --silent 與 --admin-job
    ├── requirements.txt      ← 執行時依賴（只有 PySide6）
    ├── requirements-dev.txt  ← 打包依賴（PyInstaller）
    ├── config.json           ← 本機設定（git 忽略）
    ├── WSL Deck.spec         ← PyInstaller 設定
    ├── build.ps1             ← 出 onedir 產物
    ├── build-installer.ps1   ← 出 Inno Setup 安裝包
    ├── build-zip.ps1         ← 出免安裝 zip
    ├── assets\               ← 圖示（wsl-deck-icon.ico）
    ├── installer\            ← Inno Setup 腳本
    ├── app\                  ← 業務層（見 02-architecture）
    │   ├── config.py         ← 設定讀寫、命令模板、遷移與校驗
    │   ├── wsl.py            ← 實例清單、啟停、IP、註冊表
    │   ├── distro_ops.py     ← 新增／備份／還原／複製／刪除
    │   ├── distro_settings.py← /etc/wsl.conf、代理腳本、VHD 維護
    │   ├── snapshot.py       ← restic 增量快照
    │   ├── network.py        ← 端口規則、掃描、套用編排
    │   ├── admin.py          ← 提權批次（netsh）
    │   ├── proxy.py          ← 全域代理環境變數
    │   ├── workspace.py      ← 工作目錄骨架
    │   ├── paths.py          ← 可寫路徑（開發期／凍結後）
    │   ├── autostart.py      ← 開機自啟（只支援 exe）
    │   ├── single_instance.py← 單實例鎖＋喚醒管道
    │   ├── logbus.py         ← logging → UI
    │   ├── shell.py          ← 開終端／資料夾
    │   └── ui\               ← 表現層（Qt 元件）
    ├── tests\                ← 13 個測試檔、135 項
    ├── logs\                 ← 執行時日誌（git 忽略）
    ├── build\ dist\          ← 建置產物（git 忽略）
    └── .venv\                ← 虛擬環境（git 忽略）
```

---

## 5. 三條閱讀路徑

| 你的目的 | 先讀 | 再讀 |
|---------|------|------|
| 只改 UI（版面、顏色、按鈕） | 本文第 4 節 + [02-architecture.md](./02-architecture.md#32-表現層-appui) | [01-python-primer.md](./01-python-primer.md#5-qt-心智模型)（Qt 部分） |
| 只改 WSL 業務邏輯 | [02-architecture.md](./02-architecture.md#31-業務層-app) | [05-risks-conventions.md](./05-risks-conventions.md)（破壞性操作） |
| 只想打包發布 | [03-build-release.md](./03-build-release.md) | [04-troubleshooting.md](./04-troubleshooting.md#5-打包類) |
| 全面接手 | 本文 → 02 → 01 → 03 → 04 → 05 | — |

---

## 6. 術語表

| 術語 | 含義（本專案語境） |
|------|------------------|
| **instance／distro** | 一個已註冊的 WSL 發行版實例。程式內幾乎都用 `distro`，UI 文案用「instance」。 |
| **rootfs／tar** | 匯出的 Linux 根檔案系統壓縮檔，`wsl --export` 產生、`wsl --import` 讀入。 |
| **VHDX** | WSL2 的虛擬磁碟檔（通常是 `ext4.vhdx`），效能好但匯出時必須先 `wsl --shutdown`。 |
| **portproxy** | Windows 的 `netsh interface portproxy` 端口轉發，把 `0.0.0.0:<windows_port>` 指向實例 IP。 |
| **restic** | 去重式備份工具。本專案下載 Linux 靜態二進位，放進 `snapshots\_tools\`，透過 `wsl -d <name> -u root -- <binary>` 執行。 |
| **快照（snapshot）** | restic 的一次增量備份，存於 `snapshots\<name>\repo`，密碼檔在同層 `repo.pass`。 |
| **系統 instance** | 名稱以 `docker-desktop` 開頭（可在設定擴充）的實例，UI 顯示但全部操作禁用。 |
| **提權／UAC** | `admin.py` 用 PowerShell `Start-Process -Verb RunAs` 啟動自身的第二個進程，批次執行 netsh，一次授權完成所有變更。 |
| **Signal／Slot** | Qt 的事件機制，等價於 Java 的監聽器／事件匯流排，但型別安全且可跨執行緒排隊。 |
| **QRunnable／QThreadPool** | Qt 的工作單元與執行緒池，等價於 `ExecutorService`＋`Runnable`。 |
| **QSS** | Qt 樣式表，語法近似 CSS；本專案常用 `palette(base)`、`palette(mid)` 讓深淺主題自動生效。 |
| **凍結（frozen）** | PyInstaller 打包後的執行狀態，`sys.frozen == True`、`sys.executable` 指向 exe。 |

---

## 7. 交接 checklist

### 環境

- [ ] `.venv` 可重建，`python -V` 為 3.14.x，PySide6 為 6.12.0
- [ ] `python -m unittest discover -s tests -q` 為 `Ran 135 tests / OK`
- [ ] 手動雙擊 `.lnk` 或執行 `pythonw main.py`，視窗能出現
- [ ] 「設定」→ 工作目錄改成本機路徑，並按「套用工作目錄骨架」
- [ ] 確認 `logs\wsl-deck.log` 有內容

### 未驗收／未完成（截至本次交接）

- [ ] 詳情頁「快照」整條流程（建立／還原檔案／清理／校驗）**尚未由真人點擊驗收**
- [ ] 打包產物（onedir／安裝包／zip）**本次未實跑**，只做靜態核對
- [ ] 跨裝置 LAN 驗收需把網路設定檔改成 Private（見 [04-troubleshooting.md](./04-troubleshooting.md#4-網路與防火牆類)）

### 資料安全

- [ ] `config.json`、`instances/`、`backups/`、`snapshots/` 都不進版控，確認你的備份策略
- [ ] `snapshots\<name>\repo.pass` 是明文密碼檔，不要外流

---

## 8. 文件索引

| 文件 | 內容 |
|------|------|
| **00-overview.md**（本文） | 定位、速覽、啟動、目錄、術語、checklist |
| [01-python-primer.md](./01-python-primer.md) | 給 Java 底子的 Python／Qt 速成，每條都對應本專案真實程式碼 |
| [02-architecture.md](./02-architecture.md) | 分層、模組職責、啟動／輪詢／提權三條主鏈、資料與設定模型、擴充點 |
| [03-build-release.md](./03-build-release.md) | 開發環境、測試、PyInstaller、Inno Setup、zip、版本號、凍結前後差異 |
| [04-troubleshooting.md](./04-troubleshooting.md) | 按現象分組的排障表，每條可追回程式碼位置 |
| [05-risks-conventions.md](./05-risks-conventions.md) | 破壞性操作、權限模型、技術債分級、AI 產碼特徵、編碼約定 |
