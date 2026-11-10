# 終端標題自訂

> 狀態：**已完成**

## 1. 目標

從 WSL Deck 開啟 Windows Terminal 時，分頁／視窗標題顯示 `user@instanceName`，方便同時開多個 Instance 時區分。

## 2. 已核實事實

- 原本實作在 [shell.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/shell.py#L12-L19)：`wt.exe wsl.exe -d <distro>`，未指定標題。
- Windows Terminal `1.24.12741.0` 的 `new-tab` 支援 `--title <text>` 與 `--suppressApplicationTitle`；後者阻止 bash PS1（`\e]0;...\a`）覆寫標題，否則標題會立刻變回 `user@host: cwd`。
- Instance 的登入使用者需向 WSL 查詢（`wsl -d <name> -- whoami`），可能造成 UI 阻塞，因此沿用既有 `_run_task` 背景執行。
- 無 `wt.exe` 的 fallback（`wsl.exe -d <distro>` + `CREATE_NEW_CONSOLE`）不改標題。

## 3. 變更內容

| 檔案 | 變更 |
|------|------|
| [shell.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/shell.py) | 新增 `terminal_user(distro_name)`：以 `run_wsl` 查 `whoami`，失敗時記 warning 並回傳空字串。新增 `terminal_args(distro_name, user)` 純函式組出 `wt.exe new-tab --title "<user>@<name>" --suppressApplicationTitle wsl.exe -d <name>`；查不到使用者時標題退為 `<name>`。 |
| [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py#L1576-L1589) | `_open_terminal()` 改為先以 `_run_task` 背景查使用者，再由 `_launch_terminal()` 開終端；失敗仍顯示原本的錯誤提示。 |
| [test_shell.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/tests/test_shell.py) | 新增 3 項測試覆蓋 `terminal_args` 的標題組合與 wsl 參數。 |

呼叫端（卡片牆／表格／詳情頁）與 UI 均未改動。

## 4. 驗證

1. `py_compile app\shell.py app\ui\main_window.py`：通過。
2. `unittest discover`：162 項全綠（含新增 3 項 `terminal_args` 測試）。
3. 手動執行 `wt.exe -w -1 new-tab --title "kyo@ubuntu" --suppressApplicationTitle wsl.exe -d ubuntu`，`Get-Process WindowsTerminal` 的 `MainWindowTitle` 顯示 `kyo@ubuntu`（未抑制時為 `kyo@KyoBook2HP`），確認標題固定不被 shell 覆寫。

## 5. 已確認決策

- 標題格式：`user@instanceName`（使用者由 WSL `whoami` 取得，取不到時只用 instance 名稱）。
- 使用 `--suppressApplicationTitle`：終端內 `cd` 後標題不再改變，以保證永遠可辨識 Instance。
