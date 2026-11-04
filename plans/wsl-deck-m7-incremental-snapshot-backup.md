# M7 計畫：工作目錄骨架 + 增量快照備份

> 狀態：**已完成（M7.1，2026-11-04）**
> 目標：把 WSL Deck 收斂到單一「工作目錄」骨架，讓 `instances`／`backups`／`snapshots` 同層；並在 `snapshots` 下提供 restic 增量快照（多時間點、只佔差異空間）。
> 範圍：**M7.1**（骨架 + 快照建立／列表／刪除／清理／校驗 + 檔案級還原）。M7.2（整機還原）另案確認。

## 1. 已核實事實

- WSL 本體**沒有**快照或增量匯出：`wsl --export` 只支援 `tar`／`tar.gz`／`tar.xz`／`vhd`，每次全量（本機 `wsl --help` 實測）。
- 環境：WSL `3.0.3.0`、kernel `6.18.54.1-1`。
- `Ubuntu-26.04` 內建 `rsync 3.4.1`、`GNU tar 1.35`；沒有 `restic`／`borg`／`kopia`／`btrfs-progs`。
- `/mnt/d`（DrvFs 9p）硬連結、符號連結可用；但檔案一律 `0777 kyo:kyo`，**無法保留 uid/gid/權限**。
- WSL 內 **loop 裝置不可用**（`mount -o loop` 失敗）→ 不能在 NTFS 上放 ext4 映像當倉庫。
- 現有 `ext4.vhdx`：`Ubuntu-26.04` 2.26 GB、`ubuntu` 8.17 GB、`alms` 13.49 GB、`node22` 24.04 GB（全量備份 = 這個量級）。
- 現有配置：`distro_root = D:\VirtualMachiles\wsl`（實例直接放在工作目錄下）、`backup_root = D:\VirtualMachiles\wsl\backups`。

結論：**增量只能靠內容去重（restic）或硬連結快照（rsync），不是 WSL 原生能力**；目錄層面則可先整理成三個同層子目錄。

## 2. 目錄骨架（本次重點）

```
D:\VirtualMachiles\wsl\                 ← 工作目錄 Workspace
├─ instances\                           ← 放 instance（每個一個 ext4.vhdx）
├─ backups\<instance>\                  ← 整機備份（現有 VHDX／TAR 流程）
└─ snapshots\
   ├─ _tools\restic-linux-amd64         ← App 自動下載的 restic 靜態二進位
   └─ <instance>\
      ├─ repo\                          ← restic 增量倉庫
      └─ repo.pass                      ← 首次 init 自動產生的倉庫密碼
```

- 目錄名用**複數**（`instances`／`backups`／`snapshots`）：英語習慣上放多個項目的容器目錄用複數。
- 啟動時 `ensure_workspace()` 自動建立 `instances`、`backups`、`snapshots`（已存在則跳過）。
- **本次不搬移既有 instance**：`distro_root` 保留 `D:\VirtualMachiles\wsl`，設定頁標註「尚未整理」；整理留到 M8（用 `wsl --manage <name> --move <path>`）。
- 新安裝（沒有 `distro_root` 鍵）時，`distro_root` 才預設為 `<workspace>\instances`。

## 3. 方案比較（快照後端）

| 方案 | 每份增量成本 | 還原保真度 | 額外依賴 | 還原方式 | 評價 |
|---|---|---|---|---|---|
| **A. restic 增量倉庫（已選）** | 只存新增／變更區塊（zstd 壓縮），首份後通常幾十 MB～數百 MB | 完整（uid/gid/mode/xattr 存在倉庫內） | restic 靜態二進位（自動下載一次） | 檔案級覆蓋還原；或 dump → `wsl --import` 成新 instance | 最省空間、可校驗、可保留策略 |
| B. rsync 硬連結快照 | 只存變更檔案（整檔） | 倉庫在 NTFS → 權限失真 | 無 | 直接 rsync 回寫 | 零依賴，但檔案級 |
| C. tar `--listed-incremental` | 只存變更檔案（整檔） | 完整 | 無 | 需 0→N 回放，鏈條脆弱 | 最省依賴、最難維護 |
| D. 每次 `wsl --export vhd` | 全量（≈ vhdx 大小） | 完整 | 無 | `wsl --import --vhd` | 現況，非增量 |

## 4. 快照流程

### 4.1 建立
1. instance 未執行 → 先啟動；原本停止的在備份後自動終止回原狀。
2. 首次：`restic init`（自動產生 `repo.pass`，無需使用者輸入）。
3. 以 root 執行：`restic backup / --one-file-system --tag wsl-deck --host <distro> --exclude ...`。
4. 預設排除：`/proc /sys /dev /run /tmp /var/tmp /mnt /media /lost+found`；`/var/lib/docker`、`/var/lib/containerd` 預設排除，對話框提供「包含 Docker 資料」勾選。
5. 完成顯示：處理檔案數、新增／變更量、耗時，並刷新列表。

> 一致性：instance 執行中，資料庫／容器寫入中的檔案可能不同步。對話框固定提示「建議先停止資料庫或容器」；不自動 terminate。

### 4.2 列表／清理／校驗
- 列表：`restic snapshots --json` → 時間、標籤、short_id。
- 倉庫大小：`restic stats --json --mode raw-data`。
- 清理：`restic forget --keep-last 10 --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune`。
- 校驗：`restic check --read-data-subset=5%`。
- 刪除單筆：`restic forget <id> --prune`。

### 4.3 還原（M7.1）
- 檔案／目錄：`restic restore <id> --include <path> --target /`，root 執行；**不刪除多餘檔案**；二次確認，並可勾選「還原前先建一次快照」。

### 4.4 整機還原（M7.2，另案）
- `restic dump <id> /` 的 tar 串流 → `wsl --import <new> <dir> -`；不覆蓋原 instance，失敗自動 unregister。

## 5. restic 自動準備

1. 若 `snapshots\_tools\restic-linux-amd64` 不存在：`curl.exe -L` 從 GitHub Releases 下載 `restic_<ver>_linux_amd64.bz2`；啟用 SOCKS5 時加 `--socks5-hostname <host>:<port>`（沿用 `test_connection` 做法）。
2. Python `bz2` 解壓 → 寫入 → `chmod +x`。
3. `restic version` 驗證可執行；版本由 `RESTIC_VERSION` 常數控制。
4. 下載失敗：明確錯誤 + 重試入口，不影響既有全量備份。

## 6. 變更範圍

| 檔案 | 變更 |
|---|---|
| `app/workspace.py`（新增） | `WorkspacePaths`、`ensure_workspace()`（建立三個子目錄）、路徑驗證 |
| `app/snapshot.py`（新增） | restic 準備、Windows→WSL 路徑對映、init／backup／snapshots 解析／stats／forget／prune／check／restore、排除清單 |
| `app/config.py` | 新增 `workspace_root`、`snapshot_root`、`snapshot_keep`；遷移規則；驗證；不再強制 `distro_root`／`backup_root` 必有（改由 workspace 推導） |
| `main.py` | `Config` 載入後呼叫 `ensure_workspace()`，記錄建立結果 |
| `app/ui/settings_dialog.py` | 「工作目錄」主欄位 + `instance／備份／快照` 三欄 + 「套用工作目錄骨架」按鈕 + 保留策略；既有路徑欄位沿用 |
| `app/ui/snapshot_dialog.py`（新增） | 快照列表（時間／標籤／ID）、立即快照（含 Docker 勾選）、還原檔案、刪除、清理、校驗、開啟資料夾；操作走 `OperationDialog` |
| `app/ui/detail_page.py` | 動作列在「備份／還原」旁新增「快照」按鈕（32px，同風格），新增 `snapshot_requested` signal |
| `app/ui/main_window.py` | 接線 `_snapshots()`；系統 instance 停用；設定儲存後重建骨架 |
| `tests/test_workspace.py`（新增） | 骨架建立、推導、遷移 |
| `tests/test_snapshot.py`（新增） | 路徑對映、JSON 解析、保留策略、排除清單 |
| `tests/test_config.py` | 更新預設鍵／遷移斷言 |

- 不改 `backup_dialogs.py`、`distro_ops.py` 的全量備份流程，只讓 `backup_root` 指向 `<workspace>\backups`。
- 新按鈕沿用 32px 高、`refresh_cursor()`、系統 instance `setEnabled(False)` 慣例。

## 7. 配置與遷移

```json
{
  "workspace_root": "D:\\VirtualMachiles\\wsl",
  "distro_root": "D:\\VirtualMachiles\\wsl",        // 既有實例位置，暫不搬
  "backup_root": "D:\\VirtualMachiles\\wsl\\backups",
  "snapshot_root": "D:\\VirtualMachiles\\wsl\\snapshots",
  "snapshot_keep": { "last": 10, "daily": 7, "weekly": 4, "monthly": 6 }
}
```

- 遷移：`workspace_root` 缺少時，取 `backup_root` 的上層（名為 `backups` 時）否則取 `distro_root`；`snapshot_root` 缺少時取 `<workspace>\snapshots`。
- `distro_root`／`backup_root` 有值就保留（相容既有配置）；缺值才由 `workspace_root` 推導。
- 變更工作目錄時：只更新推導欄位並建立骨架，不搬動既有檔案；缺失目錄由 `ensure_workspace()` 建立。

## 8. 風險與對策

| 風險 | 對策 |
|---|---|
| 首次下載 restic 失敗（無網路／代理錯） | 明確錯誤 + 重試；不影響既有備份 |
| 備份期間寫入，快照非一致 | 對話框警示；可重複建立；必要時先停服務 |
| 首份快照久（rootfs 大） | `LONG_TIMEOUT`（3600s）+ `OperationDialog` 階段文字 |
| restic 回傳 3（部分檔案略過） | 視為警告，列出略過數，不中斷 |
| 還原覆蓋 `/` 造成系統壞掉 | 二次確認 + 可選先建快照 + 不刪除多餘檔案 |
| 工作目錄改到外接碟 | 僅支援磁碟機路徑；UNC 直接報錯 |
| 既有實例仍在工作目錄根層 | 本次只標註「尚未整理」，不搬移 |

## 9. 驗證

1. `python -m py_compile` 全部變更檔。
2. `python -m unittest discover -s tests -q`（現有 71 項 + 新增測試全過）。
3. 啟動 App 後確認骨架 `instances\`、`backups\`、`snapshots\` 自動建立；既有四個 instance 仍正常列出。
4. 對 `Ubuntu-26.04`（2.26 GB）連續 3 次快照（中間加／刪檔案）：
   - 第 2、3 份耗時與倉庫增量明顯小於首份；
   - 列表 3 筆、`restic check` 通過；
   - 單檔還原後 `stat` 的內容／權限／擁有者正確。
5. 離屏渲染詳情頁與快照對話框（淺色／深色）。
6. 清理測試倉庫；必要時刪除暫存目錄。

## 10. 回滾

- 動工前先建立 `_m7-snapshots\<timestamp>` 快照（檔案 + SHA256）。
- 回滾 = 還原 `config.py`、`main.py`、`settings_dialog.py`、`detail_page.py`、`main_window.py`、`tests/test_config.py`，刪除新增模組與測試。

## 11. 確認清單

- [ ] 同意目錄骨架：`<工作目錄>\instances\`、`backups\`、`snapshots\`（複數命名）。
- [ ] 同意既有 instance 暫不搬移，`distro_root` 保持現值，設定頁標註「尚未整理」。
- [ ] 同意快照後端用 restic，首次自動下載靜態二進位到 `snapshots\_tools\`。
- [ ] 同意倉庫位置 `snapshots\<instance>\repo`，設定可改根目錄。
- [ ] 同意預設保留策略 10/7/4/6（last/daily/weekly/monthly）。
- [ ] 同意預設排除 Docker 資料，建立快照時可勾選包含。
- [ ] 同意本輪只做 M7.1；M7.2（整機還原）另案確認。

確認後才動工。

## 12. 實作結果（2026-11-04）

- 單元測試：`115` 項全過（含新增 `test_workspace`／`test_snapshot` 與 `test_config` 遷移案例）。
- 骨架：`instances\`、`backups\`、`snapshots\_tools\` 已建立；既有 4 個 instance 維持原位，`distro_root` 未變更。
- restic `0.17.3`（26.5 MB）已自動下載到 `snapshots\_tools\restic-linux-amd64`，`restic version` 執行正常。
- 實機 3 次快照（`Ubuntu-26.04`）：
  - 首份：36,833 個檔案、1,382 MB、10.5 秒、倉庫 474.3 MB；
  - 第 2 份：新增 13.7 MB、倉庫 475.6 MB（+1.3 MB）；
  - 第 3 份：新增 15.5 MB、倉庫 477.1 MB（+1.5 MB）。
- 單檔還原 `/root/snapshot-probe.txt`：內容正確、`root:root 644`；`restic check` 無錯誤。
- 測試倉庫與暫存檔已清理，`snapshots` 目前只保留 `_tools`。
