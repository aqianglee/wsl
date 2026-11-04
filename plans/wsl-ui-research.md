# Plan：WSL Instance 管理 UI — 調研與立項

> 狀態：待確認（確認後才開始執行）
> 方法：wayfinder（本專案尚無 issue tracker，故以本文件作為地圖；若後續立項再初始化 local-markdown tracker）

## 1. 背景與現狀

- 工作目錄 `d:\VirtualMachiles\wsl` 存放多個 distro 資料夾（`ubuntu`、`node22`、`alms`）與 `backups`。
- 目前唯一自動化痕跡是 [import-from-file.bat](file:///d:/VirtualMachiles/wsl/import-from-file.bat)，內容為單條 `wsl --import ... --version 2 --vhd`。
- 痛點（用戶自述）：使用頻率低、記不住參數，每次操作都要翻文檔；希望有 UI 管理 Linux instances。

## 2. Destination（本次地圖的終點）

一份可執行的結論與規格：
1. 市面上既有 WSL GUI 管理工具的調查結果與功能對照；
2. 明確決策：直接採用現有工具，或自建；
3. 若自建：MVP 功能清單 + 技術選型 + 可配置參數設計 + 驗收標準（足以交給下一個 session 實作）。

## 3. 任務拆解

| # | 任務 | 類型 | 產出 |
|---|------|------|------|
| T1 | 市場調研：GitHub / 官方文件 / Microsoft Store 上以 `wsl.exe` 為核心的 GUI 管理器 | research (AFK) | 工具清單 + 功能矩陣（distro 列表、import/export、terminate、預設 distro、VHD 模式、mount、端口轉發、service/systemd、SSH、快照/備份） |
| T2 | 差距分析：對照「低頻使用、低認知負擔、參數可配置」的實際需求 | research (AFK) | 現有工具覆蓋率與缺口 |
| T3 | 決策：採用 / 自建 / 混合（現成工具 + 自寫腳本封裝） | HITL | 決策記錄 |
| T4 | 若自建：技術選型（Tauri vs Electron vs .NET WPF/WinUI；`wsl.exe` CLI vs WSL COM API；管理員權限與 UAC 處理） | grilling (HITL) | 選型結論 + 理由 |
| T5 | MVP 功能規格：命令預覽、危險操作二次確認、日誌面板、配置檔（參數可配置） | grilling (HITL) | 功能規格 |
| T6 | 交付與驗收：如何在本機跑起來、如何驗證每個功能 | task | 驗收清單 |

## 4. 執行順序

1. T1 + T2 並行（可派子代理做網絡調研），輸出一份對照報告。
2. 帶著報告與用戶確認 T3（採用或自建）。
3. 僅在「自建」分支：T4 → T5 → T6，形成可實作規格。

## 5. 驗收標準

- T1 至少覆蓋 5 個以上真實存在的工具，每個附來源連結與最後更新時間。
- 功能矩陣中每一項都能回答「現有工具是否支援」。
- T3 有明確結論，並記錄理由。
- 若自建，T5 的每個功能都能對應到具體 `wsl.exe` 子命令或 API。

## 6. 風險

- 部分工具已停更或僅支援 WSL1，需標註版本與活躍度。
- Microsoft Store 類工具無法用一般搜尋完整列舉，可能遺漏。
- 自建需處理 UAC／管理員權限，否則 `--import`、`--mount` 等會失敗。

## 7. 需要用戶確認

- [x] 同意本計畫並開始執行 T1/T2（2026-10-30 已確認）
- [x] 重點能力：參數可配置化、端口轉發與網路、啟動/停止/預設 distro、Import/Export + VHD
- [ ] T3 決策：採用現有工具或自建

## 8. T1/T2 調研結果（2026-10-30）

### 候選工具

| 工具 | 技術／授權 | 活躍度 | 與四大重點的對照 |
|------|-----------|--------|------------------|
| **WSL Dashboard**（[owu/wsl-dashboard](https://github.com/owu/wsl-dashboard)，[官網](https://www.wslui.com/zh-CN/)） | Rust + Slint，GPL-3.0，單一 portable exe | v0.12.0，2026-10-10 | 全部命中：端口轉發 + 自動防火牆規則 + 開機自動恢復；啟動/停止/終止/註銷/設預設；本機 RootFS/VHDX 安裝、tar/tar.gz 匯出／克隆、VHDX 遷移；另附 VHD/物理磁盤掛載、usbipd-win、任務計劃、繁中介面、托盤約 10MB |
| **WSL UI**（[octasoft-ltd/wsl-ui](https://github.com/octasoft-ltd/wsl-ui)，[官網](https://wsl-ui.octasoft.co.uk/)） | Tauri 2 + React，GPL-3.0，約 4MB | v0.19–0.21，近期活躍 | 命中三項：生命週期／預設 distro、tar 匯出匯入＋克隆、VHD/物理磁盤掛載；**無端口轉發功能**；強項是 Custom Actions（`${DISTRO_NAME}` 等變量替換、啟動動作、動作鏈、正則批量），適合「參數可配置化」；微軟商店可裝 |
| **WSL Manager**（[bostrot/wslmanager](https://github.com/bostrot/wslmanager)，[官網](https://wslmanager.com/)） | Flutter，免費＋Pro 買斷，開源 | 2.5.0，2026-10-01 | 命中三項：生命週期／預設、備份還原／克隆、VHD 掛載、`.wslconfig` 圖形化；Snippets 可存命令模板；**無端口轉發**；另有 Docker 映像轉 distro、SSH 遠端管理、MCP（Pro） |
| VS Code 擴展 WSL Manager（jkudo） | VS Code 擴展 | 持續更新 | 僅發行版列表、啟停、tar/vhdx 匯出匯入、克隆；依賴 VS Code，無網路功能 |
| Microsoft「WSL Settings」 | 官方 | 隨 WSL 更新 | 只編輯 `.wslconfig`，不管 instance 生命週期與備份 |

（LxRunOffline 等舊工具已由官方 `wsl --import/--export` 取代，不再列入推薦。）

### 結論

- 市面上**已有**成熟的 WSL UI 管理器，不需從零自建。
- 以本專案的四項重點排序，**WSL Dashboard 是最貼合的一個**：它是唯一同時具備「端口轉發 + 防火牆規則自動化 + 開機自動恢復」與「VHDX 本機安裝／遷移」的工具，且繁中介面、單檔免安裝、資源佔用低。
- 若更看重「參數可配置化／自動化動作」且不需要端口轉發，**WSL UI** 的 Custom Actions 更強，且有微軟商店版本。
- 注意：WSL Dashboard **未上架 Microsoft Store**，官方明言商店同名應用為盜版；應從 GitHub Releases 或 `winget install Owu.WSLDashboard` 安裝。

### 待實測（採用前驗證）

1. 用現有 `backups/ubuntu/ubuntu.vhdx` 走一次「本機 VHDX 安裝」，確認等價於 `wsl --import node22 ... --version 2 --vhd`。
2. 端口轉發規則是否以管理員權限建立、重開機後是否自動恢復。
3. 匯出格式是否符合需求（tar/tar.gz；若需 `.vhdx` 快照，可能仍需 `wsl --export --vhd` 命令或自建封裝）。
