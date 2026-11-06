# C 方案（獨立 netns）的可控啟用：只在 WSL Deck 啟動時生效

> 狀態：**待確認**
> 日期：2026-11-06
> 前置：[wsl-deck-per-instance-ip.md](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/plans/wsl-deck-per-instance-ip.md)（方案 C 原理與風險）

## 1. 結論

**可以做到，而且能滿足「只有 WSL Deck 啟動時才是 C，其他 `wsl` 命令啟動維持 A」**，關鍵在於：**不要在實例內留下任何常駐設定**（不寫永久 systemd drop-in、不改 `wsl.conf`），netns、veth、服務全部由 App 在執行期建立與回收。這樣：

- 從 App 啟動 → App 建 netns → 把目標服務搬進去 → 對外 IP = 設定值。
- 從外部 `wsl -d <name>` 啟動 → 沒有任何 App 痕跡 → 服務照原樣在共用 netns → 即 A。
- `wsl --shutdown` 後 netns/veth/服務狀態全部自然消失，下一次由「誰啟動」決定模式。

三個必須接受的前提：

1. **只能搬「App 管的服務」**（systemd unit 或明確的啟動命令）；使用者自己開的 shell、App 未列管的程序仍在共用 netns。
2. **實例啟動後會有一段 A 的時間窗**：systemd 會先在共用 netns 把 MySQL 等服務拉起來，App 必須先停掉再搬進 netns。可縮短但無法歸零。
3. **對外可達性仍需 `proxy_arp`**（netns 的 IP 不在 `eth0` 上，Windows 端 ARP 不會被回應）；若 HNS 不放行，只能退回「portproxy 指向 `.232` + `socat` 轉入 netns」，此時對外仍只有一個 IP。

## 2. 行為定義

| 啟動來源 | 網路模式 | 服務所在 netns | 外部看到的 IP |
|----------|----------|----------------|----------------|
| WSL Deck「啟動」，且該實例 `mode=isolated` | C | 例：`wsl-deck-wsl-mysql` | 設定值（如 `192.168.163.241`） |
| WSL Deck「啟動」，`mode=default` | A | 共用 netns | `.232` |
| 外部 `wsl -d <name>`（App 未介入） | A | 共用 netns | `.232` |
| App 已啟動 C，之後外部再 `wsl -d` 開新 shell | **A**（新 shell 落在 distro init 的共用 netns） | 已搬走的服務仍在 C netns | shell 看到 `.232`；要連 C 服務改用設定的 netns IP |
| `wsl --shutdown` 後由外部啟動 | A | 共用 netns | `.232` |

> 已啟動的 distro 無法「換掉 init 的 netns」；模式只在下一次啟動時生效。UI 需明示。
> C 是**另建**的 netns（overlay），不是取代 distro 的預設 netns；沒有被 `nsenter` 包進去的程序（含外部 wt 開的 shell）一律在 A。App 自己開的終端若要用 C，必須顯式 `nsenter --net=/run/netns/wsl-deck-<name>`。

### 2.1 「永久 C」與「條件式 C」的差別（wsl.conf 能做到哪一步）

| 做法 | 觸發點 | 外部 `wsl -d` 啟動 | 可靠性 |
|------|--------|--------------------|--------|
| 條件式 C（本計畫 §4） | App 執行期建立／回收 | A | 依賴 App 正常執行；崩潰需清理殘留 |
| 永久 C（`wsl.conf` `[boot] command` + systemd drop-in） | distro 每次啟動 | **也是 C** | 最可靠，但無法區分「誰啟動」 |

`wsl.conf` 本身**沒有** IP／netns／路由欄位，支援的只有 `[automount]`、`[boot]`、`[interop]`、`[network]`、`[user]`；`[network]` 只有 `hostname`、`generateResolvConf`。所以：

- 用 `wsl.conf` **不能**直接指定 IP，也**不能**靠它隔離網路（網路棧仍是共用的）。
- 但每個 distro 有自己的 `wsl.conf`，可利用 `[boot] command=` 在啟動時執行 root 腳本 → 建 netns／veth → 再由 systemd drop-in（`NetworkNamespacePath=`）把服務放進去。這樣就是**永久、每實例獨立**的 C。
- 永久 C 的代價：**外部 `wsl -d` 啟動也是 C**，與「App 啟動才 C」互斥。
- 若一定要「外部 A」，唯一可用的條件訊號來自 distro 外部，例如 Windows 端旗標檔（boot 腳本檢查 `/mnt/c/.../flag`）；App 崩潰時旗標殘留會導致外部誤入 C。

`[boot] command` 與 systemd 的執行先後不保證；永久方案要在 boot 腳本末尾 `systemctl restart <unit>`，或讓 unit `After=` 該 netns oneshot unit。

## 3. 設定模型（`config.json`）

沿用 `port_forwards` 的「以 distro 名稱為鍵」慣例，新增 `instance_networks`：

```json
"instance_networks": {
  "wsl-mysql": {
    "enabled": true,
    "scope": "temporary",
    "ip": "192.168.163.241",
    "services": [
      { "name": "mysql", "command": "/usr/sbin/mysqld --user=mysql" }
    ]
  }
}
```

欄位語意（對應 UI 的三個選項）：

| 欄位 | UI | 說明 |
|------|----|------|
| `enabled` | 「啟用 C 方案」勾選框 | 未勾選＝一律 A |
| `scope=temporary` | 「臨時啟用：僅 WSL Deck 啟動生效」 | App 執行期建立／回收，不落地；外部 `wsl -d` 仍為 A |
| `scope=permanent` | 「永久啟用：WSL Deck 與 wt 啟動都生效」 | 寫入 distro 的 boot hook 與 systemd drop-in，任何啟動都是 C |
| `ip` | IP 欄位 | netns 對外位址，必填；限 `192.168.160.0/20`、不可 `.232`、不可重複 |
| `services` | 服務清單（進階） | unit 名 + 啟動命令；永久與臨時共用 |

驗證（`Config._validate`）：

- `enabled` 必須是 bool；未啟用時忽略其餘欄位。
- `scope` ∈ `temporary` / `permanent`。
- 啟用時 `ip` 必填且合法；`services` 為非空陣列，每項 `name`／`command` 皆非空字串。
- 同一 IP 不可被兩個實例使用。

舊設定由 `_migrate()` 補 `instance_networks: {}`（缺省即 A）。

## 4. 生命週期

### 4.1 啟動（`wsl.py:start_distro`，[wsl.py:258](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/wsl.py#L258)）

1. `wsl -d <name> -- true`（既有）。
2. 若 `mode=isolated`：
   a. 檢查該實例是否已存在 `wsl-deck-<name>` netns；有則視為殘留，先清理。
   b. root 建立 netns 與 veth；另一端留在共用 netns，分配 `uplink_ip`（自動取池內下一個，如 `.242`）。
   c. 設定 `net.ipv4.ip_forward=1`、`net.ipv4.conf.eth0.proxy_arp=1`（供 Windows 端 ARP）。
   d. 逐一 `systemctl stop <unit>`（或 `pkill` 命令），確認共用 netns 不再監聽。
   e. 用 `systemd-run --unit=wsl-deck-<name>-<svc> --property=NetworkNamespacePath=/run/netns/wsl-deck-<name> ...` 啟動服務（transient，不落地設定檔）。
3. 驗證：`ip netns exec wsl-deck-<name> ss -tln` 看到預期埠。
4. 失敗時**回退 A**：刪 netns/veth、重啟原服務、狀態列警告（不讓實例停在半殘狀態）。

### 4.2 外部工具（掃描、探測、portproxy）

- `scan_tcp_ports` 在 `isolated` 時改用 `ip netns exec <ns> ss -tln`（[network.py:85-90](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/network.py#L85-L90)）。
- `get_distro_ip` 在 `isolated` 時回傳設定的 `ip`（[wsl.py:274](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/wsl.py#L274)）。
- portproxy `connectaddress` 用該 IP。

### 4.3 停止／App 退出／異常

| 事件 | 動作 |
|------|------|
| App 內「停止實例」 | 停 transient 服務 → 刪 veth / netns → 正常停止 distro |
| App 正常退出（實例續跑） | **預設還原 A**：停 isolated 服務 → 刪 netns → 重啟原服務（有短暫中斷；可在設定關閉） |
| App 崩潰 | 殘留 netns/veth/transient unit；下次啟動該實例時偵測並清理（辨識前綴 `wsl-deck-`） |
| `wsl --shutdown` | 全部消失，無需清理 |
| 使用者自行安裝新服務 | 仍在共用 netns；要隔離必須加入 `services` |

## 5. 為何不會污染「外部啟動 = A」

- 不寫 `/etc/systemd/system/*.d/*netns*`，不改 `wsl.conf`。
- 服務以 `systemd-run` transient unit 啟動，unit 名帶 `wsl-deck-` 前綴，App 退出即停止。
- netns 名稱帶 `wsl-deck-` 前綴，只存在於執行期。
- 因此 distro 從外部啟動時，systemd 依原設定把所有服務拉回共用 netns = A。

## 6. Windows 可達性

優先：`proxy_arp=1` on `eth0` ＋ `ip_forward=1`，讓 Windows／外部直接連 netns IP。

備援：`proxy_arp` 無效時，portproxy 仍指 `.232`，在共用 netns 用 `socat TCP-LISTEN:<port>,fork TCP:<netns_ip>:<port>` 轉入，並在 UI 明示「對外只有一個 IP」。

## 7. 影響檔案

| 檔案 | 改動 |
|------|------|
| `app/netns.py`（新增） | netns/veth 建立、位址池、transient 服務、清理、殘留偵測 |
| `app/config.py` | `instance_networks` 預設、驗證、遷移 |
| `app/wsl.py` | `start_distro` 掛 hook；`get_distro_ip` 支援覆寫 |
| `app/network.py` | 掃描改 `ip netns exec`；portproxy 指向設定 IP |
| `app/ui/instance_settings_dialog.py` | 模式、IP、服務清單欄位 |
| `app/ui/detail_page.py` | 顯示「網路模式：C（獨立 netns）」與 effective IP |
| `app/ui/main_window.py` | 啟動／停止／退出流程接上 netns 生命週期 |
| `tests/test_netns.py`（新增）、`tests/test_config.py`、`tests/test_network.py` | 命令產生、位址池、驗證、狀態 |

## 8. 測試與驗收

| 測試 | 標準 |
|------|------|
| 單元 | 命令字串產生、IP 驗證／重複、模式切換、清理命令 |
| 實機 C | App 啟動 `wsl-mysql` → `ip netns exec` 內看到 3306；Windows `Test-NetConnection <ip> -Port 3306` 成功 |
| 實機 A | `wsl --shutdown` 後用 `wsl -d wsl-mysql` 啟動 → `ss -tln` 在共用 netns，IP 為 `.232` |
| 回退 | 故意讓 netns 建立失敗 → 服務回到 A，UI 有警告，實例仍可用 |
| 殘留 | 殺掉 App 後重新啟動 → 自動清理 `wsl-deck-*` |
| 隔離 | 兩個實例都 `isolated` 且都跑 3306 → 同時可用且各自 IP |

## 9. 風險

| 風險 | 對策 |
|------|------|
| 服務啟動命令寫錯 → 搬遷後起不來 | 啟動前 `systemd-run` 失敗即回退 A 並顯示原始錯誤 |
| MySQL 資料目錄鎖未釋放 | 等 `systemctl stop` 完成（`is-active` 輪詢）再啟動 |
| `proxy_arp` 被 HNS 忽略 | 備援 socat；UI 明示限制 |
| App 崩潰留下 transient unit | 啟動時清理前綴 `wsl-deck-` |
| 使用者把 netns 當成安全邊界 | UI 明示「隔離網路，不是安全隔離」 |

## 10. 已確認的決策（2026-11-06）

- [x] 不落地任何常駐設定來實作「臨時」；臨時模式靠 App 執行期建立／回收 → 外部 `wsl -d` 仍是 A
- [x] 接受實例啟動後的短暫 A 時間窗
- [x] 臨時模式：App 正常退出且實例續跑時，**還原 A**（停 isolated 服務→刪 netns/veth→重啟原服務）
- [x] `services` 由使用者手填（unit 名 + 啟動命令）
- [x] IP 由使用者指定（`.233` 以上、不可重複）
- [x] 永久模式：`wsl.conf` `[boot] command` + 每實例腳本 + systemd transient／drop-in，WSL Deck 與 wt 啟動都生效
- [x] UI 提供：是否啟用 C、臨時／永久二選一、IP
- [x] 先以 `wsl-mysql` 做先導驗證，再推廣

## 11. 永久模式落地細節

永久模式**不用 `wsl.conf` boot 命令**（避免與 systemd 的啟動順序不確定），改用 systemd 原生機制：

| 位置 | 內容 |
|------|------|
| `/usr/local/lib/wsl-deck/netns-up.sh` | 內嵌 netns／veth／IP／uplink 常數（由 App 產生）；建 netns/veth、設 `proxy_arp`／`ip_forward`／`rp_filter`；已存在則直接退出（idempotent） |
| `/usr/local/lib/wsl-deck/netns-down.sh` | 刪 route／veth／netns |
| `/etc/systemd/system/wsl-deck-netns.service` | `Type=oneshot`、`RemainAfterExit=yes`、`ExecStart=netns-up.sh`、`ExecStop=-netns-down.sh`、`Before=<service>.service` |
| `/etc/systemd/system/<unit>.d/10-wsl-deck-netns.conf` | `After=wsl-deck-netns.service` + `NetworkNamespacePath=/run/netns/wsl-deck-<name>`（不設 `Requires=`，避免解除時 stop job 競態） |
| `/etc/wsl-deck/network.state` | 目前套用的 IP 與服務清單，用於啟動時比對，避免重複安裝 |

生命週期：

- 啟用：寫上述檔案 → `daemon-reload` → `enable` + `start wsl-deck-netns` → 重啟服務（`Before` 立即生效，不需重啟 distro）。
- 停用：`disable` → 逐一 stop 服務並移除 drop-in → `stop wsl-deck-netns` → 刪 unit／腳本／state → `daemon-reload` → 重新啟動服務，回到共用 netns。
- 外部 `wsl -d` 或 wt 啟動：systemd 先起 `wsl-deck-netns` 再起服務 → C。
- `wsl --shutdown` 後再啟動：同樣是 C（永久）。

## 12. 已定實作決策

- 永久模式採 systemd oneshot + drop-in（較穩），不依賴 `wsl.conf` boot 命令。
- 臨時模式只用 `systemd-run` transient unit，不寫任何永久檔案。
- 先導驗證在 `wsl-mysql`。

## 13. 實機驗證結果（2026-11-06，`wsl-mysql`）

| 情境 | 結果 |
|------|------|
| 臨時模式（`192.168.163.241`、`mysql`） | `ensure_after_start` 回傳 `warnings: []`；`ip netns list` 出現 `wsl-deck-01edbb25`；netns 內 `ss -tln` 有 `3306`／`33060`，共用 netns 無 3306；Windows `Test-NetConnection 192.168.163.241 -Port 3306` = `True` |
| 臨時清理 | transient unit 停止、netns／veth／route 移除；MySQL 回到共用 netns 監聽 `0.0.0.0:3306` |
| 執行中關閉 C（`ensure_after_start(raw={enabled:False}, force=True)`） | 自動停掉 transient unit、刪 netns；`list_netns` 變空、`effective_ip` 回到 `192.168.163.232`、`systemctl list-units 'wsl-deck-*'` 無殘留；Windows `Test-NetConnection 192.168.163.232:3306` = `True` |
| 永久模式 | 安裝 unit／drop-in／腳本後服務在 netns 內啟動，Windows 可連 `.241:3306` |
| 永久模式（外部 wt） | `wsl --terminate wsl-mysql` 後以外部 `wsl -d wsl-mysql -- true` 啟動 → netns 自動重建、MySQL 僅監聽於 netns 內、Windows 仍可連 `.241:3306` → 證明對 wt 啟動亦生效 |
| 停用永久模式 | unit／drop-in／腳本／state 全部移除；MySQL 回到共用 netns 監聽 `3306`／`33060`（初次因 glob 取到 `mysql.service.d` 導致未停服務，已修正為 `basename "$(dirname "$f")" .d`） |
| 殘留狀態 | 驗證後 `instance_networks` 已清空、無 `wsl-deck-*` netns，`wsl-mysql` 維持 A（`192.168.163.232:3306`） |

自動化：`python -m unittest discover -s tests` → **154 tests OK**（含 `tests/test_netns.py`、`tests/test_config.py` 新增案例）；`QT_QPA_PLATFORM=offscreen` 匯入 `app.ui.main_window` 與 `InstanceSettingsDialog` 冒煙通過。

已知限制：netns 是網路隔離，不是安全邊界；`127.0.0.1` 在 netns 內是獨立迴路（服務只綁 loopback 時，Windows 端需改用設定 IP 或 portproxy）。
