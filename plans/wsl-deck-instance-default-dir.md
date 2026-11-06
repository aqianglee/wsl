# 計畫：instance 相關操作預設落在 instances 目錄

## 1. 現狀與問題

- 目前 `config.json` 的 `workspace_root` 與 `distro_root` 都是 `D:\VirtualMachiles\wsl`；`instances\` 已建立但為空。
- 新增 instance 的精靈與複製對話框，預設目標目錄皆為 `distro_root\<name>`：
  - [main_window.py](../wsl-deck/app/ui/main_window.py#L705-L710) → `NewInstanceWizard(distro_root, ...)`
  - [backup_dialogs.py](../wsl-deck/app/ui/backup_dialogs.py#L204-L226) → `CloneDialog` 以 `distro_root` 推導目標
- 因此新建／複製的 instance 資料夾會直接落在工作目錄根層，與既有 5 個 instance、`backups\`、`snapshots\` 混在一起。

## 2. 目標行為

| 操作 | 目前預設 | 調整後預設 |
| --- | --- | --- |
| 新增 instance（線上／tar／VHDX） | `distro_root\<name>` | `<workspace>\instances\<name>` |
| 複製 instance | `distro_root\<new_name>` | `<workspace>\instances\<new_name>` |
| `distro_root` 自訂為其他路徑 | `distro_root\<name>` | 維持 `distro_root\<name>` |
| 既有 instance | 不搬移 | 不搬移 |
| 備份／快照／複製暫存檔 | `backups\`、`snapshots\` | 維持不變（不屬於 instance 目錄） |

判定規則：`distro_root` 空白或等於 `workspace_root` 時，視為舊版工作目錄佈局（實例散落在根層），instance 操作預設改用 `<workspace>\instances`；若 `distro_root` 指向其他自訂路徑則沿用，避免影響把 VM 放在其他磁碟的使用者。

## 3. 修改清單

1. `wsl-deck/app/config.py`
   - 新增 `Config.instance_root()`：以 `normcase(abspath(...))` 比較 `distro_root` 與 `workspace_root`；空白或相同時回傳 `self.workspace().instances`，否則回傳 `self.resolve_path(distro_root)`。
2. `wsl-deck/app/ui/main_window.py`
   - `_new_instance` 改用 `self.config.instance_root()` 傳入 `NewInstanceWizard`。
3. `wsl-deck/app/ui/backup_dialogs.py`
   - `CloneDialog` 的預設根目錄與「瀏覽…」起點改用 `config.instance_root()`。
4. `wsl-deck/app/ui/settings_dialog.py`
   - 更新「尚未整理到 instances」提示：說明舊佈局下新建／複製會預設使用 `instances\`，既有 instance 不會被搬移。
5. `wsl-deck/tests/test_config.py`
   - 新增測試：`distro_root` 等於 `workspace_root` → 回傳 `instances`；自訂 `distro_root` → 原樣回傳；遷移後缺值情況 → 預設 `instances`。

不改動 `distro_ops.py`（建立／複製流程只接收目標路徑）、備份、還原、快照、刪除邏輯。

### 3.5 既有 instance 搬移（使用者已確認）

目前 5 個自建 instance 皆位於 `D:\VirtualMachiles\wsl\<name>`，目標為 `D:\VirtualMachiles\wsl\instances\<name>`：

| Instance | 目前 BasePath | 目標 |
| --- | --- | --- |
| Ubuntu-26.04 | `D:\VirtualMachiles\wsl\Ubuntu-26.04` | `D:\VirtualMachiles\wsl\instances\Ubuntu-26.04` |
| alms | `D:\VirtualMachiles\wsl\alms` | `D:\VirtualMachiles\wsl\instances\alms` |
| node22 | `D:\VirtualMachiles\wsl\node22` | `D:\VirtualMachiles\wsl\instances\node22` |
| ubuntu | `D:\VirtualMachiles\wsl\ubuntu` | `D:\VirtualMachiles\wsl\instances\ubuntu` |
| wsl-mysql | `D:\VirtualMachiles\wsl\wsl-mysql` | `D:\VirtualMachiles\wsl\instances\wsl-mysql` |

`docker-desktop`（系統 instance，位於 C 槽）不搬移。

執行步驟：

1. 確認 5 個 instance 均為 `Stopped`，必要時 `wsl.exe --shutdown`。
2. 對每個 instance 執行 `wsl.exe --manage <name> --move "D:\VirtualMachiles\wsl\instances\<name>"`。
3. `wsl.exe --list --verbose` 與註冊表 BasePath 驗證搬移結果。
4. `config.json` 的 `distro_root` 改為 `D:\VirtualMachiles\wsl\instances`，與實際佈局一致。
5. 若中途失敗，立即以 `wsl.exe --manage <name> --move "D:\VirtualMachiles\wsl\<name>"` 移回。

## 4. 驗證

- `python -m unittest discover -s tests -q`：既有 129 項加上新增案例全數通過。
- 啟動 App 冒煙：
  - 「+ 新增 Instance」選 Ubuntu，輸入名稱後安裝目錄顯示 `D:\VirtualMachiles\wsl\instances\<name>`。
  - 既有 instance 的「複製」對話框目標目錄同樣落在 `instances\`。
- `git diff` 僅包含上述檔案。
- `wsl --list` 與既有 5 個 instance 目錄不受影響。

## 5. 風險與回滾

| 風險 | 處理 |
| --- | --- |
| 使用者刻意把 `distro_root` 設為工作目錄根 | 會被視為舊佈局而改走 `instances\`（符合本次需求）；改回自訂路徑即可恢復 |
| 路徑字串大小寫／斜線差異導致誤判 | 以 `normcase(abspath(...))` 正規化後比較 |
| 來源檔案選擇器起點跟著變成 `instances\` | 僅影響瀏覽起點，可再依需求改指 `backups\` |

回滾：還原本次 commit 涉及的 5 個檔案。

## 6. 已確認事項

- [x] 「`distro_root` 等於 `workspace_root` 視為舊佈局，預設自動改用 `instances`」的判定規則。
- [x] 既有 5 個 instance 一併搬入 `instances\`（使用者確認）。
- [x] 備份與快照仍使用 `backups\`、`snapshots\`。

## 7. 執行結果（2026-11-04）

- `Config.instance_root()` 已加入；新增精靈與複製對話框改用此預設根目錄。
- 設定頁提示已更新；`config.json` 的 `distro_root` 已改為 `D:\VirtualMachiles\wsl\instances`。
- 單元測試：`135` 項全過（原 129 項 + 新增案例）。
- 5 個 instance 已以 `wsl --manage --move` 搬入 `instances\`，BasePath 驗證正確，狀態皆為 `Stopped`；`docker-desktop` 未搬移。
- 搬移後舊目錄僅剩空資料夾（`Ubuntu-26.04` 內含 `shortcut.ico`），未自動刪除，待使用者確認後手動清理。
- 註：目前已安裝的 `WSL Deck.exe` 仍為舊版程式，需重新建置／安裝後才會套用本次程式變更。
