# MySQL + Tomcat 兩台 WSL 端到端驗收方案（M2／M3／M4）

> 版本：2026-11-02
> 範圍：從「新增兩個 WSL instance」開始，到在各自 distro 內安裝 MySQL／Tomcat，最後用 WSL Deck M4 網路規則把服務開放到 Windows。
> 目標：把 M2（卡片／詳情／啟停／輪詢）、M3（新增／備份／刪除）、M4（網路規則／UAC／重套）串成一條完整驗收流程。
> 參考文件：[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)、[wsl-deck-m4-acceptance.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m4-acceptance.md)

---

## 0. 部署規格（建議值，驗收前確認）

| 項目 | 建議值 | 備註 |
|------|--------|------|
| 來源映像 | `D:\VirtualMachiles\wsl\backups\ubuntu\ubuntu.vhdx` | Ubuntu 20.04.6；匯入較快，不需下載 |
| MySQL instance | `wsl-mysql` | 安裝目錄 `D:\VirtualMachiles\wsl\wsl-mysql` |
| Tomcat instance | `wsl-tomcat` | 安裝目錄 `D:\VirtualMachiles\wsl\wsl-tomcat` |
| MySQL 版本 | Ubuntu 套件 `mysql-server`（8.0.x） | 20.04 預設版本 |
| Tomcat 版本 | Ubuntu 套件 `tomcat9`（Tomcat 9 + OpenJDK 11） | 20.04 預設版本 |
| MySQL distro 端口 | 3306 | 只在 distro 內監聽 |
| Tomcat distro 端口 | 8080 | Tomcat 預設 |
| MySQL Windows 端口 | 13306 → distro 3306 | 避開 Windows 既有 3306 |
| Tomcat Windows 端口 | 18080 → distro 8080 | 避開常見 8080 |
| MySQL 對外 | 僅 Windows 本機（允許 LAN 不勾選） | 降低資料庫暴露風險 |
| Tomcat 對外 | 允許 LAN 勾選 | 方便其他裝置驗收 |
| MySQL app 帳號 | `appuser`／`<APP_PASSWORD>` | 密碼由部署者填入，不寫入文件 |
| MySQL app DB | `appdb` | 驗收用 |
| MySQL root | 保持 Ubuntu 預設 `auth_socket`，用 `sudo mysql` 管理 | 不另設 root 密碼 |

> 若 Windows 的 13306 或 18080 也被佔用，改用 23306／28080，並同步調整本文所有命令。

### 重要限制

- 基底是 **Ubuntu 20.04.6 LTS（Focal）**，已結束標準支援；若 `apt update` 出現 404，需把來源切到 `old-releases.ubuntu.com`（見 3.1）。
- 啟用 systemd 需執行 `wsl --shutdown`，會同時停止所有 distro（含 `docker-desktop`）。
- 跨裝置 LAN 訪問需要 Windows 網路設定檔為 **Private**；Public 時其他裝置會被 M4 的 private 防火牆規則阻擋。
- 本文只驗收「服務可安裝、可啟動、可從 Windows 訪問」；不做 MySQL 生產級安全加固、不做 Tomcat 應用部署、不做 M5 托盤／開機自啟。

---

## 1. 前置條件

### 1.1 環境

- WSL 3.x，支援 `wsl --import --vhd`、systemd、`wsl --shutdown`。
- D 槽可用空間 ≥ 20 GB（兩個 instance 各約 3 GB，加套件與日誌）。
- 具備 UAC 管理員授權（M4 套用網路規則會跳）。
- Windows 端 13306、18080 未被佔用：

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 13306,18080 } |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

預期：無輸出。

### 1.2 程式與自動測試

```powershell
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：`Ran 42 tests ... OK`。

### 1.3 啟動 GUI

```powershell
d:\VirtualMachiles\wsl\wsl-deck\.venv\Scripts\pythonw.exe d:\VirtualMachiles\wsl\wsl-deck\main.py
```

---

## 2. 階段 A：M2 基線檢查

在新增任何 instance 前，先確認目前 UI 正常。

| 編號 | 操作 | 預期 |
|------|------|------|
| A1 | 觀察卡片牆 | 現有 instance 以網格排列；縮放視窗會重新換行，不會全部擠成一行 |
| A2 | 觀察 `docker-desktop` 卡片 | 顯示禁止標識；四顆按鈕淡化禁用；點卡片可進詳情頁但動作全禁用 |
| A3 | 點任一非系統卡片 | 進入詳情頁；顯示狀態、WSL 版本、磁盤大小、IP、安裝路徑 |
| A4 | 詳情頁按「終端」 | 開啟該 distro 的終端 |
| A5 | 詳情頁按「Linux 檔案」「安裝目錄」 | 開啟 `\\wsl$\<name>\` 與 Windows BasePath |
| A6 | 卡片右上啟動／終止圖標 | 綠／紅圖標切換；點擊後 10 秒內卡片狀態更新 |
| A7 | 外部執行 `wsl --terminate ubuntu` | GUI 10 秒內顯示已停止 |

> 不在本階段做破壞性操作；只確認 M2 功能沒有回歸。

---

## 3. 階段 B：M3 新增兩台 instance

### 3.1 建立 `wsl-mysql`

1. GUI 按「+ 新增 Instance」。
2. 來源選 **VHDX**。
3. 檔案選 `D:\VirtualMachiles\wsl\backups\ubuntu\ubuntu.vhdx`。
4. 名稱：`wsl-mysql`。
5. 安裝目錄：`D:\VirtualMachiles\wsl\wsl-mysql`。
6. 按「開始安裝」，等待模態進度完成。
7. 完成後應自動進入 `wsl-mysql` 詳情頁。

### 3.2 建立 `wsl-tomcat`

重複上述步驟，名稱 `wsl-tomcat`、目錄 `D:\VirtualMachiles\wsl\wsl-tomcat`。

### 3.3 M3 檢查

| 編號 | 操作 | 預期 |
|------|------|------|
| B1 | 卡片牆 | 兩張新卡片出現，名稱正確 |
| B2 | 名稱重複 | 再用 `wsl-mysql` 新增時，精靈顯示「已有同名 instance」並阻擋 |
| B3 | 安裝目錄非空 | 選一個非空資料夾時被阻擋 |
| B4 | 詳情頁 | 兩台都能進入；安裝路徑與來源一致 |
| B5 | 取消新增 | 取消精靈後不產生 instance |

### 3.4 啟用 systemd（兩台都要）

在 GUI 詳情頁開終端，或使用 PowerShell：

```powershell
wsl.exe -d wsl-mysql -- sh -c "grep -q '[boot]' /etc/wsl.conf 2>/dev/null || printf '\n[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf; cat /etc/wsl.conf"
wsl.exe -d wsl-tomcat -- sh -c "grep -q '[boot]' /etc/wsl.conf 2>/dev/null || printf '\n[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf; cat /etc/wsl.conf"
```

確認兩個 `/etc/wsl.conf` 都有：

```ini
[boot]
systemd=true
```

> 若檔案原本已有 `[boot]` 但沒有 `systemd=true`，請手動補上，避免重複 section。

套用設定：

```powershell
wsl.exe --shutdown
```

> 這會停止所有 distro，包含 `docker-desktop`。GUI 會顯示全部停止，屬正常。

重新啟動兩台：

```powershell
wsl.exe -d wsl-mysql -- true
wsl.exe -d wsl-tomcat -- true
```

驗證 systemd：

```powershell
wsl.exe -d wsl-mysql -- systemctl is-system-running
wsl.exe -d wsl-tomcat -- systemctl is-system-running
```

預期：`running` 或 `degraded`（`degraded` 若只是 WSL 無關單元失敗，需記錄原因）；不可為 `offline`。

---

## 4. 階段 C：在 `wsl-mysql` 安裝 MySQL

以下命令在 `wsl-mysql` 終端內執行（預設 root）。

### 4.1 更新與安裝

```bash
apt update
```

若出現 `404 Not Found`／`no Release file`，先切換來源再重試：

```bash
sed -i 's|http://archive.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' /etc/apt/sources.list
apt update
```

安裝：

```bash
DEBIAN_FRONTEND=noninteractive apt install -y mysql-server
systemctl enable --now mysql
systemctl status mysql --no-pager
ss -tln | grep ':3306'
```

預期：`mysql` 為 `active (running)`；3306 處於 LISTEN。

### 4.2 允許 portproxy 連入

M4 的 portproxy 會從 Windows 連到 distro IP，MySQL 不能只綁 `127.0.0.1`。

```bash
sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
grep '^bind-address' /etc/mysql/mysql.conf.d/mysqld.cnf
systemctl restart mysql
ss -tln | grep ':3306'
```

預期：`bind-address = 0.0.0.0`；3306 監聽在 `0.0.0.0:3306` 或 `*:3306`。

### 4.3 建立驗收用 DB 與帳號

```bash
mysql <<'SQL'
CREATE DATABASE IF NOT EXISTS appdb;
CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY '<APP_PASSWORD>';
GRANT ALL PRIVILEGES ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
SQL
```

> 將 `<APP_PASSWORD>` 換成實際密碼；建議存在 `D:\VirtualMachiles\wsl\secrets\mysql-app.txt`，不要提交到版本庫。

### 4.4 distro 內驗證

```bash
mysql -u appuser -p -h 127.0.0.1 -P 3306 -e "SELECT 1; SHOW DATABASES;"
```

預期：輸入密碼後回傳 `1`，且能看到 `appdb`。

---

## 5. 階段 D：在 `wsl-tomcat` 安裝 Tomcat

以下命令在 `wsl-tomcat` 終端內執行。

### 5.1 更新與安裝

```bash
apt update
```

（若 404，同 4.1 切換 old-releases。）

```bash
DEBIAN_FRONTEND=noninteractive apt install -y tomcat9
systemctl enable --now tomcat9
systemctl status tomcat9 --no-pager
ss -tln | grep ':8080'
```

預期：`tomcat9` 為 `active (running)`；8080 處於 LISTEN。

### 5.2 distro 內驗證

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

預期：`200`（Tomcat 預設歡迎頁）。

### 5.3 確認開機自動啟動

```bash
systemctl is-enabled mysql     # 在 wsl-mysql
systemctl is-enabled tomcat9   # 在 wsl-tomcat
```

預期：`enabled`。

---

## 6. 階段 E：M4 網路規則

### 6.1 新增 MySQL 規則

1. 進入 `wsl-mysql` 詳情頁。
2. 按「新增規則」。
3. 填寫：
   - Windows 端口：13306
   - distro 端口：3306
   - 允許區網其他裝置存取：**不勾選**
   - 啟用：勾選
4. 儲存 → 詢問立即套用時按「是」→ UAC 按「是」。

預期：

- 只跳 **1 次 UAC**。
- 規則狀態「已套用」。
- 防火牆不應建立 MySQL 規則（allow LAN 未勾選）。

驗證：

```powershell
netsh interface portproxy show v4tov4
Get-NetTCPConnection -LocalPort 13306 -State Listen
Test-NetConnection 127.0.0.1 -Port 13306
```

預期：portproxy 有 `0.0.0.0 13306 → <mysql distro IP> 3306`；TCP 測試 `TcpTestSucceeded : True`。

若 Windows 有 MySQL 客戶端，可進一步：

```powershell
mysql -h 127.0.0.1 -P 13306 -u appuser -p -e "SELECT 1;"
```

若沒有客戶端，DB 功能以 4.4 的 distro 內驗證為準，Windows 端只驗證 TCP 埠開通。

### 6.2 新增 Tomcat 規則

1. 進入 `wsl-tomcat` 詳情頁。
2. 新增規則：
   - Windows 端口：18080
   - distro 端口：8080
   - 允許 LAN：勾選
   - 啟用：勾選
3. 套用 → UAC 按「是」。

預期：

- 只跳 **1 次 UAC**。
- 狀態「已套用」。
- 防火牆規則 `WSL Deck wsl-tomcat 18080` 存在，`Private`、`LocalSubnet`、TCP、18080。

驗證：

```powershell
netsh interface portproxy show v4tov4
netsh advfirewall firewall show rule name="WSL Deck wsl-tomcat 18080"
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:18080
```

預期：`200`。

### 6.3 掃描功能驗證（可選）

1. `wsl-mysql` 詳情頁按「掃描監聽端口」→ 應列出 3306。
2. 勾選 3306，Windows 端口改 13306 後加入，應提示已有規則或避免重複。
3. `wsl-tomcat` 掃描 → 應列出 8080。

> 此步驟主要驗證 M4 掃描能讀到服務端口；不要建立重複規則。

---

## 7. 階段 F：M2／M3／M4 串聯情境

### F1：從 GUI 停止／啟動 MySQL instance

1. 詳情頁按「終止」→ `wsl-mysql` 停止。
2. 卡片狀態 10 秒內更新；MySQL 狀態「待啟動」。
3. 按「啟動」→ 等待 systemd 啟動 MySQL。
4. 自動跳一次 UAC 重套規則。
5. 狀態回「已套用」；`Test-NetConnection 127.0.0.1 -Port 13306` 成功。

### F2：從 GUI 停止／啟動 Tomcat instance

同上；`curl http://127.0.0.1:18080` 應回 200。

### F3：外部終止後自動輪詢

```powershell
wsl.exe --terminate wsl-mysql
```

預期：10 秒內 GUI 顯示已停止、規則狀態「待啟動」；不需要手動重新整理。

### F4：關閉 App 再開（M4 自動重套）

1. 兩台 instance 執行中、規則已套用。
2. 關閉 WSL Deck 再啟動。
3. 預期 App 啟動後合併跳 **1 次 UAC**（兩個 instance 合併批次）。
4. 進入詳情頁，兩個規則都應「已套用」。
5. 兩個服務仍可從 Windows 訪問。

### F5：刪除規則與清理（可選，最後做）

1. 刪除 MySQL 或 Tomcat 規則。
2. 詢問立即套用時按「是」→ UAC。
3. 對應 portproxy 與防火牆消失。

### F6：M3 備份／刪除（可選）

- 對 `wsl-tomcat` 做一次備份（TAR 可執行中匯出；VHDX 會先 `wsl --shutdown`）。
- 若不再需要測試環境，用 M3 刪除 instance（輸入名稱；預設先備份），刪除後 M4 會提示清理網路規則。

---

## 8. 驗收結果記錄表

| 階段 | 案例 | 結果（PASS／FAIL／受限） | UAC 次數 | 備註 |
|------|------|--------------------------|----------|------|
| A | M2 基線 A1–A7 |  |  |  |
| B | 新增 `wsl-mysql` |  |  |  |
| B | 新增 `wsl-tomcat` |  |  |  |
| B | systemd 啟用 |  |  |  |
| C | MySQL 安裝與啟動 |  |  |  |
| C | MySQL appdb／appuser |  |  |  |
| D | Tomcat 安裝與啟動 |  |  |  |
| D | Tomcat 首頁 200 |  |  |  |
| E | MySQL 13306 規則 |  | 1 |  |
| E | Tomcat 18080 規則 |  | 1 |  |
| E | 掃描端口 |  |  |  |
| F | 停止／啟動重套 |  | 每次 1 |  |
| F | App 重開重套 |  | 1（合併） |  |
| F | 刪除規則清理 |  | 1 |  |

---

## 9. 通過標準

全部滿足才算本次端到端驗收通過：

1. M2 基線沒有回歸：卡片牆換行、系統 instance 禁用、啟停／終端／資料夾、10 秒輪詢正常。
2. M3 能在 3 步內建立 `wsl-mysql`、`wsl-tomcat`，名稱與目錄驗證有效。
3. 兩台 distro 的 systemd 運作，MySQL／Tomcat 服務 `enabled` 且 `active`。
4. `wsl-mysql` 內 `appuser` 能連 `appdb` 並 `SELECT 1`。
5. `wsl-tomcat` 內 `curl 127.0.0.1:8080` 回 200。
6. M4 規則：
   - Windows 13306 → MySQL 3306，狀態已套用。
   - Windows 18080 → Tomcat 8080，狀態已套用，防火牆 Private／LocalSubnet。
7. 每次套用只跳一次 UAC；App 重開時多個 instance 合併一次。
8. instance 停止顯示待啟動；重新啟動後服務恢復並自動重套。
9. 外部終止後 10 秒內 UI 更新。
10. 刪除規則／刪除 instance 後沒有殘留 portproxy／防火牆規則。

### 跨裝置 LAN

- Tomcat 18080：Windows 網路為 Private 時，同網段另一台裝置應能開啟 Tomcat 歡迎頁；Public 時記為「受限」。
- MySQL 13306：本次建議不開放 LAN；只驗證 Windows 本機 TCP 與 distro 內 DB。

---

## 10. 清理步驟

1. 刪除兩台 instance 的 M4 規則（刪除後按立即套用，UAC）。
2. 停止測試服務：

   ```powershell
   wsl.exe --terminate wsl-mysql
   wsl.exe --terminate wsl-tomcat
   ```

3. 刪除 `wsl-mysql`、`wsl-tomcat`（M3 刪除需輸入名稱；可選擇備份）。
4. 確認無殘留：

   ```powershell
   netsh interface portproxy show v4tov4
   netsh advfirewall firewall show rule name="WSL Deck wsl-mysql 13306"
   netsh advfirewall firewall show rule name="WSL Deck wsl-tomcat 18080"
   ```

5. 刪除 `D:\VirtualMachiles\wsl\secrets\mysql-app.txt`（若建立過）。
6. 可選：刪除 `backups\wsl-mysql`、`backups\wsl-tomcat`。
7. 不要刪除 `ubuntu`、`node22`、`alms`、`docker-desktop` 或 `wsl-desk-test` 等既有資料。

---

## 11. 已知限制與風險

- Ubuntu 20.04 已 EOL；套件版本較舊（MySQL 8.0、Tomcat 9）。若需要 24.04／Tomcat 10+，需改用線上安裝或另備新版 rootfs。
- `wsl --shutdown` 會停止所有 distro（含 Docker Desktop）。
- MySQL `bind-address=0.0.0.0` 是為了讓 portproxy 可連入；安全性依賴 M4 防火牆（本次 MySQL 不開 LAN，僅 Windows 本機）。
- Public 網路下，Tomcat 的 private 防火牆規則不會對其他裝置開放。
- 每次套用需 UAC；這是 portproxy／防火牆的必要權限。
- M4 目前不處理「重開機後托盤自啟」；完整開機自啟留到 M5。
- 本方案不包含 MySQL root 密碼加固、TLS、備份排程、Tomcat 應用 WAR 部署。
