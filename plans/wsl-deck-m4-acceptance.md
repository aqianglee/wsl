# WSL Deck M4 驗收方案

> 版本：2026-11-02
> 範圍：網路規則 CRUD、掃描監聽端口、一次 UAC 批次套用、啟動／開 App 自動重套、刪除規則清理。
> 對應文件：[wsl-deck-m4.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m4.md)、[wsl-deck-handoff.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-handoff.md)
> 測試對象：僅限測試 instance `wsl-deck-test`；不得對 `ubuntu`、`node22`、`alms`、`docker-desktop` 做破壞性操作。

---

## 1. 驗收目標

確認以下行為可用：

1. 在詳情頁新增、編輯、刪除、停用網路規則。
2. 「立即套用」只跳一次 UAC，批次完成 portproxy 與防火牆。
3. 規則狀態正確顯示：已套用／待套用／待啟動／已停用。
4. instance 啟動成功後與 App 啟動後會自動重套。
5. 掃描監聽端口可列出 TCP 端口並加入規則。
6. 衝突端口會被跳過且不影響其他規則。
7. 刪除規則或刪除 instance 後，對應的 portproxy／防火牆規則會被清除。

## 2. 前置條件

### 2.1 程式與測試

```powershell
cd d:\VirtualMachiles\wsl\wsl-deck
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

預期：`Ran 42 tests ... OK`。

### 2.2 測試 instance

- 若 `wsl-deck-test` 不存在，用 GUI「新增 Instance」建立：
  - 來源：VHDX
  - 檔案：`D:\VirtualMachiles\wsl\backups\ubuntu\ubuntu.vhdx`
  - 名稱：`wsl-deck-test`
  - 安裝目錄：`D:\VirtualMachiles\wsl\wsl-deck-test`
- 不要使用拼字不同的 `wsl-desk-test`／`wsl-desk-test-clone` 作測試；那些是既有資料。
- 測試前確認沒有殘留規則：

```powershell
netsh interface portproxy show v4tov4
netsh advfirewall firewall show rule name="WSL Deck wsl-deck-test 8080"
```

第一條應為空；第二條應顯示找不到規則。

### 2.3 網路環境

- 跨裝置 LAN 驗收需要目前網路為 **Private**。
- 查詢：

```powershell
Get-NetConnectionProfile | Select-Object Name,NetworkCategory
```

- 若顯示 `Public`，同一台電腦可測 `http://<Windows 區網 IP>:8080`，但其他裝置會被防火牆阻擋；此時跨裝置項目標記「受限」，不是程式失敗。
- 本機目前實測為 `Pisoft 4 / Public`，請先確認是否要切換為 Private 再測跨裝置。

### 2.4 啟動 GUI

```powershell
d:\VirtualMachiles\wsl\wsl-deck\.venv\Scripts\pythonw.exe d:\VirtualMachiles\wsl\wsl-deck\main.py
```

---

## 3. 測試資料

| 項目 | 值 |
|------|----|
| 測試 instance | `wsl-deck-test` |
| distro HTTP 服務 | `python3 -m http.server 80`（若無權限改用 8000） |
| Windows 端口 | 8080（或 18080，避開已佔用端口） |
| distro 端口 | 80（或 8000） |
| 防火牆規則名稱 | `WSL Deck wsl-deck-test 8080` |

在測試 instance 的終端執行 HTTP 服務，保持終端開著：

```bash
python3 -m http.server 80
```

若出現權限錯誤，改用：

```bash
python3 -m http.server 8000
```

後續端口相應改為 `8080 → 8000`，其餘步驟相同。

---

## 4. 驗收案例

### A1：新增規則與一次 UAC

**步驟**

1. 進入 `wsl-deck-test` 詳情頁。
2. 按「新增規則」。
3. 填寫：
   - Windows 端口：8080
   - distro 端口：80
   - 允許區網其他裝置存取：勾選
   - 啟用此規則：勾選
4. 按「新增規則」。
5. 彈出「規則已變更」時按「是」立即套用。
6. UAC 彈窗按「是」。

**預期**

- 整個流程只跳 **1 次 UAC**。
- 規則表出現 `8080 / 80 / 是 / 是 / 已套用`。
- 狀態列或日誌沒有錯誤。

**驗證命令**

```powershell
netsh interface portproxy show v4tov4
netsh advfirewall firewall show rule name="WSL Deck wsl-deck-test 8080"
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8080
```

預期：

- portproxy 有一列 `0.0.0.0 8080 → <distro IP> 80`。
- 防火牆規則顯示 `Enabled: Yes`、`Direction: In`、`Profiles: Private`、`RemoteIP: LocalSubnet`、`Protocol: TCP`、`LocalPort: 8080`。
- curl 回 `200`。

### A2：區網 IP 訪問

**步驟**

1. 查 Windows 區網 IP：

   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 |
     Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
     Select-Object IPAddress,InterfaceAlias
   ```

2. 用該 IP 訪問：

   ```powershell
   curl.exe -s -o NUL -w "%{http_code}`n" http://<Windows 區網 IP>:8080
   ```

3. 若網路為 Private，用同網段另一台裝置開瀏覽器訪問同一 URL。

**預期**

- 本機區網 IP 訪問回 `200`。
- Private 網路下另一台裝置可開啟頁面。
- Public 網路下另一台裝置失敗屬預期限制，記錄為「受限」而非 FAIL。

### A3：停止／啟動自動重套

**步驟**

1. 在詳情頁按「終止」。
2. 觀察規則狀態。
3. 再按「啟動」。
4. UAC 彈窗按「是」。

**預期**

- 停止後狀態變「待啟動」；不應顯示指向新 IP 的已套用狀態。
- 啟動成功後自動跳 **1 次 UAC**，狀態回到「已套用」。
- `curl http://127.0.0.1:8080` 再次回 `200`。

### A4：關閉 App 再開自動重套

**步驟**

1. 保持 `wsl-deck-test` 執行中且規則已套用。
2. 關閉 WSL Deck（目前尚未做托盤，關窗即退出）。
3. 重新啟動 GUI。
4. UAC 彈窗按「是」。

**預期**

- App 啟動後自動跳 **1 次 UAC**（若同時有多個 instance 有規則，也只跳一次）。
- 進入詳情頁後規則狀態為「已套用」。
- curl 仍回 `200`。

> 真正的「重開機後自啟重套」屬於 M5；M4 以本案例作為替代驗證。

### A5：編輯規則（更換 Windows 端口）

**步驟**

1. 選取規則，按「編輯」。
2. Windows 端口由 8080 改為 18080，distro 端口保持 80。
3. 儲存。
4. 詢問立即套用時按「是」，UAC 按「是」。

**預期**

- 只跳 **1 次 UAC**。
- 舊的 8080 轉發與防火牆規則被移除。
- 18080 規則狀態為「已套用」。
- `curl http://127.0.0.1:18080` 回 `200`。
- `curl http://127.0.0.1:8080` 連線失敗或非 200。

### A6：停用規則

**步驟**

1. 編輯同一條規則，取消勾選「啟用此規則」。
2. 儲存並立即套用，UAC 按「是」。

**預期**

- 狀態變「已停用」。
- 對應的 portproxy 與防火牆規則被移除。
- 該端口 curl 不再回 200。
- 再重新啟用並套用後可恢復。

### A7：刪除規則與清理

**步驟**

1. 選取規則，按「刪除」。
2. 確認刪除。
3. 詢問立即套用時按「是」，UAC 按「是」。

**預期**

- 規則從表格消失。
- 對應 portproxy 與防火牆規則被移除。
- 日誌記錄已移除規則與管理員命令。

### A8：掃描監聽端口

**步驟**

1. 確保 distro 內 HTTP 服務正在監聽（80 或 8000）。
2. 詳情頁按「掃描監聽端口」。
3. 掃描結果應列出 `80`（或 `8000`），也可能包含 `22`。
4. 勾選 HTTP 端口，Windows 端口填 18081。
5. 按「加入規則」，詢問套用時按「是」，UAC 按「是」。

**預期**

- 掃描能列出監聽中的 TCP 端口。
- 勾選的端口成功加入規則並套用。
- `curl http://127.0.0.1:18081` 回 `200`。
- 若 instance 未執行，按掃描時應先詢問是否啟動；選「是」後會啟動並掃描。

### A9：端口衝突

**步驟**

1. 在 Windows 另開一個服務佔用 18082：

   ```powershell
   python -m http.server 18082
   ```

2. 在 GUI 新增 `18082 → 80` 規則並套用。
3. 觀察結果後關閉該 Python 服務。

**預期**

- 套用結果提示「Windows 端口 18082 已被其他程式佔用，已略過」。
- 其他已啟用規則不受影響，仍可訪問。
- 被跳過的規則維持「待套用」。

### A10：取消 UAC

**步驟**

1. 修改任一規則並按立即套用。
2. 在 UAC 彈窗按「否」。

**預期**

- 顯示「已取消管理員授權，規則維持待套用」。
- 不會重複彈 UAC。
- 再次按「立即套用」可重試；按「是」後成功。

### A11：表單與系統 instance

**步驟**

1. 新增規則時，Windows 端口填一個已被其他規則使用的值。
2. 確認按下「新增規則」時出現紅字且對話框不關閉。
3. 取消新增／編輯／刪除對話框。
4. 進入 `docker-desktop` 詳情頁。

**預期**

- 重複 Windows 端口被阻擋，並提示被哪個 instance 使用。
- 取消對話框不產生任何 config 變更。
- `docker-desktop` 的網路按鈕全部禁用，不能新增／編輯／刪除／套用／掃描。

### A12：刪除 instance 時清理網路規則

**步驟**

1. 保留至少一條已套用規則。
2. 從詳情頁刪除 `wsl-deck-test`（需輸入名稱；可勾選先備份）。
3. instance 刪除完成後，若提示移除網路規則，UAC 按「是」。

**預期**

- instance 從卡片牆消失。
- 對應的 portproxy 與防火牆規則被移除。
- `config.json` 內該 instance 的 `port_forwards` 被清除。

---

## 5. 驗收結果記錄

| 案例 | 結果（PASS／FAIL／受限） | UAC 次數 | 備註 |
|------|--------------------------|----------|------|
| A1 新增規則與一次 UAC |  |  |  |
| A2 區網 IP 訪問 |  |  |  |
| A3 停止／啟動自動重套 |  |  |  |
| A4 關閉 App 再開重套 |  |  |  |
| A5 編輯規則更換端口 |  |  |  |
| A6 停用規則 |  |  |  |
| A7 刪除規則清理 |  |  |  |
| A8 掃描監聽端口 |  |  |  |
| A9 端口衝突 |  |  |  |
| A10 取消 UAC |  |  |  |
| A11 表單與系統 instance |  |  |  |
| A12 刪除 instance 清理 |  |  |  |

---

## 6. 通過標準

全部滿足才算 M4 驗收通過：

1. A1、A3、A4、A7、A10 必須 PASS。
2. 每次套用只跳一次 UAC；同一次啟動重套多個 instance 也只跳一次。
3. portproxy、防火牆規則內容與規格一致：
   - `listenaddress=0.0.0.0`
   - 防火牆 `profile=private`、`remoteip=localsubnet`、TCP、指定 localport
   - 規則名稱 `WSL Deck <instance> <windows_port>`
4. 規則狀態與實際 portproxy 狀態一致。
5. 無殘留錯誤規則；刪除後 portproxy／防火牆確實消失。
6. 日誌可看到實際 netsh 命令與錯誤原因。

A2 若因 Public 網路無法跨裝置，可記為「受限」，不算程式 FAIL；但需在備註寫明網路設定檔。

---

## 7. 異常處理與回滾

- **UAC 取消**：規則保持待套用；再次按「立即套用」即可，不需重啟 App。
- **套用失敗**：查看日誌抽屜的 netsh 輸出；修正端口或先清理衝突後重試。
- **規則狀態不更新**：關閉詳情頁再進入，或等 10 秒輪詢；仍異常則查看日誌是否有 `讀取網路狀態失敗`。
- **需要手動清理**：

  ```powershell
  netsh interface portproxy delete v4tov4 listenport=<port> listenaddress=0.0.0.0
  netsh advfirewall firewall delete rule name="WSL Deck <instance> <port>"
  ```

- **測試 instance 損壞**：直接刪除後重建；不影響其他 instance。

---

## 8. 清理步驟

1. 刪除測試規則（或直接刪除測試 instance 並按提示清理）。
2. 刪除 `wsl-deck-test` instance。
3. 關閉測試用 HTTP 服務與 Windows 測試端口。
4. 確認：

   ```powershell
   netsh interface portproxy show v4tov4
   netsh advfirewall firewall show rule name="WSL Deck wsl-deck-test 8080"
   ```

   兩者都不應有測試殘留。

5. 可選：刪除 `D:\VirtualMachiles\wsl\backups\wsl-deck-test`。
6. 不要刪除 `wsl-desk-test`／`wsl-desk-test-clone`，除非確認是本人建立的測試資料。

---

## 9. 已知限制（非 M4 缺陷）

- 防火牆只對 Private 網路的 LocalSubnet 開放；Public 網路下其他裝置無法訪問。
- 每次套用都需要 UAC；這是寫入 portproxy／防火牆的必要權限。
- instance 停止時只標記「待啟動」，不主動刪除舊 portproxy；下次啟動會重套並覆蓋。
- 真正的開機自啟與托盤常駐屬 M5；M4 以「關閉 App 再開」驗證自動重套。
- `netsh` 對不存在規則的刪除會回報錯誤；日誌可能出現清理 warning，屬正常現象。
- M5 打包後提權入口需從 `pythonw -m app.admin` 改為 exe 參數入口。
