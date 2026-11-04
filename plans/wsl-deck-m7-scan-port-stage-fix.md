# M7.2 修復計畫：掃描監聽端口 stage 參數錯誤

> 狀態：**已完成（2026-11-04，方案 A）**
> 目標：修好「掃描監聽端口」按下後彈出 `scan_tcp_ports() got an unexpected keyword argument 'stage'` 的問題，並避免同類操作再次踩坑。

## 1. 現象

於 instance 詳情頁按「掃描監聽端口」後，彈出錯誤對話框：

```
掃描監聽端口失敗
scan_tcp_ports() got an unexpected keyword argument 'stage'
詳細步驟請見日誌。
```

## 2. 根因（已核實）

1. [`_run_operation`](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/main_window.py#L671-L703) 一律建立
   `TaskWorker(fn, with_stage=True)`。
2. [`TaskWorker.run`](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/workers.py#L28-L32) 在
   `with_stage=True` 時無條件 `kwargs.setdefault("stage", self._emit_stage)`。
3. [`scan_tcp_ports(name)`](file:///d:/VirtualMachiles/wsl/wsl-deck/app/network.py#L85-L90)
   簽名只有 `name`，不接受 `stage`，於是拋出 TypeError。
   `main_window` 的呼叫點在
   [L1220-L1226](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/main_window.py#L1220-L1226)。

## 3. 影響範圍（同類隱患）

`_run_operation` 目前用於 10 個操作，其中以下函數同樣不接受 `stage`，按下按鈕會得到相同錯誤，
只是本次先回報了掃描端口：

| 操作 | 呼叫函數 | 簽名位置 |
|---|---|---|
| 掃描監聽端口 | `scan_tcp_ports(name)` | [network.py#L85](file:///d:/VirtualMachiles/wsl/wsl-deck/app/network.py#L85) |
| 套用 instance 設定 | `apply_settings(name, version, settings)` | [distro_settings.py#L261](file:///d:/VirtualMachiles/wsl/wsl-deck/app/distro_settings.py#L261) |
| 切換 WSL 版本 | `set_version(name, version)` | [distro_settings.py#L390](file:///d:/VirtualMachiles/wsl/wsl-deck/app/distro_settings.py#L390) |
| 切換 Sparse VHD | `set_sparse(name, enabled)` | [distro_settings.py#L368](file:///d:/VirtualMachiles/wsl/wsl-deck/app/distro_settings.py#L368) |
| 壓縮 VHD | `compact_vhd(name, vhdx_path)` | [distro_settings.py#L382](file:///d:/VirtualMachiles/wsl/wsl-deck/app/distro_settings.py#L382) |

（其餘 `create/backup/restore/clone/delete`、`apply_rules` 都已接受 `stage`，不受影響。）

## 4. 修法（推薦 A，請確認要 A 還是 B）

### 方案 A：在 `TaskWorker` 依簽名決定是否注入 `stage`（推薦）

- 在 `app/ui/workers.py` 新增私有輔助 `_accepts_stage(fn)`：
  - `inspect.signature(fn)` 取得參數；
  - 有 `stage` 具名參數或有 `**kwargs` 時回傳 True；
  - `signature` 取不到時回傳 False。
- `TaskWorker.run` 改為 `if self.with_stage and _accepts_stage(self.fn):` 才注入。
- 效果：一次修好上表 5 個操作；支援 `stage` 的長操作仍會更新進度文字；
  不支援的函數不再被強塞參數，UI 與業務層簽名都不用改。
- `functools.partial` 會被 `inspect.signature` 正確攤平，`partial(scan_tcp_ports, name)`
  解析結果為 `()`，因此不會注入。

### 方案 B：只給 `scan_tcp_ports` 加 `stage` 參數（最小改動，只修本次回報）

```python
def scan_tcp_ports(name: str, stage: Stage | None = None) -> list[int]:
    if stage:
        stage(f"正在掃描 {name} 的監聽端口…")
    ...
```

- 只修本次 bug，但「套用設定／切換版本／Sparse／壓縮 VHD」仍會留著同一顆雷。
- 與 `apply_rules`、`distro_ops` 的 `stage` 慣例一致，但需逐一補齊其他 4 個函數才算完整。

## 5. 變更範圍（方案 A）

| 檔案 | 變更 |
|---|---|
| `app/ui/workers.py` | 新增 `_accepts_stage()`；`run()` 僅在支援時注入 `stage` |
| `tests/test_workers.py` | 新增測試：一般函數不接受 `stage` 時不注入、接受時注入、`partial` 攤平判斷、`**kwargs` 視為接受 |

不動 UI 文案、不動 `app/network.py`、`app/distro_settings.py` 的業務簽名。

## 6. 驗證

1. `python -m py_compile app\ui\workers.py`。
2. `python -m unittest discover -s tests -q` 全過（含新增測試）。
3. 手動驗證（啟動 app）：
   - 對執行中的 `wsl-mysql` 按「掃描監聽端口」→ 正常列出端口或提示沒有端口，不再彈 TypeError；
   - 順帶抽查「套用設定」「切換 WSL 版本」「Sparse」「壓縮 VHD」不再出現同類錯誤。

## 7. 風險

| 風險 | 對策 |
|---|---|
| `inspect.signature` 對 C 擴充或內建函數取不到簽名 | 捕獲 `TypeError/ValueError`，視為不支援，退回不注入 |
| 誤判而漏注入 `stage`，長操作沒有進度文字 | 以簽名判斷；有 `stage` 或 `**kwargs` 都會注入；補單元測試覆蓋 |
| 改動共用 worker 影響其他頁面（快照對話框） | 快照的 `task(stage=None)` 有具名 `stage`，行為不變；跑完整測試 |

## 8. 確認清單

- [ ] 同意採 **方案 A**（改 `TaskWorker` 依簽名注入，一次修好 5 個操作）。
- [ ] 或改採 **方案 B**（只加 `scan_tcp_ports` 的 `stage`，其餘暫不動）。
- [ ] 同意變更範圍：`app/ui/workers.py` + 新增 `tests/test_workers.py`。
- [ ] 同意驗證方式：單元測試 + 實機按一次「掃描監聽端口」。

確認後才動工。

## 9. 實作結果（2026-11-04）

- `app/ui/workers.py`：新增 `_accepts_stage()`；`TaskWorker.run` 改為只有目標函數接受 `stage`
  （具名參數或 `**kwargs`）時才注入，`functools.partial` 可正確攤平判斷。
- 新增 `tests/test_workers.py`：覆蓋一般函數、具名 `stage`、`**kwargs`、`partial` 與實際注入行為。
- 驗證：
  - `python -m py_compile app\ui\workers.py tests\test_workers.py` 通過。
  - `python -m unittest discover -s tests -q`：**129 項全過**。
  - 以實際呼叫物件檢查：`scan_tcp_ports`／`apply_settings`／`set_sparse`／`compact_vhd`／
    `set_version` 的 partial 皆判定為不接受 `stage`（不再注入）；`apply_rules` 仍為 True（保留進度文字）。
- 未改動 `app/network.py`、`app/distro_settings.py` 的業務簽名與 UI 文案。
