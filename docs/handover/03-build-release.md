# 構建與發布

> 本文說明「從乾淨機器到可交付安裝包」的完整鏈路。
> **驗證聲明**：本節的命令本次只做了靜態核對與版本確認（PyInstaller 6.22.3 已安裝、`dist/` 內有既有產物）；**沒有重新執行** `build.ps1`／`build-installer.ps1`／`build-zip.ps1`。文中標「未實測」者請自行驗證。

---

## 1. 開發環境

### 1.1 版本基線

| 項目 | 值 | 來源 |
|------|----|------|
| Python | 3.14.2 | `.venv` 實測 |
| PySide6-Essentials | 6.12.0 | [requirements.txt](../../wsl-deck/requirements.txt)，實測 `PySide6.__version__` |
| PyInstaller | 6.22.3 | [requirements-dev.txt](../../wsl-deck/requirements-dev.txt)，實測 `python -m PyInstaller --version` |
| Inno Setup | 6.x | [build-installer.ps1](../../wsl-deck/build-installer.ps1) 會找 `ISCC.exe` |

本專案**沒有** `pyproject.toml`／`setup.py`／`Pipfile`。依賴只有兩份 `requirements*.txt`，這是刻意的：它是應用不是套件。

### 1.2 從零建立 `.venv`

```powershell
cd d:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

驗證：

```powershell
.\.venv\Scripts\python.exe -V                                   # Python 3.14.2
.\.venv\Scripts\python.exe -m PyInstaller --version              # 6.22.3
.\.venv\Scripts\python.exe -c "import PySide6; print(PySide6.__version__)"   # 6.12.0
```

> `.venv/` 被 [.gitignore](../../.gitignore) 忽略（第 19 行）。換機器一定要重建，不能直接複製——venv 內含絕對路徑。

### 1.3 不需要 `activate`

本專案所有腳本都寫死 `.venv\Scripts\python.exe`。原因：`activate` 只影響當前 shell session，一旦切到 IDE／CI／AI 工具就會失效。直接呼叫絕對路徑最穩。

---

## 2. 開發期執行與測試

```powershell
# 執行測試（已實測：Ran 135 tests / OK）
.\.venv\Scripts\python.exe -m unittest discover -s tests -q

# 啟動 GUI（用 pythonw 才不會多出主控台視窗）
.\.venv\Scripts\pythonw.exe main.py
```

| 差異 | `python.exe` | `pythonw.exe` |
|------|-------------|--------------|
| 主控台視窗 | 有 | 無 |
| stdout／stderr | 可見 | 丟棄（所以 `print` 除錯會看不到） |
| 用途 | 跑測試、CLI 除錯 | 啟動 GUI |

`main.py` 支援兩個參數（[main.py:12-18](../../wsl-deck/main.py#L12-L18)）：

| 參數 | 用途 |
|------|------|
| `--silent` | 開機自啟用；有托盤時不顯示主視窗，直接常駐 |
| `--admin-job <job.json> <result.json>` | **內部使用**，提權子進程的入口；一般不要手動呼叫 |

---

## 3. PyInstaller onedir

### 3.1 spec 逐欄位解讀

[WSL Deck.spec](../../wsl-deck/WSL%20Deck.spec)：

| 欄位 | 值 | 為什麼 |
|------|----|--------|
| `Analysis(["main.py"])` | 唯一入口 | 所有模組由 import 關係自動收集 |
| `datas=[("assets/wsl-deck-icon.ico", "assets")]` | 圖示 | 執行期由 `app_icon.asset_path()` 從 `_MEIPASS/assets` 讀取 |
| `hiddenimports=["app.admin"]` | 手動補 | `app.admin` 只在 `--admin-job` 分支被匯入（[main.py:13-15](../../wsl-deck/main.py#L13-L15)），明列可確保它一定進包 |
| `EXE(..., name="WSL Deck", console=False, icon=...)` | 無主控台 | 等價於 `pythonw`；`console=False` 是 GUI 應用必須 |
| `COLLECT(..., name="WSL Deck")` | onedir | 產生 `dist\WSL Deck\` 資料夾，不是單檔 |

`upx=False`：UPX 壓縮常讓 Qt DLL 載入失敗，關掉是對的。

### 3.2 build.ps1 的做法

[build.ps1](../../wsl-deck/build.ps1) 只做四件事：

1. 呼叫 `python -m PyInstaller --noconfirm --clean --workpath build --distpath dist "WSL Deck.spec"`（[build.ps1:11-15](../../wsl-deck/build.ps1#L11-L15)）
2. 把 stderr 導到 `build/pyinstaller.log`
3. 檢查 `dist\WSL Deck\WSL Deck.exe` 存在
4. 若 `dist\WSL Deck\config.json` 不存在，就複製應用根目錄的 `config.json`（[build.ps1:29-32](../../wsl-deck/build.ps1#L29-L32)）

**為什麼第 8-18 行要把 `$ErrorActionPreference` 改成 `Continue`**：PowerShell 5.1 會把原生命令寫到 stderr 的內容當成「終止錯誤」，PyInstaller 的進度輸出正好走 stderr，直接跑會被誤判為失敗。改成 `Continue` + 收集 exit code 才是正確做法。

```powershell
.\build.ps1
```

產物：

```
dist\
└── WSL Deck\
    ├── WSL Deck.exe          ← 啟動器
    ├── config.json           ← 首次建置時從應用根目錄複製
    ├── _internal\            ← Python 直譯器、標準庫、PySide6、Qt DLL
    └── ...
```

> **風險（重要）**：第 4 步會把**開發者本機的 `config.json`** 一起打包。目前該檔的 `workspace_root` 是 `D:\VirtualMachiles\wsl`，而 `DEFAULT_CONFIG` 的預設值也是同一個路徑（[config.py:35](../../wsl-deck/app/config.py#L35)）。這代表**新使用者首次啟動時，預設工作目錄會指向一個他電腦上不存在的路徑**。發布前務必確認 `config.json` 內容，或直接刪掉它讓程式生成預設值（見 [05-risks-conventions.md](./05-risks-conventions.md#4-技術債分級)）。

### 3.3 打包後的路徑變化

| 函式 | 開發期 | 凍結後 |
|------|--------|--------|
| `app_dir()`（[paths.py:13-17](../../wsl-deck/app/paths.py#L13-L17)） | 應用根目錄 | `WSL Deck.exe` 所在資料夾 |
| `config.json` | 應用根目錄 | exe 同層 |
| `logs\wsl-deck.log` | 應用根目錄下 | exe 同層下 |
| `asset_path()`（[app_icon.py:17-20](../../wsl-deck/app/ui/app_icon.py#L17-L20)） | `assets/` | `sys._MEIPASS/assets`（即 `_internal/assets`） |

---

## 4. Inno Setup 安裝包

### 4.1 iss 關鍵設定

[installer/WSL Deck.iss](../../wsl-deck/installer/WSL%20Deck.iss)：

| 設定 | 值 | 含義 |
|------|----|------|
| `MyAppVersion` | `1.0.0` | **全專案版本號唯一來源**（[WSL Deck.iss:5](../../wsl-deck/installer/WSL%20Deck.iss#L5)） |
| `AppId` | `{4447AF87-...}` | 升級識別碼；**改了會變成另一個產品**，不要動 |
| `PrivilegesRequired=lowest` | 低權限 | 安裝到 `{localappdata}\Programs`，不需要管理員 |
| `ArchitecturesAllowed=x64compatible` | 64 位 | 與 Qt／PySide6 的 wheel 一致 |
| `MinVersion=10.0` | Windows 10+ | WSL2 的前提 |
| `Compression=lzma2/ultra64` | 高壓縮 | 安裝包約 29 MB（既有產物實測） |
| `OutputDir=..\dist` | 輸出到 dist | 與 zip、onedir 同層 |
| `OutputBaseFilename=WSL-Deck-Setup-{#MyAppVersion}` | 檔名帶版本 | 免安裝 zip 的命名規則對齊它 |
| `VersionInfoVersion={#MyAppVersion}` | exe 檔案內容的版本資訊 | — |

### 4.2 檔案佈局與 `config.json` 的特殊處理

```ini
[Files]
Source: "..\dist\WSL Deck\*"; DestDir: "{app}"; Excludes: "config.json,logs\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\WSL Deck\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
```

- 第一行安裝**全部檔案但排除** `config.json` 與 `logs\*`：升級時不會覆蓋使用者的設定與日誌。
- 第二行再單獨安裝 `config.json`，且 `onlyifdoesntexist`：只有全新安裝才寫入。
- `[UninstallDelete]` 只刪 `{app}\logs`，**不刪** `instances`／`backups`／`snapshots`（那些在工作目錄，不在安裝目錄）。

### 4.3 build-installer.ps1

[build-installer.ps1](../../wsl-deck/build-installer.ps1) 依序找三個位置的 `ISCC.exe`（[build-installer.ps1:3-11](../../wsl-deck/build-installer.ps1#L3-L11)）：

1. `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`
2. `C:\Program Files\Inno Setup 6\ISCC.exe`
3. `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

```powershell
.\build.ps1             # 先出 onedir
.\build-installer.ps1   # 再出安裝包
```

> **已知 bug（未修）**：[build-installer.ps1:15](../../wsl-deck/build-installer.ps1#L15) 把檢查路徑寫死成 `dist\WSL-Deck-Setup-1.0.0.exe`。一旦 `MyAppVersion` 改成 `1.1.0`，安裝包會正確產出，但腳本會因為找不到 `1.0.0` 而報「建置失敗」。升版時要一起改這一行（見第 6 節）。

---

## 5. 免安裝 zip

[build-zip.ps1](../../wsl-deck/build-zip.ps1)：

```powershell
.\build-zip.ps1                  # 版本讀自 iss，排除 config.json 與 logs
.\build-zip.ps1 -IncludeConfig   # 連 config.json 一起打包
.\build-zip.ps1 -Version 1.1.0   # 臨時指定版本號（不改 iss）
```

流程（[build-zip.ps1:33-54](../../wsl-deck/build-zip.ps1#L33-L54)）：

1. 版本號：`-Version` > iss 的 `MyAppVersion` > 保底 `1.0.0`
2. 日期戳：`yyyyMMdd`
3. 輸出：`dist\WSL-Deck-<version>-<yyyyMMdd>.zip`
4. 先複製到 `build\zip-stage\WSL Deck\`，刪掉 `logs\`，預設刪掉 `config.json`，再壓縮，最後清掉 stage

**為什麼預設排除 `config.json`**：避免把開發者的本機路徑帶給使用者；程式首次啟動會用 `DEFAULT_CONFIG` 生成一份。但如前所述，`DEFAULT_CONFIG` 的 `workspace_root` 目前也是開發機路徑，所以「排除」並沒有真正解決問題，只是把問題延後到首次啟動。

既有產物：`dist\WSL-Deck-1.0.0-20261105.zip`（約 41.4 MB，本次僅列出、未重建）。

---

## 6. 版本號與升版步驟

版本號只有一處：#define MyAppVersion "1.0.0"（[WSL Deck.iss:5](../../wsl-deck/installer/WSL%20Deck.iss#L5)）。`build-zip.ps1` 會自動讀它，`build.ps1` 不涉及版本。

升版 checklist：

1. 改 [WSL Deck.iss:5](../../wsl-deck/installer/WSL%20Deck.iss#L5) 的 `MyAppVersion`
2. 改 [build-installer.ps1:15](../../wsl-deck/build-installer.ps1#L15) 的硬編碼檢查路徑（否則腳本會誤報失敗）
3. `.\build.ps1`
4. `.\build-installer.ps1`
5. `.\build-zip.ps1`
6. 確認 `dist\` 下三個產物版本一致
7. 在乾淨機器（或新建使用者設定檔）實測安裝與啟動

> 程式本身**不讀版本號**（沒有 `__version__`），UI 也不顯示版本。所以版本只影響檔名與檔案內容資訊。

---

## 7. 凍結前後的行為差異（改程式前必看）

| 行為 | 開發期 | 凍結後 | 程式位置 |
|------|--------|--------|---------|
| 可寫目錄 | 應用根目錄 | exe 同層 | [paths.py:13-17](../../wsl-deck/app/paths.py#L13-L17) |
| 開機自啟 | **不支援**（`is_supported()` 回 False） | 寫 `HKCU\...\Run` | [autostart.py:16-33](../../wsl-deck/app/autostart.py#L16-L33) |
| 提權子進程命令 | `python.exe -m app.admin` | `WSL Deck.exe --admin-job` | [admin.py:135-141](../../wsl-deck/app/admin.py#L135-L141) |
| 提權子進程工作目錄 | 應用根目錄 | exe 同層 | [admin.py:139-141](../../wsl-deck/app/admin.py#L139-L141) |
| 圖示資源 | `assets/` | `_internal/assets`（`sys._MEIPASS`） | [app_icon.py:17-20](../../wsl-deck/app/ui/app_icon.py#L17-L20) |
| `sys.executable` | python.exe 路徑 | exe 路徑 | 標準庫 |

**最容易被忽略的一條**：如果你改了 `--admin-job` 這個參數名，[main.py:13](../../wsl-deck/main.py#L13) 與 [admin.py:139](../../wsl-deck/app/admin.py#L139) 必須同步改，而且**只有打包後才會踩到**——開發期走的是 `-m app.admin` 分支，測試不會發現。

---

## 8. 發布 checklist

- [ ] 測試通過：`Ran 135 tests / OK`
- [ ] `config.json` 內容已確認（不要把開發機的 `workspace_root` 帶出去）
- [ ] 版本號在 iss 與 build-installer.ps1 兩處一致
- [ ] `.\build.ps1` 成功，`dist\WSL Deck\WSL Deck.exe` 存在
- [ ] `.\build-installer.ps1` 成功，安裝包大小合理（約 29 MB）
- [ ] `.\build-zip.ps1` 成功，zip 大小合理（約 41 MB）
- [ ] 在**乾淨環境**（另一個使用者設定檔或 VM）測試：
  - [ ] 安裝後可啟動、工作目錄可設定
  - [ ] 開機自啟可勾選（`is_supported()` 只在凍結後為真）
  - [ ] 網路規則「立即套用」能跳一次 UAC 並成功
  - [ ] 卸載後 `{app}\logs` 被清掉，`instances/backups/snapshots` 保留

---

## 9. 本次交接的驗證範圍

| 項目 | 狀態 |
|------|------|
| `.venv` 版本（Python 3.14.2、PySide6 6.12.0） | 已實測 |
| PyInstaller 6.22.3 已安裝 | 已實測 |
| 135 項 unittest | 已實測 |
| `dist/` 既有產物存在（1.0.0 exe／zip） | 已實測（僅列檔，未重建） |
| `build.ps1` / `build-installer.ps1` / `build-zip.ps1` | **未實測**（靜態核對） |
| GUI 啟動與安裝流程 | **未實測**（需真人操作） |
