# 故障排查

> 用法：按現象分組查表。每一列都給「可能原因 → 怎麼確認 → 怎麼處理」，並附程式位置。
> 排查前先看日誌：`logs\wsl-deck.log`（開發期在應用根目錄，打包後在 exe 同層）。

---

## 0. 先做這三件事

```powershell
# 1) 看日誌最後 50 行
Get-Content .\logs\wsl-deck.log -Tail 50

# 2) 確認 WSL 本身正常
wsl.exe --list --verbose

# 3) 確認設定檔沒壞（壞了程式會在啟動時彈「配置錯誤」並退出）
Get-Content .\config.json -Raw | ConvertFrom-Json | Out-Null
```

日誌同時會鏡射到 UI 底部的「日誌」抽屜（錯誤自動展開）。兩者內容一樣，差別是：
- 檔案日誌有級別（`INFO`／`WARNING`／`ERROR`）與模組名（[logbus.py:31-35](../../wsl-deck/app/logbus.py#L31-L35)）；
- UI 抽屜只有 `HH:MM:SS 訊息`（[logbus.py:37-40](../../wsl-deck/app/logbus.py#L37-L40)）；
- 日誌級別固定 `INFO`，`logger.debug()` 不會出現在任何地方（例如單實例的喚醒記錄，[single_instance.py:67](../../wsl-deck/app/single_instance.py#L67)）。

---

## 1. 啟動類

| 現象 | 可能原因 | 怎麼確認 | 處理 |
|------|---------|---------|------|
| 視窗一閃就消失／根本沒出現 | 從 AI 沙箱、CI 或排程命令啟動，子進程在命令結束時被回收 | 改從 PowerShell 直接跑 `pythonw main.py` | 由使用者自己啟動；這不是 bug |
| 啟動後毫無反應，也沒有日誌 | `pythonw.exe` 沒有 stdout，例外被吞掉 | 改用 `python.exe main.py` 跑一次看 traceback | 先修例外；或暫時把 spec 的 `console` 設 `True` 除錯 |
| 第二次啟動沒有新視窗 | 單實例機制：第一個實例被喚醒 | 工作管理員只有一個 `WSL Deck.exe` | 正常行為（[single_instance.py:42-52](../../wsl-deck/app/single_instance.py#L42-L52)） |
| 托盤圖標不見，關窗後程式還在 | `close_to_tray=True` 且系統托盤可用 | 工作列右下角「隱藏的圖標」 | 托盤選「結束」，或把設定改回關窗即退出（[main_window.py:470-490](../../wsl-deck/app/ui/main_window.py#L470-L490)） |
| 關窗後直接退出，托盤也沒了 | `QSystemTrayIcon.isSystemTrayAvailable()` 為 False，或改過設定 | 設定→關窗縮托盤 | 無托盤的環境只能關窗退出（[tray.py:20-25](../../wsl-deck/app/ui/tray.py#L20-L25)） |
| 啟動彈「配置錯誤」並退出 | `config.json` 格式／型別／範圍不合法 | 看彈窗文字與 `config.py` 的 `_validate` | 用 `config.json.pre-m5.bak` 還原，或刪掉讓程式重建（[config.py:99-115](../../wsl-deck/app/config.py#L99-L115)） |
| 啟動後提示工作目錄建立失敗 | 設定的路徑不存在／沒有寫入權限 | 日誌 `建立工作目錄骨架失敗` | 設定→改工作目錄→「套用工作目錄骨架」（[main.py:51-54](../../wsl-deck/main.py#L51-L54)） |
| 設定改了重啟後又變回去 | 寫入失敗被回滾 | 日誌 `設定未儲存` | 檢查 `config.json` 是否唯讀／被佔用 |
| 開機自啟勾了沒效果 | 開發期 `is_supported()` 永遠 False，只有 exe 才寫註冊表 | 設定裡該項是否可用／灰掉 | 用打包後的 exe；或手動確認 `HKCU\...\Run` 的 `WSL Deck` 值（[autostart.py:16-44](../../wsl-deck/app/autostart.py#L16-L44)） |
| 舊版升級後設定跑掉 | 舊鍵 `preview_commands`／`minimize_to_tray` 被遷移 | 檢查是否生成 `config.json.pre-m5.bak` | 遷移是預期行為，備份檔可回溯（[config.py:67-71](../../wsl-deck/app/config.py#L67-L71)） |

---

## 2. WSL 資料類

| 現象 | 可能原因 | 怎麼確認 | 處理 |
|------|---------|---------|------|
| 某個實例狀態顯示 `Unknown` | 它只在註冊表存在，`wsl --list` 沒列出（例如已損壞或未初始化） | `wsl.exe --list --verbose` 對照 | 程式以註冊表為主合併（[wsl.py:218-235](../../wsl-deck/app/wsl.py#L218-L235)）；必要時用 `wsl --unregister` 清掉 |
| 狀態顯示英文／中文混雜 | `wsl.exe` 輸出被系統語言本地化 | 看 `parse_list_output` 的分詞結果 | `running` 用中英關鍵字比對（[wsl.py:39-43](../../wsl-deck/app/wsl.py#L39-L43)）；新增語言要補關鍵字 |
| 磁碟大小一直是 0 | `BasePath` 空白、目錄不存在、或找不到 `*.vhdx` | 看詳情頁「安裝路徑」是否空白 | 確認註冊表 `BasePath`；`_locate_vhdx` 會先找 `*.vhdx` 再退回 `ext4.vhdx`（[wsl.py:176-189](../../wsl-deck/app/wsl.py#L176-L189)） |
| IP 顯示「未取得」 | 實例沒在跑，或 `hostname -I` 只有 IPv6 | `wsl -d <name> -- hostname -I` | 先啟動；程式只取第一個非 127 的 IPv4（[wsl.py:249-255](../../wsl-deck/app/wsl.py#L249-L255)） |
| 清單少了一個實例 | 名稱重複／讀註冊表項目失敗 | 日誌 `讀取註冊表項目失敗` | 檢查 `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss` 權限 |
| 系統實例可以操作（不該） | 名稱前綴不在 `system_instances` 清單 | 看 `config.json` 的 `system_instances` | 設定→加前綴；判定在 [wsl.py:244-246](../../wsl-deck/app/wsl.py#L244-L246) |
| 讀清單失敗，狀態列顯示「無法讀取 WSL 狀態」 | `wsl.exe` 不存在／逾時／非零退出 | 日誌 `讀取 WSL 狀態失敗` | 確認 WSL 已啟用；逾時預設 60 秒（[wsl.py:70-95](../../wsl-deck/app/wsl.py#L70-L95)） |

---

## 3. 備份、還原、快照類

| 現象 | 可能原因 | 怎麼確認 | 處理 |
|------|---------|---------|------|
| VHDX 備份失敗：`sharing violation`／檔案被佔用 | VHDX 匯出必須**所有 WSL 實例都關閉**，只 terminate 目標實例不夠 | 備份對話框的提示；日誌是否有 `正在關閉 WSL 子系統` | 程式在 `vhd=True` 時會先 `wsl --shutdown`（[distro_ops.py:178-180](../../wsl-deck/app/distro_ops.py#L178-L180)）；接受這個副作用再重試 |
| TAR 備份也要關機嗎 | 不用，TAR 可在執行中匯出 | 看格式下拉選「TAR」 | 想避免中斷就用 TAR，代價是檔案較大（[distro_ops.py:183-186](../../wsl-deck/app/distro_ops.py#L183-L186)） |
| 還原後安裝目錄整個不見 | `wsl --unregister` 會刪除整個安裝資料夾 | 日誌 `正在移除現有 instance` | 這是設計行為；還原流程會重建目錄再匯入（[distro_ops.py:221-227](../../wsl-deck/app/distro_ops.py#L221-L227)） |
| 還原失敗後實例消失 | 匯入失敗時會嘗試用「現況備份」回滾 | 日誌 `還原失敗，正在用現況備份回復` | 若沒勾「先備份目前狀態」，就沒有回滾來源（[distro_ops.py:242-253](../../wsl-deck/app/distro_ops.py#L242-L253)） |
| 磁盤空間不足 | 匯入／匯出都需要額外空間（VHDX 約 1.0 倍、TAR 約 2.0 倍） | 錯誤訊息會寫「需要約 X，可用 Y」 | 換目標磁碟或先清理（[distro_ops.py:121-128](../../wsl-deck/app/distro_ops.py#L121-L128)） |
| 第一次按「快照」卡很久 | 首次要下載 restic（約 25 MB）＋建立全量基線 | 日誌 `正在下載 restic`／`正在掃描並寫入快照（首次較久）` | 屬正常；後續是增量（[snapshot.py:183-196](../../wsl-deck/app/snapshot.py#L183-L196)、[snapshot.py:463](../../wsl-deck/app/snapshot.py#L463)） |
| restic 下載失敗 | 沒有 `curl.exe`、代理未設、GitHub 不可達 | 日誌 `下載 restic 失敗` | 設定全域代理；或手動放 `snapshots\_tools\restic-linux-amd64`（[snapshot.py:138-168](../../wsl-deck/app/snapshot.py#L138-L168)） |
| 還原 `/` 時報 `read-only file system` 並整體失敗 | restic 對 WSL 的只讀掛載做 `lchown`，只要一個錯誤就退出碼 1 | 錯誤明細裡是不是只有 `ignoring error for ... read-only file system` | 程式已排除固定路徑並動態讀 `/proc/mounts`（[snapshot.py:54-60](../../wsl-deck/app/snapshot.py#L54-L60)、[snapshot.py:361-368](../../wsl-deck/app/snapshot.py#L361-L368)）；若仍出現非只讀錯誤，就是真失敗 |
| 快照倉庫不支援網路路徑 | `windows_to_wsl_path` 拒絕 UNC | 路徑是否 `\\server\share` | 改用磁碟機路徑（[snapshot.py:104-114](../../wsl-deck/app/snapshot.py#L104-L114)） |
| 保留策略全設 0，清理時報錯 | restic 至少要保留一份 | 設定→保留策略 | 至少把一項設為 >0（[snapshot.py:305-314](../../wsl-deck/app/snapshot.py#L305-L314)） |
| 快照列表不見了，倉庫還在 | `repo.pass` 遺失或內容空白 | 看 `snapshots\<name>\repo.pass` 是否存在 | **不要刪**；密碼檔沒了就無法解開舊快照（[snapshot.py:126-135](../../wsl-deck/app/snapshot.py#L126-L135)） |
| 掃描端口彈 `unexpected keyword argument 'stage'` | 歷史 bug：`_run_operation` 無條件注入 `stage`，但該函式不接受 | 錯誤訊息 | 已由 `_accepts_stage()` 修好（[workers.py:14-23](../../wsl-deck/app/ui/workers.py#L14-L23)）；若再現，檢查新函式簽名是否漏了 `stage=None` |
| 還原檔案後多了不該有的檔案 | restic `restore` 只覆蓋、不刪除多餘檔案 | — | 屬設計；要「完全回到快照狀態」只能用整機覆蓋式還原 |

---

## 4. 網路與防火牆類

| 現象 | 可能原因 | 怎麼確認 | 處理 |
|------|---------|---------|------|
| 規則一直顯示「待啟動」 | 目標實例沒在跑 | 狀態列與詳情頁狀態 | 先啟動實例；狀態判定在 [network.py:117-136](../../wsl-deck/app/network.py#L117-L136) |
| 按「立即套用」後仍「待套用」 | 使用者取消了 UAC，或端口被其他程式佔用 | 日誌 `已取消管理員授權`／`已被其他程式佔用` | 重新按並允許 UAC；換一個 Windows 端口（[network.py:231-235](../../wsl-deck/app/network.py#L231-L235)） |
| 本機能連，同網段其他裝置連不上 | Windows 網路設定檔是 **Public**，而防火牆規則只開 `profile=private` | `Get-NetConnectionProfile` | 把該網路改為 Private，或自行加一條 Public 規則（[admin.py:97-107](../../wsl-deck/app/admin.py#L97-L107)） |
| portproxy 顯示正確但仍連不上 | WSL 重啟後 distro IP 變了，轉發還指向舊 IP | `netsh interface portproxy show v4tov4` 對照目前 IP | 重新按「立即套用」（會先刪舊再加新） |
| 套用時 netsh 回一堆錯誤，但最後成功 | 刪除不存在的 portproxy／防火牆規則會回非零 | 日誌是 `warning` 還是 `error` | 屬正常清理 warning（[admin.py:62-80](../../wsl-deck/app/admin.py#L62-L80)） |
| UAC 視窗沒出現，直接失敗 | `powershell.exe` 被策略禁用／逾時 | 日誌 `等待管理員授權逾時`／`找不到 powershell.exe` | 檢查端點安全策略；逾時 300 秒（[admin.py:163-183](../../wsl-deck/app/admin.py#L163-L183)） |
| UAC 取消後程式卡住 | 子進程退出碼 1223、沒有 result.json | 日誌 `未取得管理員授權` | 正常返回 `denied=True`，不應卡住；若卡住看是否 `-Wait` 未返回（[admin.py:152-160](../../wsl-deck/app/admin.py#L152-L160)） |
| 同一端口兩條規則 | 規則校驗只在 UI／`validate_rule` 層，`config.json` 可能被手改 | `config.json` 的 `port_forwards` | 啟動時 `_validate` 會擋重複端口（[config.py:324-330](../../wsl-deck/app/config.py#L324-L330)） |
| 掃描監聽端口為空 | 實例沒跑、`ss`／`netstat` 都不存在、或沒有 LISTEN | `wsl -d <name> -- sh -c "ss -tln \|\| netstat -tln"` | 掃描前會詢問是否啟動；解析只收 `LISTEN` 行（[network.py:67-90](../../wsl-deck/app/network.py#L67-L90)） |

### 快速診斷指令

```powershell
# 目前轉發
netsh interface portproxy show v4tov4

# 目前網路設定檔（Private / Public）
Get-NetConnectionProfile | Select-Object Name, NetworkCategory

# 防火牆規則（名稱前綴 WSL Deck）
netsh advfirewall firewall show rule name=all | Select-String "WSL Deck"

# distro 目前 IP
wsl.exe -d <name> -- hostname -I
```

---

## 5. 打包類

| 現象 | 可能原因 | 怎麼確認 | 處理 |
|------|---------|---------|------|
| PowerShell 輸出中文變亂碼（`瀹屾垚锛?`） | `.ps1` 存成 UTF-8 **無 BOM**，PowerShell 5.1 按系統 ANSI（GBK）解碼 | 用十六進位看首字節是否 `EF BB BF` | 把腳本另存為 **UTF-8 with BOM**（[plans/wsl-deck-ps1-encoding-fix.md](../../plans/wsl-deck-ps1-encoding-fix.md)） |
| `build.ps1` 明明成功卻報失敗 | PowerShell 5.1 把 PyInstaller 的 stderr 當終止錯誤 | 看 `build/pyinstaller.log` | 腳本已把 `$ErrorActionPreference` 設 `Continue` 並改判 exit code（[build.ps1:8-22](../../wsl-deck/build.ps1#L8-L22)） |
| 打包後 exe 一閃就退 | `console=False`，看不到 traceback | 從 PowerShell 啟動仍無輸出 | 暫時把 spec 的 `console` 改 `True` 重建除錯；或看 `logs\wsl-deck.log` |
| 打包後圖示不見 | `datas` 沒帶到，或 `_MEIPASS` 路徑不對 | 檢查 `dist\WSL Deck\_internal\assets\wsl-deck-icon.ico` | `app_icon.py` 會回退到現畫圖示；要真圖示就確認 spec 的 `datas`（[WSL Deck.spec:7](../../wsl-deck/WSL%20Deck.spec#L7)、[app_icon.py:17-20](../../wsl-deck/app/ui/app_icon.py#L17-L20)） |
| 打包後「立即套用」失敗，開發期正常 | 提權子進程入口不一致：凍結後必須走 `exe --admin-job` | 日誌 `找不到模組`／`unrecognized arguments` | 確認 [main.py:13-15](../../wsl-deck/main.py#L13-L15) 與 [admin.py:135-141](../../wsl-deck/app/admin.py#L135-L141) 同步 |
| 改了版本號後 `build-installer.ps1` 報找不到產物 | 腳本第 15 行把 `1.0.0` 寫死 | 看 `dist\` 下實際檔名 | 同步改 [build-installer.ps1:15](../../wsl-deck/build-installer.ps1#L15) |
| 安裝包帶著開發機路徑 | `build.ps1` 把應用根目錄的 `config.json` 複製進 `dist`，安裝包再帶出去 | 解壓安裝包看 `config.json` 的 `workspace_root` | 發布前刪掉 `dist\WSL Deck\config.json`，或改用 zip 的預設排除行為（[build.ps1:29-32](../../wsl-deck/build.ps1#L29-L32)） |
| 卸載後使用者的實例也被刪 | 不應該；`[UninstallDelete]` 只刪 `{app}\logs` | 檢查 `installer/WSL Deck.iss` 的 `[UninstallDelete]` | 若被改過就還原（[WSL Deck.iss:46-47](../../wsl-deck/installer/WSL%20Deck.iss#L46-L47)） |

---

## 6. 文件沒寫到的情況怎麼辦

1. 先確認 `logs\wsl-deck.log` 有沒有對應的 `ERROR`／`WARNING`；本專案幾乎每個失敗路徑都有 log。
2. 用 `Select-String` 找錯誤文案出處：

```powershell
Select-String -Path app\*.py,app\ui\*.py -Pattern "錯誤文案片段"
```

3. 若是 `wsl.exe` 的原始錯誤，直接手動重跑同一條命令（日誌會印出 `執行：...`，見 [distro_ops.py:45-47](../../wsl-deck/app/distro_ops.py#L45-L47)）。
4. 若懷疑是測試沒覆蓋到的 UI 流程，先補一個純函式測試（本專案 135 項測試全在 `tests/`，沒有 UI 測試）。
