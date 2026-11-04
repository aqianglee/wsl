# M6.2 實作計畫：SOCKS5 代理（App 全域 ＋ Instance 級）

> 狀態：**待確認**
> 上層文件：[wsl-deck-m6-view-and-instance-settings.md](file:///d:/VirtualMachiles/wsl/plans/wsl-deck-m6-view-and-instance-settings.md)
> 目標：App 全域代理存 `config.json`，實例代理存實例內的 `/etc/profile.d`；兩者都使用本機 SOCKS5，方便在 WSL 內下載 GitHub 的 Linux rootfs／鏡像。

## 1. 已核實事實（2026-11-03）

| 項目 | 結論 | 方式 |
|------|------|------|
| WSL 網路模式 | NAT（`%USERPROFILE%\.wslconfig` 不存在） | 檢查檔案 |
| Windows 端 WSL 位址 | `vEthernet (WSL (Hyper-V firewall))` = `192.168.160.1` | `Get-NetIPAddress` |
| Windows 環境變數 | `wsl.exe` **不會**自動把 `HTTPS_PROXY` 傳給 Linux 程序 | 實測，輸出為空 |
| WSLENV | PowerShell 直接呼叫時可用；但由 Python 子進程啟動 `wsl.exe` 時未生效 | 實測，改用命令注入 |
| Windows curl | `curl 8.22.0`，支援 `--socks5-hostname` | `curl.exe --version` |
| 本機代理 | Clash Verge 服務存在，7890 可連通 `github.com` | `test_connection` 實測成功 |

推論：

- WSLENV 在 PowerShell 直接呼叫時可用，但由 Python 子進程啟動 `wsl.exe` 時實測未生效；全域代理改為在 `wsl -d <name> --` 之後注入 `env KEY=VALUE` 前綴，直接設定 Linux 端環境變數。
- NAT 模式下 WSL 內的 `127.0.0.1` 指向 WSL 自己；要連 Windows 代理必須使用 `192.168.160.1` 這類主機位址，且代理需允許局域網，或改用 mirrored 模式。
- `apt` 不支援 SOCKS5；`curl`、`git` 等遵循 `ALL_PROXY`／`HTTPS_PROXY` 的工具才會生效。

## 2. 範圍

**做：**

- 全域設定新增「SOCKS5 代理」：啟用、主機、埠、偵測 WSL 主機 IP、測試連線；存入 `config.json`。
- App 啟動與設定變更時，把代理寫入程序環境與 `WSLENV`，讓 App 啟動的 `wsl.exe`／終端／Linux 命令繼承。
- Instance 設定新增「SOCKS5 代理」：啟用、主機、埠、偵測實例內主機 IP；寫入該實例的 `/etc/profile.d/99-wsl-deck-proxy.sh`。
- 讀回與停用（移除腳本）。
- 單元測試：設定驗證、腳本產生／解析、WSLENV 合併。

**不做：**

- 不做 HTTP／HTTPS 代理，只支援 SOCKS5（`socks5h://`，DNS 也走代理）。
- 不支援代理帳號密碼（Clash 本機代理通常無驗證）。
- 不改 Windows 系統代理（WinINet／WinHTTP）。
- 不改 `.wslconfig` 的 `networkingMode`。
- 不處理 `wsl --install` 的 Windows 側下載；該流程可能使用系統代理而非環境變數，僅在文件中說明。
- 不為 apt／docker daemon 單獨配置代理。

## 3. 資料模型

### 3.1 `config.json` 新增

```json
"proxy": {
  "enabled": false,
  "host": "127.0.0.1",
  "port": 7890
}
```

驗證（`Config._validate`）：

- `proxy` 必須是物件。
- `enabled` 必須是 bool。
- `host` 必須是非空字串。
- `port` 必須是 1–65535 的 int（排除 bool）。

舊設定由 `_migrate()` 自動補鍵。

### 3.2 Instance 內的代理腳本

路徑：`/etc/profile.d/99-wsl-deck-proxy.sh`（root 寫入，權限 644）。

```sh
# Managed by WSL Deck. Do not edit.
export ALL_PROXY="socks5h://192.168.160.1:7890"
export all_proxy="$ALL_PROXY"
export HTTP_PROXY="$ALL_PROXY"
export http_proxy="$ALL_PROXY"
export HTTPS_PROXY="$ALL_PROXY"
export https_proxy="$ALL_PROXY"
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="$NO_PROXY"
```

停用時直接 `rm -f`。這是實例代理的唯一真相來源，不寫回 `config.json`。

## 4. App 全域代理（`app/proxy.py`）

```python
PROXY_ENV_KEYS = (
    "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy",
)

@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool
    host: str
    port: int

def parse_config(data: dict) -> ProxyConfig
def proxy_url(config: ProxyConfig) -> str          # socks5h://host:port
def current_proxy() -> ProxyConfig | None          # 供 run_wsl 注入
def apply_runtime(config: ProxyConfig) -> None     # 設定／還原 os.environ
def detect_wsl_host_ip() -> str                    # PowerShell 查 WSL 虛擬網卡
def test_connection(config: ProxyConfig) -> tuple[bool, str]
```

行為：

- `apply_runtime(enabled=True)`：設定 8 個環境變數（`ALL_PROXY` 使用 `socks5h://`，`NO_PROXY=localhost,127.0.0.1,::1`），並記錄 `current_proxy()`。
- `apply_runtime(enabled=False)`：移除本次設定的鍵，還原原本值。
- 由 `main.py` 啟動時呼叫；`MainWindow._apply_settings()` 在設定儲存後再次呼叫。
- **`run_wsl()` 注入**：若代理啟用且參數含 `--`，就在 `--` 後插入
  `env ALL_PROXY=... HTTP_PROXY=... HTTPS_PROXY=... NO_PROXY=... <原命令>`，
  讓 App 啟動的所有 Linux 命令直接取得代理。實測 WSLENV 在 Python 子進程下不可靠，故不依賴它。
- `open_terminal()` 不由 App 注入（無法通用地替換使用者 shell）；終端請用 Instance 級代理（`/etc/profile.d`）。
- `detect_wsl_host_ip()`：PowerShell
  `Get-NetIPAddress -AddressFamily IPv4 | ? InterfaceAlias -like '*WSL*' | Select -First 1 -ExpandProperty IPAddress`；
  失敗回傳空字串。
- `test_connection()`：`curl.exe --socks5-hostname <host>:<port> -I -L --max-time 10 https://github.com`；
  回傳（成功, 給使用者看的訊息）。找不到 `curl.exe` 時回傳失敗與提示。

## 5. Instance 代理（`app/distro_settings.py`）

`InstanceSettings` 追加（皆給預設值，不破壞既有建構）：

```python
proxy_enabled: bool = False
proxy_host: str = ""
proxy_port: int = 0
```

新增：

```python
PROXY_PATH = "/etc/profile.d/99-wsl-deck-proxy.sh"

def build_proxy_script(host: str, port: int) -> str
def parse_proxy_script(text: str) -> tuple[bool, str, int]
def detect_instance_host_ip(name: str) -> str   # ip route show default 的 gateway
def write_proxy(name: str, enabled: bool, host: str, port: int) -> None
```

- `read_settings()`：除了 `wsl.conf`，再讀代理腳本；有檔案且能解析出 `socks5h://host:port` 就視為啟用。
- `apply_settings()`：寫完 `wsl.conf` 後：
  - 啟用：寫入暫存檔 → `chmod 644` → `mv` 覆蓋 → 讀回驗證。
  - 停用：`rm -f`，再確認檔案不存在。
- `detect_instance_host_ip()`：`wsl -d <name> -- sh -c "ip route show default"`，取 `default via <ip>` 的 `<ip>`；失敗改用 `app.proxy.detect_wsl_host_ip()`。

## 6. UI

### 6.1 全域設定（右下角齒輪）

在既有表單中新增：

| 欄位 | 控制項 | 行為 |
|------|--------|------|
| SOCKS5 代理 | `QCheckBox("啟用 SOCKS5 代理")` | 未勾選時禁用下列欄位 |
| 代理主機 | `QLineEdit` + `QPushButton("偵測 WSL 主機 IP")` | 按鈕填入 `192.168.160.1` 這類位址 |
| 代理埠 | `QSpinBox` 1–65535 | 預設 7890 |
| 連線測試 | `QPushButton("測試連線")` + 狀態 `QLabel` | 背景執行 `curl.exe`，成功顯示綠色，失敗紅字 |

- 新增說明：
  「NAT 模式下 WSL 內需使用 Windows 主機 IP，且代理需允許局域網；apt 不支援 SOCKS5。」
- 儲存驗證：啟用時主機不可空白、埠必須合法。
- `values()` 回傳 `proxy` 子物件；`MainWindow` 寫入 config 後呼叫 `apply_runtime()`。

### 6.2 Instance 設定（詳情頁「設定」）

在「常用設定」群組追加：

| 欄位 | 控制項 |
|------|--------|
| SOCKS5 代理 | `QCheckBox("啟用 SOCKS5 代理")` |
| 代理主機 | `QLineEdit` + `QPushButton("偵測主機 IP")` |
| 代理埠 | `QSpinBox` 1–65535 |

- 與既有常用設定相同：需實例執行中才可編輯；停止時禁用。
- 說明文字：「寫入 `/etc/profile.d`，新登入 shell 生效；apt 不支援 SOCKS5。」
- 儲存驗證：啟用時主機不可空白、埠合法。
- 儲存成功仍提示「下次啟動生效」（`wsl.conf` 變更）與「新 shell 生效」（代理腳本）。

## 7. 任務拆解

1. **`app/proxy.py` ＋ 測試**：`ProxyConfig`、`merge_wslenv`、`apply_runtime`、`detect_wsl_host_ip`、`test_connection`。
2. **`config.py` ＋ 測試**：`DEFAULT_CONFIG["proxy"]`、驗證、遷移。
3. **`main.py`**：載入 config 後 `apply_runtime(parse_config(config.data["proxy"]))`。
4. **`settings_dialog.py`**：代理欄位、偵測按鈕、背景測試、驗證、`values()["proxy"]`。
5. **`main_window.py`**：儲存後套用代理（`apply_runtime`），沿用既有 `_apply_settings()`。
6. **`distro_settings.py` ＋ 測試**：`InstanceSettings` 擴充、腳本產生／解析、讀寫、偵測主機 IP。
7. **`instance_settings_dialog.py`**：代理欄位、偵測按鈕、驗證、`values()`。
8. **整合驗證**：單元測試、離屏 UI、實機代理連通。

## 8. 測試

| 測試 | 覆蓋 |
|------|------|
| `tests/test_proxy.py`（新增） | `parse_config`、`current_proxy`、`apply_runtime` 啟用／停用還原、`proxy_url` |
| `tests/test_config.py`（擴充） | proxy 預設鍵、缺鍵補齊、非法型別／埠 |
| `tests/test_distro_settings.py`（擴充） | 腳本產生、解析、停用解析為 false、空文字 |

GUI 與真實代理連通仍以手動驗收（沿用專案慣例，不引入 UI 自動化）。

## 9. 驗收

> 破壞性項目（寫入實例內 `/etc/profile.d`）只在臨時 instance 上做。

1. 單元測試全過。
2. **全域設定持久化**：填 `127.0.0.1:7890` → 儲存 → 重開 App 仍在。
3. **全域連線測試**：本機代理啟動時，「測試連線」對 `https://github.com` 成功；代理關閉時失敗並顯示原因。
4. **App 命令繼承**：全域代理改用 `192.168.160.1:7890` 後，執行
   `wsl -d ubuntu -- sh -c 'echo $ALL_PROXY'`（由 App 觸發的等價命令）應輸出 `socks5h://192.168.160.1:7890`。
5. **Instance 代理**：在臨時實例啟用代理並儲存 → 新開終端 → `echo $ALL_PROXY` 有值 → `curl -I https://github.com` 成功；重啟實例後仍存在。
6. **停用**：取消勾選並儲存 → 檔案 `/etc/profile.d/99-wsl-deck-proxy.sh` 消失，新 shell 不再有代理變數。
7. **不污染**：全域代理關閉時，App 啟動的 WSL 命令 `env | grep -i proxy` 不應出現本次注入的值（使用者自己的設定除外）。

## 10. 風險與回滾

| 風險 | 對策 |
|------|------|
| 代理只綁 `127.0.0.1`，WSL 連不到 | 設定說明＋偵測按鈕填入 Windows WSL 主機 IP；提示需開啟「允許局域網」或改 mirrored 模式 |
| `WSLENV` 覆蓋使用者既有設定 | `merge_wslenv` 保留原條目；停用時還原 |
| SOCKS5 對 apt／docker daemon 無效 | UI 明示僅 curl／git 等；不承諾 apt |
| `wsl --install` 不走環境變數 | 說明為已知限制，不改 Windows 系統代理 |
| `/etc/profile.d` 僅登入 shell 生效 | UI 明示「新登入 shell 生效」；既有 shell 需重開 |
| 代理腳本被使用者改動 | 讀回時以 `# Managed by WSL Deck` 標記與實際 `socks5h://` 判斷；無法解析視為停用 |
| 全域環境變數影響其他子程序 | 停用時移除；只設定 8 個標準代理鍵與 `NO_PROXY` |
| 無 git，改壞難回復 | 沿用 `_m6-snapshots\20261103-104503` 快照 |

## 11. 確認清單

- [ ] 同意只支援 SOCKS5（`socks5h://`），不做 HTTP 代理與帳密。
- [ ] 同意全域代理存 `config.json`，並以 `os.environ` + `WSLENV` 影響 App 啟動的 WSL 命令。
- [ ] 同意 Instance 代理存 `/etc/profile.d/99-wsl-deck-proxy.sh`，只影響新登入 shell。
- [ ] 同意提供「偵測 WSL 主機 IP」與「測試連線」。
- [ ] 同意 apt／docker daemon／`wsl --install` 不在保證範圍內。
- [ ] 同意 §9 的驗收範圍（實例寫入只在臨時 instance 做）。

確認後才動工。
