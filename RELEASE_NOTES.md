# WSL Deck v1.0.1

管理 WSL2 實例的 Windows 桌面程式。本次為修補版本，修正網路隔離下的 MySQL 重複啟動問題、免安裝版 zip 的打包失敗，並讓終端分頁標題可辨識實例。

## 下載

- **安裝版** `WSL-Deck-Setup-1.0.1.exe` — 裝到 `%LocalAppData%\Programs\WSL Deck`，不需要管理員權限
- **免安裝版** `WSL-Deck-1.0.1-<日期>.zip` — 解壓即用

需要 Windows 10/11（64 位元），且 WSL2 已啟用。

## 本次更新

### 修正

- **網路隔離臨時模式的 MySQL 重複實例**（`fix(netns)`）
  臨時模式原本只 `systemctl stop` 原 unit，任何人再執行一次 `service mysql start` 就會在共用網路多起一份 `mysqld`，搶不到 `ibdata1` 而無限重試，對外看起來像 MySQL 起不來。現在停止後會 `mask --runtime` 原 unit，於 cleanup／restore／切換永久模式前 unmask；套用後會檢查原 unit 是否仍 active／activating，衝突時回報 warning；mask 失敗也改為回報 warning。
- **免安裝版 zip 打包失敗**（`fix(build)`）
  `build-zip.ps1` 改用 `tar.exe` 取代 `Compress-Archive`，解決檔案被鎖住時 zip 產出失敗的問題。

### 改進

- **終端標題固定顯示 `user@instance`**（`feat(shell)`）
  從 WSL Deck 開終端時，原本所有分頁都叫 `user@host`，多開幾個實例無法區分。改以 `wt new-tab --title <user>@<instance>` 指定標題，並加 `--suppressApplicationTitle` 避免 shell PS1 把標題覆寫回 `user@host`；使用者名稱透過背景執行緒查詢，查不到時標題退回實例名稱。

## 功能

- 卡片牆／列表兩種檢視，狀態、IP、磁碟大小一眼看完
- 新增實例三步精靈：官方發行版、rootfs/tar、VHDX
- 啟停、開終端、開 Linux 檔案、開安裝目錄
- 備份／還原／複製／刪除
- restic 增量快照，每日／每週／每月保留策略
- 改 `/etc/wsl.conf`、預設使用者、systemd 開關
- Windows 端口轉發與防火牆規則，一次 UAC 跑完
- 網路隔離模式（netns），避免多實例埠衝突
- 托盤、開機自啟、深淺主題

## 已知限制

- 只支援 Windows
- 還原是覆蓋式：先備份現況 → 註銷 → 重新匯入，不做 diff
- Docker Desktop 的系統實例只看不碰
- 安裝包未簽章，Windows 可能跳 SmartScreen 提示，選「更多資訊 → 仍要執行」
