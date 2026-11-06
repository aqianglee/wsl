# WSL Deck：兩個實例 IP 相同、外部機器連不進來 — 診斷與處置計畫

> 狀態：**待確認**
> 日期：2026-11-06
> 範圍：`wsl-mysql`（13306→3306，已套用）與 `wsl-tomcat9`（無規則）

## 1. 現象

| 截圖 | 觀察 |
|------|------|
| wsl-mysql | 目前 IP `192.168.163.232`；規則 `13306→3306` 已套用、`33060→33060` 待套用 |
| wsl-tomcat9 | 目前 IP `192.168.163.232`（與上者相同）；「尚無規則」 |

使用者回報：兩台 IP 相同，且外部機器連不進來。

## 2. 已核實事實（2026-11-06 實機指令）

| 項目 | 結果 | 指令 |
|------|------|------|
| `.wslconfig` | 不存在 → 預設 NAT 模式 | `Test-Path $env:USERPROFILE\.wslconfig` |
| 兩個實例的網路命名空間 | **同一個** `net:[4026531833]` | `wsl -d <name> -- readlink /proc/self/ns/net` |
| 兩個實例的 IP | 皆 `192.168.163.232/20`（eth0） | `wsl -d <name> -- ip -4 addr show` |
| Windows 端 WSL 虛擬網卡 | `vEthernet (WSL)` = `192.168.160.1/20`（涵蓋 192.168.160.0–192.168.175.255） | `Get-NetIPAddress` |
| portproxy | 只有 `0.0.0.0:13306 → 192.168.163.232:3306` | `netsh interface portproxy show v4tov4` |
| 防火牆規則 | `WSL Deck wsl-mysql 13306`：`Profile=Private`、`RemoteAddr=LocalSubnet`、Enable | `Get-NetFirewallRule` |
| Windows 網路設定檔 | `以太网 / Pisoft 4` = **Public**；本機 LAN IP = `192.168.1.6/24` | `Get-NetConnectionProfile` |
| 主機連 WSL 的 3306 | **失敗** `TCP connect to 192.168.163.232:3306 failed` | `Test-NetConnection 192.168.163.232 -Port 3306` |
| 主機連轉發埠 | `127.0.0.1:13306` 成功、`192.168.1.6:13306` 成功（監聽正常） | `Test-NetConnection` |
| wsl-mysql 內 mysqld | 只監聽 `127.0.0.1:3306`、`127.0.0.1:33060`；行程 PID 296 自 **Nov04** 啟動 | `ss -tln`、`ps -ef` |
| mysqld 設定 | `bind-address = 0.0.0.0`，檔案改於 **Nov 6 10:01**（晚於行程啟動） | `grep bind-address /etc/mysql/mysql.conf.d/mysqld.cnf` |
| wsl-tomcat9 內服務 | 無 8080 監聽、未安裝 Tomcat（無 `/opt/tomcat*`、`/usr/share/tomcat9`） | `ss -tln`、`ls` |

## 3. 根因判定

1. **兩個 IP 相同不是程式 bug**：本機 WSL 的兩個發行版共用同一個網路命名空間（inode `4026531833`），因此 `hostname -I` 必然回傳同一個位址；`192.168.163.232` 也確實落在 WSL 虛擬網卡 `192.168.160.1/20` 的子網內。WSL Deck 只是如實顯示。
2. **外部連不進的主因（後端斷鏈）**：`mysqld` 目前只綁 `127.0.0.1:3306`。portproxy 把 `13306` 轉到 `192.168.163.232:3306`，但該位址上沒有服務在聽，連線直接被拒。設定檔已改為 `0.0.0.0`，但行程是 11/04 啟動、沒重啟，**設定與執行狀態不一致**。連 Windows 本機直連 WSL IP 都失敗，可證與外部網路無關。
3. **外部連不進的次因（防火牆）**：規則只開 `profile=private`，但目前 `以太网` 的網路設定檔是 `Public`，入站被防火牆阻擋；即使後端修好，同網段其他機器仍連不上。
4. **wsl-tomcat9 完全沒有可連的目標**：沒有規則、沒有 Tomcat、沒有 8080 監聽；`33060` 那條則尚未套用。

## 4. Phase 0：環境修復（不涉程式碼）

> 這一步會動到實例內的系統服務與 Windows 網路設定檔，需逐項確認。

| # | 動作 | 驗證 |
|---|------|------|
| 0-1 | `wsl -d wsl-mysql -u root -- systemctl restart mysql` | `ss -tln` 出現 `0.0.0.0:3306` |
| 0-2 | 主機測後端 | `Test-NetConnection 192.168.163.232 -Port 3306` 為 True |
| 0-3 | 讓外部可入站：把 `以太网` 改 Private，**或**在 WSL Deck 支援下加開 Public 規則 | `Get-NetConnectionProfile`；`Test-NetConnection <Windows LAN IP> -Port 13306`（從另一台機器） |
| 0-4 | `33060` 規則按「立即套用」（先確認 33060 是否真要對外，MySQL X Protocol 通常不必） | 規則狀態變「已套用」 |
| 0-5 | `wsl-tomcat9`：確認是否要裝 Tomcat；要就安裝＋新增 `8080→8080`（或 `18080→8080`）規則，不要就移除對它的期待 | `ss -tln` 有 8080；規則已套用 |

## 5. Phase 1：程式改進（可選，需另行確認）

| 編號 | 問題 | 改法 | 檔案 |
|------|------|------|------|
| P1 | 「已套用」只比對 portproxy 條目，不驗證後端 | 新增 `probe_backend(ip, port, timeout=2)`；`rule_status` 多一個「後端不可達」狀態，UI 以橘字顯示並提示「實例內服務未監聽在此位址」 | `app/network.py`、`app/ui/network_panel.py`、`tests/test_network.py` |
| P2 | 防火牆規則固定 `profile=private`，Public 網路必失敗 | 規則對話框加「同時開放公用網路（Public）」勾選（預設關）；未勾且目前網路為 Public 時，套用後給警告 | `app/ui/rule_dialog.py`、`app/admin.py`、`app/network.py` |
| P3 | 多實例共用 IP 造成誤解 | 詳情頁 IP 欄加註「與其他執行中實例共用（WSL 單一網路命名空間）」 | `app/ui/detail_page.py` |
| P4 | 掃描端口結果未標註跨實例共用 | 掃描結果旁加一行說明：同 IP 下無法區分來源實例 | `app/ui/network_panel.py` |

不做：不改 `.wslconfig` 的 `networkingMode`、不代管實例內服務（不安裝／重啟 MySQL、Tomcat）、不自動改 Windows 網路設定檔。

## 6. 測試

| 測試 | 覆蓋 |
|------|------|
| `tests/test_network.py` 擴充 | `probe_backend` 成功／逾時／拒絕；`rule_status` 新狀態分支；public 規則的 `build_admin_job` 輸出 |
| 手動 | Phase 0 每列的驗證指令；離屏 UI 檢查新欄位與狀態顏色 |

## 7. 驗收

1. `192.168.163.232:3306` 從 Windows 可連；`13306` 從同網段另一台機器可連（Private 或加開 Public 後）。
2. 停掉 mysqld 後，WSL Deck 規則狀態顯示「後端不可達」而非「已套用」。
3. Public 網路下勾「同時開放 Public」並套用後，外部機器可連；不勾時有明確警告。
4. `wsl-tomcat9` 與 `wsl-mysql` 詳情頁 IP 相同但不再被誤認為異常。

## 8. 風險與回滾

| 風險 | 對策 |
|------|------|
| 重啟 MySQL 造成短暫斷線 | 先確認無長交易；必要時 `systemctl restart` 後立即驗證 |
| 開放 Public 擴大攻擊面 | 預設關閉；僅在 `remoteip=localsubnet` 下開放，並在 UI 明示 |
| 後端探測增加延遲 | 2 秒逾時、背景執行緒，不阻塞 UI |
| 改壞程式 | 沿用既有快照／備份流程 |

## 9. 確認清單

- [ ] 同意先做 Phase 0（含重啟 `wsl-mysql` 的 MySQL 服務）
- [ ] 網路設定檔：改 Private，還是保留 Public 並由程式加開 Public 規則？
- [ ] `33060` 是否要對外？（建議不要）
- [ ] `wsl-tomcat9` 要安裝 Tomcat 還是先擱置？
- [ ] Phase 1 要全部做、只做 P1+P2，還是暫不改程式？

確認後才動工。
