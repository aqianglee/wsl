# 計畫：發佈 GitHub Release（上傳 zip 與安裝包）

> 目的：把 `dist\` 的 `WSL-Deck-Setup-1.0.0.exe` 與 `WSL-Deck-1.0.0-*.zip` 掛到 GitHub Releases，讓不想裝 Python 的人直接下載。

## 1. 現況

| 項目 | 狀態 |
|------|------|
| 遠端倉庫 | `https://github.com/aqianglee/wsl.git`（注意：repo 名叫 `wsl`，不是 `wsl-deck`） |
| 分支 | `main`，無任何 tag |
| 未提交 | `LICENSE`、`README.md`、`docs/screenshots/`、3 份 plans |
| `gh` CLI | **未安裝** |
| Inno Setup 6 | 已安裝（`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`） |
| 現有產物 | `dist\WSL-Deck-Setup-1.0.0.exe`（27.8 MB）、`dist\WSL-Deck-1.0.0-20261105.zip`（39.5 MB）— **2026-11-05 建的，早於本次 UI 改動與 README** |

兩個要先處理的坑：

1. **README 克隆網址是佔位符** `<your-account>/wsl-deck.git`，實際是 `aqianglee/wsl.git`。不修的話 release 頁的 clone 指令是錯的。
2. **舊產物過期**。dist 裡那兩支是 11-05 的，之後改過表格、對話框、圖示。直接上傳等於發舊版。

## 2. 我可以代做的部分

| # | 動作 | 說明 |
|---|------|------|
| 1 | 修 README 克隆網址 | `<your-account>/wsl-deck.git` → `aqianglee/wsl.git`（1 行） |
| 2 | 重建 onedir | `.\build.ps1`（PyInstaller，約 1–3 分鐘） |
| 3 | 重建安裝包 | `.\build-installer.ps1` → `dist\WSL-Deck-Setup-1.0.0.exe` |
| 4 | 重建 zip | `.\build-zip.ps1` → `dist\WSL-Deck-1.0.0-<今天>.zip` |
| 5 | 起草案 release notes | 產出一段可直接貼的 Markdown（含版本、亮點、下載說明、已知限制） |

**我不代做**：`git commit` / `git push` / 建立 tag / 上傳資產——這些涉及公開發佈，由您按確認鍵。

## 3. 發佈流程（二選一）

### 方案 A：GitHub 網頁（不需裝任何工具，推薦）

1. **先推程式碼**（在倉庫根 `d:\workspaces\workspace-wsl-deck\wsl-deck`）：

```powershell
git add README.md LICENSE docs/screenshots plans/wsl-deck-readme-*.md
git commit -m "docs: README、MIT LICENSE 與應用截圖"
git push origin main
```

2. **打 tag 並推上去**：

```powershell
git tag -a v1.0.0 -m "WSL Deck v1.0.0"
git push origin v1.0.0
```

3. **開 release 頁**：`https://github.com/aqianglee/wsl/releases/new`
   - Choose a tag → `v1.0.0`（剛推上去會出現在清單）
   - Release title → `WSL Deck v1.0.0`
   - 描述欄貼上我起草的 release notes
4. **上傳兩個資產**（把檔案拖進「Attach binaries」框，或點選）：
   - `wsl-deck\wsl-deck\dist\WSL-Deck-Setup-1.0.0.exe`
   - `wsl-deck\wsl-deck\dist\WSL-Deck-1.0.0-20261109.zip`
5. 勾「Set as the latest release」→ **Publish release**

> GitHub 會自動附上「Source code (zip/tar.gz)」，那是原始碼快照，與您的 exe/zip 資產並存，正常現象。

### 方案 B：gh CLI（想用指令一鍵發佈）

```powershell
winget install --id GitHub.cli
gh auth login                       # 選 HTTPS，瀏覽器授權
gh release create v1.0.0 `
  "wsl-deck\wsl-deck\dist\WSL-Deck-Setup-1.0.0.exe" `
  "wsl-deck\wsl-deck\dist\WSL-Deck-1.0.0-20261109.zip" `
  --title "WSL Deck v1.0.0" --notes-file RELEASE_NOTES.md --target main
```

好處是之後改版一行搞定；壞處是多裝一個工具、要授權。

## 4. Release notes 草案（屆時產出檔案或直接貼給您）

```markdown
## WSL Deck v1.0.0

第一個公開版本。管理 WSL2 實例的 Windows 桌面程式。

### 下載

- **安裝版**：`WSL-Deck-Setup-1.0.0.exe` — 安裝到 `%LocalAppData%\Programs\WSL Deck`，不需管理員權限
- **免安裝版**：`WSL-Deck-1.0.0-20261109.zip` — 解壓即用

需要 Windows 10/11 64 位元，且已啟用 WSL2。

### 功能

- 卡片牆／列表兩種檢視，顯示狀態、IP、磁碟大小
- 新增實例三步精靈（官方發行版／rootfs-tar／VHDX）
- 啟停、終端、Linux 檔案、安裝目錄一鍵直達
- 備份／還原／複製／刪除
- restic 增量快照（每日／每週／每月保留策略）
- `/etc/wsl.conf`、預設使用者、systemd 設定
- Windows 端口轉發與防火牆規則（批次 UAC）
- 托盤、開機自啟、深淺主題

### 已知限制

- 只支援 Windows
- 還原為覆蓋式（先備份現況 → 註銷 → 重新匯入），不做 diff
- Docker Desktop 的系統實例只看不碰
- 安裝包未簽章，Windows 可能跳 SmartScreen 提示（選「更多資訊 → 仍要執行」）
```

## 5. 驗收

1. `dist\` 內三項產物時間戳皆為今天。
2. Release 頁面顯示 2 個自訂資產 + 2 個原始碼包。
3. 換一台乾淨機器（或新資料夾）下載 zip 解壓即能啟動。

## 6. 待確認

| # | 問題 | 預設 |
|---|------|------|
| Q1 | 是否由我代做 §2 的 1–3 項（修 README 網址 + 重建三項產物） | 是 |
| Q2 | 版本號是否維持 `1.0.0` | 維持 |
| Q3 | 上傳方式 | 方案 A（網頁手動） |
| Q4 | 是否要我產出 `RELEASE_NOTES.md` 檔案 | 是（放倉庫根，之後可複用） |
| Q5 | 舊的 11-05 zip 是否刪除 | 保留，不影響 |
