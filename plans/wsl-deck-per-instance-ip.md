# 每實例獨立 IP：可行性與實作計畫

> 狀態：**待確認**
> 日期：2026-11-06
> 前置：[wsl-deck-network-external-access.md](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/plans/wsl-deck-network-external-access.md)（Phase 0 已完成：MySQL 已重啟，13306 可連）

## 1. 結論（先回答問題）

**原生設定做不到。** WSL 的 IP 是「VM 級」而非「distro 級」：本機 WSL 3.0.3.0 把多個 distro 放在同一個 VM、共用同一個網路命名空間；`.wslconfig` 是全域設定，`wsl.conf` 沒有 IP／網路位址欄位。所以 `目前 IP` 相同是如實顯示，不是遺漏。

但**可以透過 Linux 網路機制「做出」不同 IP**，有兩條路，代價不同：

| 方案 | 做法 | 能達到 | 代價／限制 |
|------|------|--------|-------------|
| A（現況） | 不改 IP，用不同 Windows 埠（13306、18080） | 外部可分別連到兩個服務 | 對外看起來只是一個 IP；**兩個實例共用協議棧，不能同時各綁 3306** |
| B IP 別名 | 在共用 netns 的 `eth0` 上加第二個位址（如 `192.168.163.233`），服務綁該位址 | 兩個實例有不同 IP，portproxy 可分別指過去 | 非真正隔離（兩實例仍能互見彼此介面）；WSL 重啟後消失，需 App 重建；要 root |
| C 獨立 netns | 每個實例 rootfs 內建 `/run/netns/wsl-deck-<name>`＋veth＋NAT，服務用 `nsenter` 跑在裡面 | 真正獨立網路棧：各自 IP、各自 3306／8080 不衝突 | 複雜度高、非持久、systemd 服務要改啟動方式、需封裝進 App 啟動流程 |
| D 獨立 VM | 第二個服務改用 Hyper-V／VMware 完整 VM 或另一台機器 | 完全獨立 | 脫離 WSL Deck 管理範圍 |

## 2. 已核實事實（2026-11-06 實機）

| 項目 | 結果 |
|------|------|
| WSL 版本 | `3.0.3.0`，核心 `6.18.54.1-1` |
| PID 命名空間 | 兩實例**不同**（`4026532214` / `4026532304`） |
| 網路命名空間 | 兩實例**相同**（`4026531833`） |
| 介面 | 僅 `lo`、`eth0`（`192.168.163.232/20`），無 bridge |
| root 能力 | `CapEff=000001ffffffffff`（含 `CAP_NET_ADMIN`） |
| netns 可用性 | `unshare -n` 成功；`ip netns add`／`delete` 成功（已清除測試用 namespace） |
| 工具 | `/usr/sbin/ip`、`/usr/bin/nsenter` 皆存在 |

## 3. 方案 B：IP 別名（最小改動）

### 3.1 原理

```bash
ip addr add 192.168.163.233/20 dev eth0    # 由 root 執行
# 服務綁定該位址（MySQL bind-address=192.168.163.233 或 0.0.0.0）
netsh portproxy: connectaddress=192.168.163.233 connectport=3306
```

### 3.2 App 整合

- 實例設定新增「靜態 IP」（空白＝沿用 WSL 預設）。
- 實例啟動後以 root 執行 `ip addr add`；停止前 `ip addr del`（或忽略，等 WSL 重啟自然清除）。
- `get_distro_ip()` 若該實例有靜態 IP，直接回傳設定值（[wsl.py:274](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/wsl.py#L274)）。
- portproxy 套用時 `connect_address` 用該 IP（[network.py:148-191](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/network.py#L148-L191)）。

### 3.3 限制（必須在 UI 明示）

- 兩實例仍共用同一個協議棧，A 的服務可以綁到 B 的位址；這只是「標籤式」區分，不是隔離。
- `wsl --shutdown` 或重開機後位址消失，需再次「套用」。
- 同一服務埠（例如兩邊都要 3306）仍然衝突，B 只解決 IP 不解決埠。
- 別名屬於 `eth0` 本身，Linux 會對任何本地地址回 ARP，Windows 端到達率較高；但仍需先導驗證（HNS/WSL NAT 可能只認主要 IP）。
- **`127.0.0.1` 也是共用的**：若服務綁 `0.0.0.0`，另一個實例的 `localhost:<port>` 也會連到它；只有綁定到別名位址才能避免這種誤連。

## 4. 方案 C：獨立網路命名空間（真正隔離）

### 4.1 步驟（每實例）

```bash
ip netns add wsl-deck-<name>                         # 命名空間存於該實例 rootfs 的 /run/netns
ip link add veth-<name> type veth peer name veth-<name>-in
ip link set veth-<name>-in netns wsl-deck-<name>
ip addr add 192.168.163.241/20 dev veth-<name>       # 共用 netns 這端
ip -n wsl-deck-<name> addr add 192.168.163.242/20 dev veth-<name>-in
ip -n wsl-deck-<name> link set veth-<name>-in up
ip link set veth-<name> up
ip -n wsl-deck-<name> route add default via 192.168.163.241
# 服務：nsenter --net=/run/netns/wsl-deck-<name> <啟動命令>
```

### 4.2 App 整合要點

- 啟動實例時（root）建立 netns 與 veth；停止時刪除。
- 服務啟動命令需包 `nsenter`（App 目前直接開終端／由 systemd 起服務，改動面較大）。
- IP 分配：由 App 管理 `192.168.163.233-254` 池，避免與 `.232` 衝突，記錄在設定檔。
- portproxy 指向該 netns 的 IP。

### 4.3 風險

- systemd 服務（MySQL／Tomcat）預設跑在共用 netns，需改 unit（`NetworkNamespacePath=`）或由 App 用 `nsenter` 拉起。
- 非持久：WSL 重啟後全部重建。
- 需要 iptables/NAT 才可對外上網；DNS 需複製 `/etc/resolv.conf`。
- 出錯會影響共用協議棧（veth 建錯可能斷網），需提供「一鍵清除」。
- **Windows 端可達性是最大未知**：netns 內的 IP 不在 `eth0` 上，`eth0` 不會代回 ARP。要讓 Windows／外部直接連，需在共用 netns 開 `proxy_arp`，或維持 portproxy 指向 `.232` 再用 `socat` 轉入 netns。後者等於對外仍只有一個 IP。
- 每個實例的 `/run/netns` 存在各自 rootfs，互不可見；建立 netns／veth 必須由「該實例自己」以 root 執行，不能跨實例操作。

### 4.4 與方案 B 的關鍵差異

| 問題 | B IP 別名 | C 獨立 netns |
|------|-----------|--------------|
| 兩個實例都有 3306 | 不行 | 可以 |
| Windows 直接連新 IP | 較可能（eth0 本地地址） | 需 proxy_arp／中繼 |
| 服務是否需要改啟動方式 | 不用 | 要（systemd drop-in 或 nsenter） |
| 故障影響面 | 小，可單獨刪除地址 | 大，veth 設錯可能斷網 |

## 5. 建議

1. **若目的只是外部機器分別連 MySQL 與 Tomcat**：維持方案 A（不同 Windows 埠）即可，最穩定。
2. **若一定要「兩個 IP」對外可見**：先做方案 B，改動小、可逆；加先導驗證（見 §6）。
3. **若兩個實例真的都要各自 3306／8080**：只能方案 C 或 D。

## 6. 先導驗證（5 分鐘、可完全還原）

```powershell
wsl -d wsl-mysql -u root -- ip addr add 192.168.163.233/20 dev eth0
Test-NetConnection 192.168.163.233 -Port 3306
wsl -d wsl-mysql -u root -- ip addr del 192.168.163.233/20 dev eth0
```

- 通過條件：Windows 能 `ping`／TCP 連到 `.233`（需 MySQL 已綁 `0.0.0.0`，目前已綁）。
- 若 Windows 端不可達，方案 B 不成立，直接跳到 C 或 D。

## 7. 影響檔案（若採方案 B）

| 檔案 | 改動 |
|------|------|
| `app/config.py` | 實例設定新增 `static_ip`（空白＝預設），驗證格式與位址池衝突 |
| `app/wsl.py` | `get_distro_ip(name)` 支援覆寫 |
| `app/network.py` | 套用前確保別名存在；`build_admin_job` 用指定 IP |
| `app/admin.py` | 新增 root 端 `ip addr add/del` 的執行步驟（或走 `wsl -u root`） |
| `app/ui/detail_page.py` | 「目前 IP」顯示指定 IP，並加註「靜態別名」 |
| `app/ui/instance_settings_dialog.py` | 靜態 IP 欄位與說明 |
| `tests/test_network.py`、`tests/test_config.py` | IP 驗證、portproxy 位址、位址池衝突 |

## 8. 測試與驗收

| 項目 | 標準 |
|------|------|
| 單元測試 | 靜態 IP 格式／池衝突／portproxy 使用指定 IP |
| 實機 | 兩實例各套用不同 IP，`Test-NetConnection <ip> -Port <port>` 皆成功 |
| 重啟 | `wsl --shutdown` 後重新啟動，App 能自動重建別名並恢復連線 |
| 外部 | 同網段另一台機器可分別連 `13306`／`18080`（Private 網路或加開 Public） |

## 9. 風險與回滾

| 風險 | 對策 |
|------|------|
| 別名與 WSL 自動重配 IP 衝突 | 只使用 `.233` 以上、避開 DHCP 範圍；衝突時拒絕套用 |
| 改壞共用協議棧（方案 C） | 提供 `ip link del`／`ip netns delete` 一鍵清除；先做先導驗證 |
| 使用者誤以為有隔離 | UI 明示「方案 B 非隔離」 |

## 10. 確認清單

- [ ] 先做 §6 先導驗證（加／測／刪 `.233`，可完全還原）
- [ ] 依結果選方案：A（維持現狀）／B（IP 別名）／C（netns）／D（獨立 VM）
- [ ] 若做方案 B：靜態 IP 由使用者手填，還是由 App 自動從位址池分配？
- [ ] 若做方案 B：實例停止時是否立即移除別名？

確認後才動工。
