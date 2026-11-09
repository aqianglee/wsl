# 計畫：為 GitHub 開源準備 README 與 LICENSE

> **狀態：已完成（2026-11-09）**
> 產物：[README.md](../README.md)（9,780 bytes）、[LICENSE](../LICENSE)（MIT，1,078 bytes），皆位於倉庫根。

> 目標：讓本倉庫（`d:\workspaces\workspace-wsl-deck\wsl-deck\`，已為 git 根）具備 GitHub 首頁所需的 README，以及一份開源授權條款檔。兩份檔案位於倉庫根，GitHub 會自動渲染。

## 1. 現狀盤點

- 倉庫根 `d:\workspaces\workspace-wsl-deck\wsl-deck\` 目前**沒有** `README.md` 與 `LICENSE`，GitHub 首頁會顯示空白。
- 專案本體位於子目錄 `wsl-deck\wsl-deck\`（以下稱「應用根目錄」），程式層面資訊來自：
  - 入口 [main.py](../wsl-deck/main.py) — PySide6 GUI、單實例、可 --silent 入托盤。
  - 依賴 [requirements.txt](../wsl-deck/requirements.txt)（僅 `PySide6-Essentials==6.12.0`）+ [requirements-dev.txt](../wsl-deck/requirements-dev.txt)（`pyinstaller==6.22.3`）。
  - 功能全景見 [docs/handover/00-overview.md](../docs/handover/00-overview.md) §1：列出/啟停、卡片牆/表格、新增精靈、備份/還原/複製、restic 增量快照、/etc/wsl.conf 設定、netsh 端口轉發、托盤/自啟/主題。
  - 版本來源 [installer/WSL Deck.iss](../wsl-deck/installer/WSL%20Deck.iss) `MyAppVersion=1.0.0`。
  - 測試：135 項 unittest，全 mock，不碰真實 wsl。
  - 打包：`build.ps1` → onedir；`build-installer.ps1` → Inno Setup 安裝包；`build-zip.ps1` → 免安裝 zip。
- `.screenshots/` 目錄目前只有 `.tmp`，**沒有可用的應用截圖**，README 不能引用不存在的圖。
- 專案介面、日誌、文件皆為繁體中文，團隊慣用繁中。

## 2. 待辦與範圍

本次**只做兩件事**，其餘檔案一律不動：

| # | 產物 | 位置 |
|---|------|------|
| 1 | `README.md` | 倉庫根 `d:\workspaces\workspace-wsl-deck\wsl-deck\README.md` |
| 2 | `LICENSE`（含版權標頭） | 倉庫根 `d:\workspaces\workspace-wsl-deck\wsl-deck\LICENSE` |

明確**不做**：
- 不修改任何 Python/PS1/ISS 檔。
- 不新增截圖（目錄沒素材，等以後使用者提供）。
- 不新增 CONTRIBUTING、CODE_OF_CONDUCT、SECURITY、CHANGELOG 等附屬文件，避免首次開源就檔案膨脹。
- 不 git commit；由使用者自行檢閱後再決定何時入版控。

## 3. README.md 內容規劃

語言：**繁體中文**（與專案 UI/文件一致）；在最末段給出 English TL;DR 摘要，方便非中文讀者快速理解。整體長度約 250–320 行，節制不浮誇。

章節順序（自上到下）：

1. **專案徽章行**：License、平台 Windows、語言 Python、框架 Qt6/PySide6、版本 1.0.0、測試 unittest 135 項全綠（徽章使用 shields.io 靜態徽章，離線也不影響 README 可讀性）。
2. **一句話介紹**：「WSL Deck 是一個 Windows 桌面 GUI，把 `wsl.exe` 的常用操作可視化，用來管理多個 WSL2 發行版實例。」
3. **為什麼做這個**：3–5 句痛點說明（命令列分散、缺乏快照與端口轉發統一入口、缺乏 GUI 卡片式管理）。
4. **功能特色**（條列 8 項）：
   - 實例清單（卡片牆/表格兩種視圖，含狀態、IP、容量、預設標記）
   - 新增精靈（官方線上發行版 / 本地 tar / VHDX 三種來源）
   - 一鍵啟停、開啟終端、開啟檔案位置
   - 備份 / 還原 / 複製 / 刪除（覆蓋式還原）
   - 增量快照（restic 後端，含每日/每週/每月保留策略）
   - 編輯 `/etc/wsl.conf`、預設使用者、systemd 開關
   - Windows 端口轉發與防火牆規則（`netsh portproxy`，批次 UAC）
   - 系統托盤、開機自啟、深/淺主題、單實例喚醒
5. **系統需求**：Windows 10/11 64 位元 + WSL2 已啟用；執行來源碼需 Python 3.14+；PySide6 6.12.0。
6. **快速開始**：
   - 一般使用者 → 下載 Release 的 `WSL-Deck-Setup-*.exe`（未來）或 `*-win64.zip`。
   - 開發者 → `git clone` → `python -m venv .venv` → `pip install -r requirements.txt` → `pythonw main.py`。
7. **從原始碼建置**（簡述三條產線）：
   - `build.ps1`（PyInstaller onedir）
   - `build-installer.ps1`（Inno Setup 安裝包，需先裝 Inno Setup 6）
   - `build-zip.ps1`（免安裝 zip）
8. **執行測試**：`python -m unittest discover -s tests -q`（135 項全 mock）。
9. **目錄結構**：貼一段精簡 tree（倉庫根 → wsl-deck → app/ui/tests/assets/installer）。
10. **設定檔**：解釋 `config.json` 是本機狀態、被 `.gitignore` 排除、首次啟動會以預設值建立；列出 3 個重要 key（`workspace_root`、`theme`、`proxy`）。
11. **常見問題**：3–5 條，來自 [04-troubleshooting.md](../docs/handover/04-troubleshooting.md) 精華（視窗沒出現、UAC 觸發時機、為何不能動 docker-desktop、IP 顯示「-」的原因）。
12. **授權**：指向 `LICENSE`（預計 MIT，見 §4）。
13. **致謝**（可選）：感謝 PySide6、restic、Inno Setup、shields.io。
14. **English TL;DR**：5–8 行英文摘要，給非中文讀者。

## 4. LICENSE 選擇

建議 **MIT License**，理由：
- 專案是單人/小團隊桌面工具，MIT 對商用與再發布最友善、最常見於 Qt 桌面應用。
- 依賴 `PySide6-Essentials` 採 LGPLv3，MIT 與之相容（動態連結）。
- 不依賴 copyleft；GPLv3 會強制衍生作品開源，對貢獻者門檻高。

若你更在意「衍生作品必須同樣開源」可改 GPLv3；若更在意專利授權明確可改 Apache-2.0。**本計畫預設採 MIT**，如需更換請在回覆中指出。

LICENSE 檔案內容：標準 MIT 全文，抬頭填 `Copyright (c) 2026 WSL Deck contributors`。年份取當前系統年（2026），版權人使用專案通用名「WSL Deck contributors」而非個人姓名——若你希望填具體姓名/組織，請在回覆中提供。

## 5. 檔案編碼與格式

- `README.md`：UTF-8（無 BOM）、CRLF、Markdown CommonMark。
- `LICENSE`：UTF-8（無 BOM）、LF（GitHub 授權偵測建議 LF）。
- 兩者皆放在倉庫根，GitHub 會自動在 repo 首頁渲染 README 並於右上角顯示 License。

## 6. 驗收方式

1. 在倉庫根執行 `Get-Content README.md -TotalCount 5`，確認首行是 `# WSL Deck`。
2. 在 PowerShell 用 `Get-Content LICENSE` 檢查首行 `MIT License`。
3. 使用者於 GitHub Web 上傳或 push 後，repo 首頁應自動渲染 README、右側應出現 `License: MIT`。

## 7. 回滾

兩份檔案皆為新建，不修改任何既有檔案；若結果不符預期，直接刪除 `README.md` / `LICENSE` 即可還原。

## 8. 待確認事項

| # | 問題 | 預設 |
|---|------|------|
| Q1 | LICENSE 選型 | **MIT**（可改 GPLv3 / Apache-2.0） |
| Q2 | LICENSE 版權人抬頭 | `WSL Deck contributors`（可改為你的姓名/組織） |
| Q3 | README 語言 | **繁體中文為主**＋末段英文 TL;DR（可改純繁中或雙語併排） |
| Q4 | 是否需要在 README 放佔位截圖區塊 | **不放**（等素材到位再補） |
| Q5 | 是否額外附 `CONTRIBUTING.md` | **不附**（避免初期膨脹） |

如無異議請回覆「確認」或「OK，按預設執行」；如需調整任一項，請指出編號與新值。
