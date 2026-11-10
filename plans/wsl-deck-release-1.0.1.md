# 發佈 WSL Deck v1.0.1

> 狀態：**已完成**（release 頁面由使用者手動建立）

## 1. 現況核實

| 項目 | 實測結果 |
|------|----------|
| 分支 | `main`，領先 `origin/main` **2 個 commit** |
| 未推送 commit | `4b6ba99` fix(netns) 臨時模式 mask 原 unit；`b22458e` feat(shell) 終端標題 `user@instance` |
| 未提交變更 | `wsl-deck/build-zip.ps1` 僅多了一個 BOM（`﻿` → `﻿﻿`），屬誤改 |
| 未追蹤檔案 | `README.md.ai-draft.bak`（9.7 KB，AI 草稿備份） |
| 遠端 tag | `1.0.0`（指向 `ee4e3d2`） |
| 遠端 release | `1.0.0` 已存在，含 `WSL-Deck-Setup-1.0.0.exe`、`WSL-Deck-1.0.0-20261109.zip` |
| `dist` 產物 | 皆為 1.0.0（2026-11-09 建置） |
| 單元測試 | `Ran 162 tests` — OK |
| `gh` CLI | **未安裝**；無 `GITHUB_TOKEN`；`credential.helper=manager`（push/tag 可用） |
| 版本號唯一來源 | `wsl-deck/installer/WSL Deck.iss` 的 `MyAppVersion "1.0.0"` |

`1.0.0` 之後的變更（將列入 1.0.1 日誌）：

1. `fix(build)`：`build-zip.ps1` 改用 `tar.exe` 壓縮，解決 `Compress-Archive` 檔案鎖導致 zip 失敗
2. `fix(netns)`：臨時模式停止後 `mask --runtime` 原 unit，避免 netns 內服務被再次拉起而搶佔 `ibdata1`
3. `feat(shell)`：終端標題固定 `user@instance`，並抑制 shell 覆寫標題

## 2. 已確認決策

| # | 問題 | 決定 |
|---|------|------|
| D1 | 是否重建 1.0.1 產物（exe／zip） | **是**，三項產物全部重建 |
| D2 | release 建立方式（`gh` 未安裝、無 token） | **網頁手動**。我完成 bump＋建置＋commit＋push＋tag＋release notes，release 頁面由使用者在 GitHub 建立並上傳資產 |
| D3 | `README.md.ai-draft.bak` | **已刪除**，未進版本庫 |
| D4 | `build-zip.ps1` 多餘 BOM | **已還原**，未提交 |

## 3. 執行步驟

1. **清工作區**：刪 `README.md.ai-draft.bak`；`git checkout -- wsl-deck/build-zip.ps1` 還原 BOM。
2. **升版 1.0.1**：
   - `installer/WSL Deck.iss`：`MyAppVersion "1.0.0"` → `"1.0.1"`
   - `build-installer.ps1:15`：硬編碼檢查路徑 `WSL-Deck-Setup-1.0.0.exe` → `1.0.1`（不改則腳本誤報失敗）
3. **重建三項產物**：`build.ps1` → `build-installer.ps1` → `build-zip.ps1`，確認 `dist` 內時間戳為今日、檔名為 1.0.1。
4. **驗證**：`py_compile` 關鍵檔＋`unittest discover` 162 項全綠；確認 zipped `config.json` 未帶開發機路徑。
5. **提交**：`chore(release): 升版 1.0.1 並更新建置腳本版本檢查`，只納入 iss、build-installer.ps1（以及若同意一併提交的 release notes）。
6. **推送**：`git push origin main`（含先前 2 個 commit）。
7. **打 tag**：`git tag -a 1.0.1 -m "WSL Deck v1.0.1"`、`git push origin 1.0.1`（沿用 1.0.0 的無前綴風格）。
8. **寫 release notes**：更新 `RELEASE_NOTES.md` 為 1.0.1（保留功能與已知限制段落），內容可直接貼進 GitHub release 描述。
9. **建立 release**：由使用者在 `https://github.com/aqianglee/wsl/releases/new` 選擇 tag `1.0.1`，貼上 `RELEASE_NOTES.md` 並上傳兩項資產。
10. **驗收**：release 頁顯示 2 項自訂資產；`git status` 乾淨；`git log origin/main..HEAD` 為空。

## 4. 驗證結果

| 項目 | 結果 |
|------|------|
| `build.ps1` | 成功，`dist\WSL Deck\WSL Deck.exe` 存在 |
| `build-installer.ps1` | 成功，`dist\WSL-Deck-Setup-1.0.1.exe`（29.1 MB，檔案版本 1.0.1） |
| `build-zip.ps1` | 成功，`dist\WSL-Deck-1.0.1-20261110.zip`（39.7 MB） |
| zip 內容抽查 | 無 `config.json`、無 `logs/`，入口 `WSL Deck/WSL Deck.exe` 存在 |
| `unittest discover` | `Ran 162 tests` — OK |

## 5. 風險

| 風險 | 處理 |
|------|------|
| 建置時間較長（PyInstaller 約 1–3 分鐘） | 分步執行，失敗即停並回報日誌 |
| `gh auth login` 需人工授權 | 由您完成，我只等結果 |
| tag 已存在同名 | 執行前 `git ls-remote --tags` 檢查，不覆蓋既有 tag |
| 誤把開發機 `config.json` 打包 | zip 預設排除；建置後抽查 |
