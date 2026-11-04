# M7.1 修復計畫：整機還原避開 WSL 只讀掛載

> 狀態：**已完成（2026-11-04）**
> 目標：修好「快照 → 還原檔案」在還原 `/` 時，因 WSL 只讀掛載導致 `restic` 退出碼 1 而整體判定失敗的問題。

## 1. 現象

```
app.wsl.WslError: ignoring error for /usr/lib/linux-tools/6.18.54.1-microsoft-standard-WSL2:
lchown ...: read-only file system
...
Fatal: There were 3 errors
```

## 2. 根因（已核實）

- 目標實例 `/proc/mounts` 的只讀掛載：
  - `/usr/src/linux-headers-6.18.54.1-microsoft-standard-WSL2`（`ext4 ro`）
  - `/usr/lib/linux-tools/6.18.54.1-microsoft-standard-WSL2`（`ext4 ro`）
  - `/usr/lib/wsl/drivers`（`9p ro`）
  - `/mnt/wslg/distro`、`/tmp/.X11-unix`、`/run/credentials/*`、`/init`（其他只讀掛載）
- `restic restore /` 會對這些掛載點還原目錄並執行 `lchown`，只讀檔案系統拒絕；`restic restore --help` 明確寫「Exit status is 1 if there was any error」，所以只要有一個只讀掛載點就整體失敗。
- `restic restore` 支援 `-e/--exclude pattern`（可重複），可用來跳過這些路徑。

## 3. 修法

1. 在 `app/snapshot.py` 新增還原專用排除清單 `RESTORE_EXCLUDES`：
   - 沿用 `BASE_EXCLUDES`（`/proc`、`/sys`、`/dev`、`/run`、`/tmp`、`/mnt` 等）；
   - 加上 WSL 固定只讀路徑：`/usr/lib/wsl`、`/usr/lib/linux-tools`、`/usr/src/linux-headers-*`、`/init`。
2. 新增 `read_only_mounts(distro)`：在還原前讀取 `/proc/mounts`，動態收集所有 `ro` 掛載點（排除 `/`），一併作為 `--exclude`，避免換核心版本或使用者自訂掛載後再次踩雷。
3. 新增 `restore_arguments(snapshot_id, path, extra_excludes)` 純函式，集中組裝：
   `restore <id> --target / --include <path> --overwrite always` + 每個 `--exclude`。
4. `restore_path` 改用上述參數；還原流程與 UI 不變。
5. 若仍出現 `read-only file system` 以外的錯誤（例如執行中檔案被佔用），維持原本失敗提示，不吞錯。

## 4. 變更範圍

| 檔案 | 變更 |
|---|---|
| `app/snapshot.py` | 新增 `RESTORE_EXCLUDES`、`read_only_mounts()`、`restore_arguments()`；`restore_path` 套用 |
| `tests/test_snapshot.py` | 新增排除清單、`/proc/mounts` 解析、`restore_arguments` 測試 |

不改 UI 文案、不动 `backup` 流程（備份端已有 `--one-file-system`）。

## 5. 驗證

1. `python -m py_compile app\snapshot.py`。
2. `python -m unittest discover -s tests -q` 全過。
3. 實機（`Ubuntu-26.04`）：
   - 重建一份臨時快照；
   - 以新參數還原 `/usr/src`（含只讀的 `linux-headers-*`），確認退出碼 0、不再出現 `read-only file system`；
   - `restic check` 通過；
   - 清理臨時倉庫。
4. 不動使用者目前實例的 `/`，避免二次覆蓋。

## 6. 風險

| 風險 | 對策 |
|---|---|
| 動態排除把 `/` 之外的正常目錄誤排除 | 只收集 `ro` 掛載點；`/` 永不排除 |
| `/proc/mounts` 路徑含空白轉義（`\040`） | 解析時解碼常見八進位轉義 |
| 換核心版本後路徑變動 | 動態收集，不依賴固定版本號 |

## 7. 確認清單

- [ ] 同意還原時排除 WSL 只讀掛載（固定清單 + 動態 `/proc/mounts`）。
- [ ] 同意只改 `app/snapshot.py` 與測試，不動 UI。
- [ ] 同意驗證方式：還原 `/usr/src` 子路徑，不重跑整機 `/` 還原。

確認後才動工。

## 8. 實作修訂與結果（2026-11-04）

**修訂：** 實測發現 `restic restore` 的 `--include` 與 `--exclude` **互斥**（`Fatal: exclude and include patterns are mutually exclusive`），不能同時使用。最終實作：

- 還原 `/`：只用 `--exclude`，跳過 `BASE_EXCLUDES` + WSL 固定路徑 + 動態收集的 `ro` 掛載點。
- 還原指定路徑：只用 `--include`；若錯誤全為 `read-only file system`，降級為警告並回報「已略過 N 個唯讀掛載點」，其他錯誤仍失敗。

**驗證結果：**

- 單元測試 `123` 項全過。
- 整機 `/` dry-run：退出碼 `0`，`Restored 8413 files/dirs (16.976 MiB), skipped 36714 files/dirs`，參數被 restic 接受。
- 實際還原 `/usr/src`（包含只讀 headers 掛載）：成功，回報略過 1 個唯讀掛載點。
- 驗證用的臨時快照已刪除；使用者原有 2 份快照未受影響。
