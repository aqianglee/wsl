# 風險、技術債與編碼約定

> 這份文件回答三個問題：**哪些操作會造成不可逆的後果？程式哪裡最脆弱？改東西時該遵守什麼風格？**

---

## 1. 破壞性操作清單

> 原則：本專案沒有「資源回收桶」。`wsl --unregister` 會**直接刪除整個安裝資料夾**，不會進回收桶。

| 操作 | 實際命令 | 影響面 | 可逆性 | 現有保護 | 程式位置 |
|------|---------|--------|--------|---------|---------|
| **刪除實例** | `wsl --terminate` → `wsl --unregister` | 該實例的整個安裝目錄（含 `ext4.vhdx`）被刪除；同時移除 `config.json` 內該實例的端口規則 | **不可逆**（除非有備份） | 需輸入實例名稱；預設勾選「先備份」（TAR）；系統實例禁用 | [distro_ops.py:292-306](../../wsl-deck/app/distro_ops.py#L292-L306)、[main_window.py:790-820](../../wsl-deck/app/ui/main_window.py#L790-L820) |
| **覆蓋式還原** | terminate → 選擇性備份現況 → `--unregister` → `--import` | 目前狀態被備份檔取代；未備份的變更永久消失 | **不可逆**（沒勾備份就沒有回滾來源） | 需輸入名稱；預設勾「先備份目前狀態」；失敗時自動用現況備份回滾 | [distro_ops.py:191-254](../../wsl-deck/app/distro_ops.py#L191-L254) |
| **VHDX 備份** | `wsl --shutdown` → `wsl --export --format vhd` | **所有**執行中的 WSL 實例被關閉，包含 Docker Desktop | 可回復（重新啟動即可），但會中斷使用者工作 | 對話框明示；僅 `vhd=True` 時執行 | [distro_ops.py:168-189](../../wsl-deck/app/distro_ops.py#L168-L189) |
| **全部關機** | `wsl --shutdown` | 所有實例，含系統實例 | 可回復 | 只在有執行中實例時可按；會二次確認 | [main_window.py:644-670](../../wsl-deck/app/ui/main_window.py#L644-L670) |
| **複製實例** | 先匯出 TAR 到 `backups\_tmp`，再 `--import` | 目標目錄被建立；暫存檔在結束時刪除 | 可回復（刪掉新實例） | 名稱與目錄校驗；失敗時自動 `--unregister` 新名稱 | [distro_ops.py:257-289](../../wsl-deck/app/distro_ops.py#L257-L289)、[main_window.py:767-788](../../wsl-deck/app/ui/main_window.py#L767-L788) |
| **套用端口規則** | `netsh portproxy add/delete` + `netsh advfirewall` | **全機**生效：`0.0.0.0:<port>` 對外開放；防火牆規則對 `localsubnet` 開放 | 可回復（刪規則），但若忘記清理會留下對外端口 | 一次 UAC；先刪後加；端口衝突檢查；規則名稱固定 `WSL Deck <name> <port>` | [admin.py:62-107](../../wsl-deck/app/admin.py#L62-L107) |
| **刪除快照** | `restic forget <id> --prune` | 該快照與其獨佔資料塊被永久刪除，倉庫立即縮小 | **不可逆** | 需在快照對話框中選取後按刪除 | [snapshot.py:518-538](../../wsl-deck/app/snapshot.py#L518-L538) |
| **按策略清理** | `restic forget --keep-* --prune` | 超出保留策略的快照被刪除 | **不可逆** | 保留策略在設定中，至少一項 > 0 | [snapshot.py:541-562](../../wsl-deck/app/snapshot.py#L541-L562) |
| **整機還原** | `restic restore <id> --target / --overwrite always` | 覆蓋整機檔案；**只覆蓋、不刪除多餘檔案** | 部分可逆（再還原另一份快照） | 排除 `/proc`、`/sys`、`/dev`、WSL 只讀掛載；只略過「純只讀錯誤」 | [snapshot.py:54-60](../../wsl-deck/app/snapshot.py#L54-L60)、[snapshot.py:371-410](../../wsl-deck/app/snapshot.py#L371-L410) |
| **改寫 `/etc/wsl.conf`** | `cp -n` 備份 → `cat > tmp` → `mv` | 預設使用者、systemd、automount、appendWindowsPath | 可回復（`.wsl-deck.bak`） | 寫入後重新讀取驗證；使用者必須存在 | [distro_settings.py:16-22](../../wsl-deck/app/distro_settings.py#L16-L22)、[distro_settings.py:261-341](../../wsl-deck/app/distro_settings.py#L261-L341) |
| **寫入代理腳本** | `cat > /etc/profile.d/99-wsl-deck-proxy.sh` | 該實例所有新 shell 的 `*_PROXY` 環境變數 | 可回復（取消勾選即刪檔） | 寫入後重讀驗證 | [distro_settings.py:169-200](../../wsl-deck/app/distro_settings.py#L169-L200) |
| **設為預設實例** | `wsl --set-default` | 全機預設值改變；影響使用者直接輸入 `wsl` 的行為 | 可回復（再設另一個） | 系統實例禁用 | [wsl.py:270-272](../../wsl-deck/app/wsl.py#L270-L272) |
| **切換 WSL 版本** | `wsl --set-version` | 版本 1↔2 轉換需要完整複製磁碟，可能很久 | 可回復（再轉回） | 需先終止；維護區有說明 | [distro_settings.py:390-391](../../wsl-deck/app/distro_settings.py#L390-L391) |
| **壓縮 VHD** | `wsl --manage --compact` | 實體檔案縮小；**無法還原已刪資料** | 不可逆 | 需先終止 | [distro_settings.py:382-387](../../wsl-deck/app/distro_settings.py#L382-L387) |
| **切換稀疏檔** | `wsl --manage --set-sparse` | VHDX 的配置方式改變；可能影響效能 | 可切回 | 需先終止 | [distro_settings.py:368-372](../../wsl-deck/app/distro_settings.py#L368-L372) |
| **開機自啟** | 寫 `HKCU\...\Run` | 每次登入自動啟動（`--silent` 到托盤） | 可回復（取消勾選） | 只有凍結後的 exe 可啟用 | [autostart.py:31-44](../../wsl-deck/app/autostart.py#L31-L44) |
| **全域代理** | 修改目前進程的 `*_PROXY` 環境變數 | 本進程與其所有子進程（`wsl.exe`、`curl.exe`、`powershell.exe`） | 可回復（停用時還原原值） | `apply_runtime` 會記住原值 | [proxy.py:56-96](../../wsl-deck/app/proxy.py#L56-L96) |

### 三條「做之前先想清楚」的規則

1. **任何會呼叫 `--unregister` 的流程，先確認備份路徑真的存在且大小合理。** 還原流程會在 `unregister` 之後才 `import`，中間失敗就只剩現況備份。
2. **VHDX 匯出會停掉整個 WSL**。如果使用者正在 Docker Desktop 裡跑容器，這一步會中斷它。UI 已提示，但不要在其他流程中「順手」呼叫 `backup_instance(vhd=True)`。
3. **portproxy 是全機的**。同一台機器上的其他工具可能共用端口；刪除規則時只刪 `listenport`，不區分來源。程式的保護只有「同一 Windows 端口只允許一條規則」。

---

## 2. 權限模型

| 操作 | 需要管理員？ | 原因 |
|------|------------|------|
| 列出／啟停／終止實例 | 否 | 目前使用者的 WSL 實例 |
| 新增（`wsl --install`／`--import`） | 通常否 | 寫入使用者有權限的目錄即可 |
| 備份／還原／複製／刪除 | 否 | 同上（但 `--unregister` 會刪目錄） |
| 修改 `/etc/wsl.conf` | 否 | 以 `-u root` 在實例內執行，不需要 Windows 管理員 |
| 讀寫 `HKCU` 註冊表 | 否 | 目前使用者 hive |
| **portproxy＋防火牆** | **是** | `netsh` 的全機設定需要提升權限 |
| 開機自啟 | 否 | `HKCU\...\Run` |

### 提權的邊界

- 只有 [`network.apply_rules`](../../wsl-deck/app/network.py#L194) 會走到 [`run_admin_job`](../../wsl-deck/app/admin.py#L144)。
- 提權子進程的生命週期只有「執行 netsh 批次」這幾秒，結束即退出；主程式全程普通權限。
- 使用者取消 UAC 時：PowerShell 退出碼 `1223`、沒有 `result.json` ⇒ `AdminResult(denied=True)`（[admin.py:194-199](../../wsl-deck/app/admin.py#L194-L199)）。**不會重試**，也不會退回「只改一半」的狀態。
- 批次是「先刪後加」：即使新增失敗，舊規則也已被清掉。這是刻意的（避免新舊衝突），但代表失敗後可能出現「規則完全不存在」的中間狀態。

---

## 3. 資料安全與隱私

| 項目 | 現狀 | 風險 | 建議 |
|------|------|------|------|
| `snapshots\<name>\repo.pass` | **明文**存放 restic 倉庫密碼（[snapshot.py:126-135](../../wsl-deck/app/snapshot.py#L126-L135)） | 拿到檔案就能讀整份快照 | 至少把 `snapshots\` 放在受控目錄；未來可考慮 DPAPI |
| 備份檔（VHDX／TAR） | **未加密** | 內含完整 Linux 檔案系統（含金鑰、憑證） | 不要把 `backups\` 放在共用磁碟 |
| `config.json` | 含本機路徑、端口規則、代理主機 | 洩漏內網拓撲 | 已被 `.gitignore` 排除；不要貼到 issue |
| `logs\wsl-deck.log` | 含實例名、IP、執行的命令 | 同上 | 回報問題前先脫敏 |
| `%TEMP%\wsl-deck-*.job.json` | 提權工作的暫存檔，含 IP 與端口 | 短暫存在，結束即刪（[admin.py:203-204](../../wsl-deck/app/admin.py#L203-L204)） | 異常中斷時可能殘留，可手動清理 |
| 全域代理 | 會把 `*_PROXY` 寫進所有子進程環境 | 子進程（含第三方工具）會走代理 | 只在需要時開啟 |

---

## 4. 技術債分級

> 分級標準：**P1＝拖慢接手或直接影響新使用者**；**P2＝會引發故障或誤導**；**P3＝風格與整潔**。
> 每條都給「症狀／影響／建議改法／改動風險」，方便你排優先級。

### P1

| # | 問題 | 症狀 | 影響 | 建議改法 | 改動風險 |
|---|------|------|------|---------|---------|
| P1-1 | **MainWindow 是上帝類**：1,368 行、30+ 方法、10 個狀態旗標（[main_window.py:88-1368](../../wsl-deck/app/ui/main_window.py#L88-L1368)） | 改任何流程都要先讀完整個檔案；狀態旗標互相影響 | 新人上手成本最高；無法為流程寫測試 | 先抽出「操作服務」：備份／還原／新增各自成一個 `*_service.py`，MainWindow 只保留接線與 UI 狀態 | 中高：要逐條搬家並重跑 135 項測試；建議一次搬一個流程 |
| P1-2 | **預設工作目錄寫死開發機路徑**：[config.py:35](../../wsl-deck/app/config.py#L35) 的 `DEFAULT_CONFIG["workspace_root"] = r"D:\VirtualMachiles\wsl"` | 新使用者首次啟動，預設路徑不存在；`ensure_workspace` 只記 warning（[main.py:51-54](../../wsl-deck/main.py#L51-L54)） | 首次體驗直接壞掉；備份／新增會失敗 | 改成 `Path.home() / "WSLDeck"` 或 `app_dir()/workspace` | 低：改一個常數 + 補測試 |
| P1-3 | **發布包會帶開發機 `config.json`**：[build.ps1:29-32](../../wsl-deck/build.ps1#L29-L32) 複製應用根目錄的設定到 `dist`；iss 再用 `onlyifdoesntexist` 裝進去 | 使用者安裝後就繼承 `D:\VirtualMachiles\wsl` | 與 P1-2 疊加，等於預設路徑一定錯 | 發布前刪 `dist\WSL Deck\config.json`；或 build 時生成一份乾淨預設 | 低 |
| P1-4 | **沒有 lint／型別檢查／CI** | 重構靠人工；註解型別與實際不符不會被發現 | 回歸風險隨時間上升 | 加 `ruff` + `mypy`（先只檢查 `app/`），再掛一個跑測試的 CI | 低（但第一次會有大量 warning） |

### P2

| # | 問題 | 症狀 | 影響 | 建議改法 | 改動風險 |
|---|------|------|------|---------|---------|
| P2-1 | **命令模板是死代碼**：`config.json` 的 `commands` 區塊看起來可自訂，但 `Config.command()` 只在測試中使用（[test_config.py:92](../../wsl-deck/tests/test_config.py#L92)、[test_config.py:107](../../wsl-deck/tests/test_config.py#L107)） | 使用者改了 `commands` 完全沒效果 | 誤導＋設定膨脹 | 要嘛讓 `wsl.py`／`distro_ops.py` 真的走模板，要嘛刪掉整個 `commands` 與 `COMMAND_KEYS` | 中：前者要改多處呼叫；後者要改 `_validate` 與測試 |
| P2-2 | **兩套 subprocess 風格**：`wsl.py` 有統一封裝（[run_wsl_process](../../wsl-deck/app/wsl.py#L70)），但 `proxy.py`、`network.py`、`distro_settings.py`、`snapshot.py` 各自 `subprocess.run` | 編碼、`CREATE_NO_WINDOW`、逾時、錯誤處理四份實作略有差異 | 行為不一致；新增命令容易漏 | 抽出 `app/proc.py` 的 `run_process()`，統一 encoding／errors／flags／timeout | 中：需逐處替換並補測試 |
| P2-3 | **錯誤直接顯示給使用者**：`WslError(str)` 常是 `wsl.exe` 的原始 stderr | 使用者看到英文／簡體原文，不知道下一步 | 支援成本 | 在業務層映射常見錯誤（找不到發行版、空間不足、權限）成可操作文案，原文只進日誌 | 低 |
| P2-4 | **狀態判定靠字串比對**：[wsl.py:39-43](../../wsl-deck/app/wsl.py#L39-L43) 用 `"running"` 與中文字樣比對 | 系統語言變化／WSL 改字樣就失效 | 狀態顯示錯誤 | 用 `wsl.exe --list --running` 判斷；或同時保留字串比對作為 fallback | 低 |
| P2-5 | **詳情頁每 10 秒跑兩個子進程**：[main_window.py:972-982](../../wsl-deck/app/ui/main_window.py#L972-L982) 每次刷新都 `netsh show portproxy` + `hostname -I` | 開著詳情頁時每 10 秒一次 `netsh`／`wsl` | 耗電、風扇、筆電續航 | 詳情頁網路狀態改成「進入頁面時＋操作後＋手動刷新」，或拉長間隔 | 低 |
| P2-6 | **清理階段的異常被靜默吞掉**：`except WslError: pass`（[distro_ops.py:212-213](../../wsl-deck/app/distro_ops.py#L212-L213)、[distro_ops.py:303-304](../../wsl-deck/app/distro_ops.py#L303-L304)） | terminate 失敗沒有任何日誌 | 後續 `unregister` 才失敗，原因難追 | 改成 `logger.warning`（`snapshot.py:427-428` 已是正確示範） | 低 |
| P2-7 | **UI 幾乎沒有測試**：135 項全在純函式與解析層 | 快照、精靈、設定等 GUI 流程只能人工驗 | 每次改 UI 都要全手工回歸 | 先為「對話框取值 → 產生 plan」的純邏輯補測試；GUI 用 `QTest` 或 pytest-qt 另立 | 中 |
| P2-8 | **版本號硬編碼在打包腳本**：[build-installer.ps1:15](../../wsl-deck/build-installer.ps1#L15) | 升版後腳本誤報「找不到產物」 | 發布流程卡住 | 從 iss 讀版本，或改用 `Get-ChildItem dist\WSL-Deck-Setup-*.exe` | 低 |

### P3

| # | 問題 | 建議 |
|---|------|------|
| P3-1 | 逾時常數重複定義：`LONG_TIMEOUT = 3600` 同時出現在 [distro_ops.py:21](../../wsl-deck/app/distro_ops.py#L21) 與 [snapshot.py:38](../../wsl-deck/app/snapshot.py#L38) | 集中到一個 `constants.py` |
| P3-2 | 語言混用：應用內註解與 UI 是繁體，但 [build-installer.ps1:10](../../wsl-deck/build-installer.ps1#L10) 寫「请先安装」、部分 `plans/` 是簡體 | 對外文件與腳本統一繁體（或統一簡體），不要在同一個檔案混 |
| P3-3 | 顏色寫死：`#2D7FF9` 同時出現在 [main_window.py:142](../../wsl-deck/app/ui/main_window.py#L142)、[view_toggle.py:30](../../wsl-deck/app/ui/view_toggle.py#L30)、[icons.py:19](../../wsl-deck/app/ui/icons.py#L19) | 抽 `theme.ACCENT` 常數 |
| P3-4 | 沒有 `__version__`，UI 不顯示版本 | 加 `app/version.py`，打包與 UI 共用 |
| P3-5 | `_users`／`_workers` 集合只用來保活，沒有上限 | 文件化即可；或改用 `QThreadPool` 的完成訊號自動移除 |
| P3-6 | 圖標全部用 `QPainter` 現畫（[icons.py](../../wsl-deck/app/ui/icons.py)） | 好處是無資源依賴；代價是無法直接用設計稿替換。若日後要換圖標，先改 `icons.py` 的函式介面 |

---

## 5. AI 產碼特徵與應對

> 陳述事實，不做評價。知道這些模式，你 review 時會快很多。

| 特徵 | 具體表現 | 你該怎麼應對 |
|------|---------|------------|
| **骨架高度一致** | 每個業務模組都是「docstring → `from __future__` → 標準庫 → 本地 import → 常數 → dataclass → 純函式 → 執行函式」 | 可預測，照順序讀即可 |
| **過度防禦** | 大量 `isinstance`／`or ""`／`bool` 排除；邊界校驗很完整，內部也常重複校驗 | 邊界的保留；內部的可精簡 |
| **偏好新增而非重構** | 功能一直往 `main_window.py` 疊，檔案從幾百行長到 1,368 行 | 每次改動前先問「這段能不能抽出去」 |
| **重複樣板** | `subprocess.run` 的參數組合複製了 4 份；`LONG_TIMEOUT` 定義 2 次 | 第二次看到就抽 |
| **文件與計畫齊全** | `plans/` 有 24 份計畫，記錄了每個決策與踩過的坑 | 這是最有價值的遺產，先讀與你任務相關的那幾份 |
| **宣稱「已實測」但未必是 GUI** | 舊的 `plans/wsl-deck-handoff.md` 多處寫「已實作待 GUI 驗收」 | 要求證據：日誌、截圖、或你自己點一遍 |
| **會留 `# noqa` 但沒裝 linter** | 5 處 `# noqa: BLE001`（[admin.py:122](../../wsl-deck/app/admin.py#L122)、[workers.py:46](../../wsl-deck/app/ui/workers.py#L46)、[main_window.py:1326](../../wsl-deck/app/ui/main_window.py#L1326) 等） | 當成純註解，不要以為有工具在管 |
| **對 Windows 細節很敏感（踩過坑）** | UTF-8 BOM、`\x00`、本地化輸出、`CREATE_NO_WINDOW`、UAC 退出碼 1223 都有對應處理 | 這些是資產，不要「簡化」掉 |

### AI 最可能漏掉的三件事

1. **打包後的行為差異**（`sys.frozen`、`--admin-job` 入口、`_MEIPASS`）：開發期測不出來。
2. **失敗後的中間狀態**（例如 netsh 先刪後加、還原流程 unregister 後 import 前）。
3. **UI 文案與實際行為不一致**（例如「先備份」預設勾選，但使用者取消勾選後沒有二次警告）。

---

## 6. 編碼約定（本專案的既成事實）

> 這些不是「建議」，是**現有程式碼的實際風格**。改程式時照著做，diff 才不會突兀。

### 6.1 檔案結構

```python
"""模組一句話說明。"""          # 每個模組第一行

from __future__ import annotations   # 每個模組都有

import json                         # 標準庫
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal   # 第三方（僅 UI 層與 logbus）

from app.config import Config       # 本地，絕對匯入
```

- **不要用相對匯入**（`from .config import ...`）。
- 常數放模組頂部、`UPPER_CASE`。
- 私有函式加 `_` 前綴。
- 4 個空白縮排、UTF-8、檔名 snake_case。

### 6.2 型別與資料

- 所有函式簽名都有型別註解（含 `-> None`）。
- 資料載體用 `@dataclass`；能 `frozen=True` 就 frozen。
- 可選值用 `X | None`，不要 `Optional[X]`。
- 集合型別用 `list[str]`／`dict[str, Any]`，不要 `List`／`Dict`。

### 6.3 例外與日誌

- 業務層拋自訂異常（`WslError`／`ConfigError`）或內建 `ValueError`／`RuntimeError`。
- 轉拋時用 `raise ... from exc` 保留原因。
- 日誌一律 `logger.info("訊息 %s", 值)` 的惰性格式化，不要 f-string。
- 錯誤訊息用繁體中文、給使用者看得懂的話；原始錯誤放日誌。
- 背景工作的 `except Exception` 必須把錯誤**回報出去**（訊號／回傳值），不能只寫日誌。

### 6.4 執行緒與 UI

- 任何可能超過 0.2 秒的操作，一律走 `TaskWorker`（`_run_task` 或 `_run_operation`）。
- **禁止**在 UI 回呼中直接 `subprocess.run`。
- 背景執行緒**禁止**碰 widget；只能 `emit` 訊號。
- 進度文字統一透過 `stage` 參數注入。

### 6.5 設定與路徑

- `config.json` 只能透過 `Config` 讀寫；不要自己 `json.load`／`json.dump`。
- 路徑一律用 `Path`，不要字串拼接。
- 相對路徑一律相對於 `config.json` 所在目錄（`Config.resolve_path`）。
- 使用者可見目錄（instances／backups／snapshots）只能從 `Config.workspace()` 取。

### 6.6 視覺與文案

- UI 文案繁體中文、**不用 emoji**。
- QSS 用 `palette(base)`／`palette(mid)`／`palette(button)`，不要寫死背景色（強調色除外）。
- 間距與尺寸用模組頂部常數（`CARD_HEIGHT`、`BUTTON_HEIGHT` 等），不要散落魔數。
- 可用／禁用游標一律用 `refresh_cursor()`。

### 6.7 測試

- 命名：`class XxxTest(unittest.TestCase)`、方法 `test_xxx`。
- 外部依賴一律 `patch("使用它的模組.屬性")`。
- 暫存檔用 `tempfile.TemporaryDirectory()` + `with`。
- 不引入 pytest；執行方式是 `python -m unittest discover -s tests -q`。
- 純函式（解析、驗證、參數組裝）優先補測試；UI 流程目前不測。

---

## 7. 繼續用 AI 協作的建議

本專案是 AI 產出的，你大概率會繼續用 AI 改它。以下做法能讓品質穩定：

1. **先寫 plan 再動工**：沿用 `plans/wsl-deck-*.md` 的格式（現況 → 根因 → 方案 → 變更範圍 → 驗證 → 風險）。本專案 24 份計畫就是這樣累積出來的。
2. **要求 `file:line` 證據**：不要接受「應該是」「大概」；要求指出哪一行、哪個函式。
3. **每次改動後必跑**：
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -q
   ```
4. **GUI 由你親自驗**：AI 沙箱啟動的 GUI 會被回收，它無法真正「看到」畫面。
5. **限制改動範圍**：一次只搬一個流程、只改一個模組；這個專案的狀態旗標太多，大批重構很容易出錯。
6. **要求它先讀既有計畫**：`plans/wsl-deck-mvp.md`（需求）、`plans/wsl-deck-m3.md`／`m4.md`（流程）、`plans/wsl-deck-m7-*.md`（踩過的坑）。
7. **不要讓它「順手優化」**：本專案的風格是刻意統一的，順手改會產生大量無關 diff。

---

## 8. 接手第一個月建議順序

| 週次 | 做什麼 | 為什麼 |
|------|--------|--------|
| 第 1 週 | 讀 00／01／02；跑測試與 GUI；把工作目錄改成自己的路徑 | 先能跑、能看懂 |
| 第 2 週 | 讀 `plans/wsl-deck-mvp.md` 與 m3／m4；手動走一遍新增→備份→還原→刪除 | 理解產品意圖與破壞性流程 |
| 第 3 週 | 修 P1-2／P1-3（預設路徑與發布包），補對應測試 | 成本最低、影響最大 |
| 第 4 週 | 加 `ruff`＋`mypy`（只查 `app/`），處理第一批 warning | 為後續重構建立安全網 |
| 之後 | 再考慮拆 MainWindow（P1-1） | 沒有安全網之前不要動 |
