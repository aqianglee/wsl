# WSL Deck v1.0.0

第一個公開版本。管理 WSL2 實例的 Windows 桌面程式。

## 下載

- **安裝版** `WSL-Deck-Setup-1.0.0.exe` — 裝到 `%LocalAppData%\Programs\WSL Deck`，不需要管理員權限
- **免安裝版** `WSL-Deck-1.0.0-<日期>.zip` — 解壓即用

需要 Windows 10/11（64 位元），且 WSL2 已啟用。

## 功能

- 卡片牆／列表兩種檢視，狀態、IP、磁碟大小一眼看完
- 新增實例三步精靈：官方發行版、rootfs/tar、VHDX
- 啟停、開終端、開 Linux 檔案、開安裝目錄
- 備份／還原／複製／刪除
- restic 增量快照，每日／每週／每月保留策略
- 改 `/etc/wsl.conf`、預設使用者、systemd 開關
- Windows 端口轉發與防火牆規則，一次 UAC 跑完
- 托盤、開機自啟、深淺主題

## 已知限制

- 只支援 Windows
- 還原是覆蓋式：先備份現況 → 註銷 → 重新匯入，不做 diff
- Docker Desktop 的系統實例只看不碰
- 安裝包未簽章，Windows 可能跳 SmartScreen 提示，選「更多資訊 → 仍要執行」
