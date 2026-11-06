# 計畫：新增 ZIP 發行包打包腳本

## 1. 目標

提供一個可重複使用的 PowerShell 腳本 `wsl-deck/build-zip.ps1`，把 `dist\WSL Deck\` 打成 ZIP 發行包，由使用者自行執行。

## 2. 腳本設計

| 項目 | 設計 |
| --- | --- |
| 檔案位置 | `wsl-deck/build-zip.ps1`（與 `build.ps1`、`build-installer.ps1` 同層） |
| 執行方式 | `.\build-zip.ps1` |
| 前置檢查 | `dist\WSL Deck\WSL Deck.exe` 不存在時報錯，提示先執行 `build.ps1` |
| 版本號 | 預設讀取 `installer\WSL Deck.iss` 的 `MyAppVersion`；可用 `-Version` 覆寫 |
| 輸出名稱 | `dist\WSL-Deck-<version>-<yyyyMMdd>.zip` |
| ZIP 結構 | 保留頂層 `WSL Deck\`，與現有 `WSL-Deck-M6-20261103.zip` 一致 |
| 預設排除 | `logs\`；`config.json` 依確認結果決定 |
| 暫存目錄 | `build\zip-stage\WSL Deck`，成功後刪除，避免污染 `dist` |
| 參數 | `-Version <string>`、`-IncludeConfig`（可選） |
| 編碼 | UTF-8 BOM，避免 PowerShell 5.1 中文輸出亂碼 |

## 3. 預計腳本邏輯

1. 解析參數與路徑。
2. 檢查 `WSL Deck.exe`。
3. 決定版本號（參數 → `.iss` → `1.0.0`）。
4. 建立 `build\zip-stage\WSL Deck`，複製 `dist\WSL Deck\*`。
5. 移除 `logs\`；若未指定 `-IncludeConfig` 則移除 `config.json`。
6. `Compress-Archive` 產出 ZIP，`-Force` 覆寫同名檔案。
7. 清理暫存目錄並輸出成品路徑與大小。

## 4. 驗證方式

- 以 PowerShell 語法解析器檢查腳本語法（不實際打包）。
- 檢查檔案編碼為單一 UTF-8 BOM。
- 實際打包由使用者自行執行。

## 5. 風險與說明

| 風險 | 處理 |
| --- | --- |
| 忘記先建置 | 腳本偵測不到 exe 即報錯並提示 `build.ps1` |
| 發行包帶本機 `config.json` | 預設排除，可用 `-IncludeConfig` 明確加入 |
| PowerShell 5.1 中文亂碼 | 檔案存為 UTF-8 BOM |

## 6. 已確認事項

- [x] 新增 `wsl-deck/build-zip.ps1`（使用者確認）。
- [x] `config.json` 預設排除（可用 `-IncludeConfig` 加入）。
- [x] 建立後不執行打包，交由使用者自行執行。

## 7. 執行結果（2026-11-04）

- 已建立 `wsl-deck/build-zip.ps1`，UTF-8 BOM 編碼。
- PowerShell 語法解析通過（`SYNTAX OK`）。
- 版本號解析驗證：`1.0.0` → 產出檔名 `dist\WSL-Deck-1.0.0-20261104.zip`。
- 未實際執行打包。
