# 計畫：建置 WSL Deck 新版本（instance 預設目錄變更）

## 1. 背景

- 本次程式已改為新增／複製 instance 預設使用 `<工作目錄>\instances`，並已搬移 5 個既有 instance。
- 目前 `dist\WSL Deck` 建置於 16:03、安裝包於 16:06，仍是舊版程式。
- 已安裝並執行中的 `WSL Deck.exe` 不會被本次建置影響。

## 2. 前置檢查

| 項目 | 狀態 |
| --- | --- |
| 單元測試 | 135 項全過 |
| PyInstaller | 6.22.3（`.venv` 內） |
| PySide6 | 6.12.0 |
| Inno Setup | `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` 存在 |
| `build.ps1` | 開頭有**重複 BOM**（`EF BB BF EF BB BF`），PowerShell 5.1 可能解析失敗，需先修正 |

## 3. 建置步驟

1. 修正 `wsl-deck/build.ps1`：移除重複的 BOM，只保留單一 UTF-8 BOM。
2. 執行 `build.ps1`：
   - PyInstaller `--noconfirm --clean`，輸出 `dist\WSL Deck\`。
3. 驗證 `dist\WSL Deck\WSL Deck.exe` 時間戳已更新。
4. 以來源 `wsl-deck\config.json` 覆蓋 `dist\WSL Deck\config.json`：
   - 避免新安裝沿用舊 `distro_root = D:\VirtualMachiles\wsl`。
5. 執行 `build-installer.ps1`：
   - ISCC 產出 `dist\WSL-Deck-Setup-1.0.0.exe`。
6. 驗證安裝包時間戳與大小。

## 4. 驗證清單

- [ ] `dist\WSL Deck\WSL Deck.exe` 時間戳晚於本次開始時間。
- [ ] `dist\WSL Deck\config.json` 的 `distro_root` 為 `D:\VirtualMachiles\wsl\instances`。
- [ ] `dist\WSL-Deck-Setup-1.0.0.exe` 時間戳已更新。
- [ ] 建置日誌 `build\pyinstaller.log` 無 ERROR。

## 5. 風險與說明

| 風險 | 處理 |
| --- | --- |
| 已安裝的舊版 App 正在執行 | 不影響 dist 建置；本計畫不自動安裝 |
| 安裝包版本號仍為 1.0.0 | 本次不 bump 版本；如需新版本號另行確認 |
| `build.ps1` BOM 修正 | 僅移除重複 BOM，不改邏輯 |

## 6. 已確認事項

- [x] 建置範圍：PyInstaller exe ＋ Inno Setup 安裝包（使用者確認）。
- [x] 不自動安裝新版本，僅產出 `dist` 成品。

## 7. 執行結果（2026-11-04）

- `build.ps1` 重複 BOM 已修正（`EF BB BF` 單一 BOM）。
- PyInstaller 建置成功：`dist\WSL Deck\WSL Deck.exe`（2026-11-04 17:30:06，2.39 MB）。
- `dist\WSL Deck\config.json` 已同步來源設定，`distro_root = D:\VirtualMachiles\wsl\instances`。
- `build\pyinstaller.log` 無 ERROR。
- Inno Setup 編譯成功：`dist\WSL-Deck-Setup-1.0.0.exe`（2026-11-04 17:30:51，28.99 MB）。
