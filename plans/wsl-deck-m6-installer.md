# M6.3 計畫：制作標準安裝版（保留攜帶版）

> 狀態：**待確認**
> 上層文件：[wsl-deck-m6-proxy.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m6-proxy.md)
> 目標：在既有 `dist\WSL Deck` 攜帶版與 zip 之外，再產出一個 `WSL-Deck-Setup-1.0.0.exe` 安裝包，具備開始選單／桌面捷徑、Apps & Features 卸載項，且升級時保留使用者 `config.json`。

## 1. 已核實事實（2026-11-03）

| 項目 | 結論 |
|------|------|
| winget | `v1.29.380` 可用 |
| Inno Setup | winget 提供 `JRSoftware.InnoSetup 6.7.3`，本機尚未安裝 |
| 7-Zip | `C:\Program Files\7-Zip\7z.exe` 存在（僅作備援，不使用） |
| 既有產物 | `dist\WSL Deck\`（onedir，約 100 MB）與 `dist\WSL-Deck-M6-20261103.zip`（約 41 MB） |
| 捷徑 | `WSL Deck.lnk` 已指向 `dist\WSL Deck\WSL Deck.exe` |

## 2. 安裝包設計

| 項目 | 決策 |
|------|------|
| 工具 | Inno Setup 6.7.3（winget 安裝；安裝工具本身可能需要一次 UAC） |
| 安裝範圍 | **目前使用者**（`PrivilegesRequired=lowest`），安裝到 `{localappdata}\Programs\WSL Deck`，安裝 App 時不彈 UAC |
| 版本 | `1.0.0` |
| 捷徑 | 開始選單固定建立；桌面捷徑以 Tasks 提供（預設勾選） |
| 卸載 | 標準 `unins000.exe`，寫入 HKCU 的 Apps & Features 項目 |
| 設定保留 | `config.json` 以 `onlyifdoesntexist` 安裝；升級或重裝不覆蓋既有設定 |
| 安裝內容 | `dist\WSL Deck\` 全部檔案（含 `_internal`） |
| 語言 | 優先簡體中文；若 Inno 未附 `ChineseSimplified.isl` 則用英文安裝介面（App 本身仍為繁中） |
| 圖標 | 捷徑與卸載項使用 `WSL Deck.exe` 的圖標（目前為 PyInstaller 預設圖標，不改） |
| 輸出 | `dist\WSL-Deck-Setup-1.0.0.exe` |

## 3. 檔案變更

| 檔案 | 內容 |
|------|------|
| `installer\WSL Deck.iss`（新增） | Inno Setup 腳本：AppId、目錄、檔案、捷徑、Tasks、Run、Uninstall |
| `build-installer.ps1`（新增） | 尋找 `ISCC.exe`（Program Files 或 x86），執行 `.iss`，驗證輸出存在 |
| `dist\WSL-Deck-Setup-1.0.0.exe`（產物） | 安裝包 |
| `dist\WSL-Deck-M6-20261103.zip` | 保留不動 |

`.iss` 重點設定：

```ini
[Setup]
AppId={{固定的 GUID}}
AppName=WSL Deck
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\WSL Deck
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\WSL Deck.exe
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=WSL-Deck-Setup-1.0.0

[Files]
Source: "..\dist\WSL Deck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\WSL Deck\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; Flags: checkedonce

[Icons]
Name: "{autoprograms}\WSL Deck"; Filename: "{app}\WSL Deck.exe"
Name: "{autodesktop}\WSL Deck"; Filename: "{app}\WSL Deck.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WSL Deck.exe"; Description: "啟動 WSL Deck"; Flags: nowait postinstall skipifsilent
```

- 不設定 `CloseApplications`，避免安裝時強制關閉正在執行的 App。
- 不安裝開機自啟；沿用 App 內設定。
- 卸載不額外刪除使用者日後產生的 logs（Inno 只移除它安裝的檔案）。

## 4. 任務

1. **安裝 Inno Setup**：`winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements`；若因 UAC 無法完成，提供使用者手動命令。
2. **撰寫 `installer\WSL Deck.iss`**：固定 GUID（一次生成後不再變），其餘照 §2。
3. **撰寫 `build-installer.ps1`**：自動找 ISCC、執行、檢查 `dist\WSL-Deck-Setup-1.0.0.exe`。
4. **建置**：執行 `build-installer.ps1`。
5. **靜默安裝測試**：
   - `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="D:\VirtualMachiles\wsl\_installer-test" /TASKS=""`
   - 驗證 `_installer-test\WSL Deck.exe`、`config.json`、開始選單捷徑、HKCU 卸載項。
6. **啟動測試**：`_installer-test\WSL Deck.exe --silent`，等 8 秒，日誌應載入 5 個 instance 且無錯誤，然後終止。
7. **設定保留測試**：修改測試安裝的 `config.json`（例如 `view_mode=list`），再次靜默安裝到同一目錄，確認設定未被覆蓋。
8. **卸載測試**：`unins000.exe /VERYSILENT`，確認 exe 與捷徑消失、卸載項移除；手動清理殘留 logs。
9. **交付**：保留攜帶版 zip；新增 `WSL-Deck-Setup-1.0.0.exe`。

## 5. 驗收

1. `dist\WSL-Deck-Setup-1.0.0.exe` 存在，大小合理（約 40–60 MB）。
2. 安裝到測試目錄後可直接啟動，日誌無 traceback。
3. 開始選單出現「WSL Deck」；桌面捷徑按 Tasks 建立。
4. 第二次安裝不覆蓋既有 `config.json`。
5. 卸載後 exe、`_internal`、捷徑與 HKCU 卸載項消失。
6. 攜帶版 `dist\WSL Deck` 與 zip 不受影響。

## 6. 風險與回滾

| 風險 | 對策 |
|------|------|
| 安裝 Inno Setup 需要 UAC，Agent 無法代點 | 先嘗試 winget `--silent`；失敗則把命令交給使用者執行一次 |
| Inno 未附簡中語言檔 | 自動偵測 `Languages\ChineseSimplified.isl`，不存在就用英文介面 |
| SmartScreen 未知發佈者 | 未簽名屬預期；使用者選「仍要執行」 |
| 安裝覆蓋使用者設定 | `onlyifdoesntexist`；並在測試中驗證 |
| 卸載殘留 logs／config 之外的檔案 | 明確告知；必要時手動刪除安裝目錄 |
| 安裝到 `%LocalAppData%\Programs` 被企業策略限制 | 允許安裝時自訂目錄；失敗則改用 `--scope` 或手動指定 |
| 無 git，改壞難回復 | 只新增 installer 與 build 腳本，不動 App 程式碼；攜帶版與 zip 保留 |

## 7. 確認清單

- [ ] 同意安裝 Inno Setup 6.7.3（可能需一次 UAC）。
- [ ] 同意採用「目前使用者安裝、免 UAC」到 `%LocalAppData%\Programs\WSL Deck`。
- [ ] 同意開始選單固定、桌面捷徑可選、標準卸載項。
- [ ] 同意 `config.json` 僅在不存在時寫入，升級不覆蓋。
- [ ] 同意保留攜帶版 zip，另產出 `WSL-Deck-Setup-1.0.0.exe`。
- [ ] 同意在 `_installer-test` 目錄做安裝／卸載測試。

確認後才動工。
