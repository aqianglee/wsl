# MySQL 起不來：netns 內已有一份 mysqld，原 unit 無限重試

> 狀態：**已執行**（2026-11-10，採 §4 + §5 第 1、2 點，mask 方式為 `--runtime`）
> 日期：2026-11-10
> 實例：`wsl-mysql`（C 方案／臨時模式，隔離 IP `192.168.163.231`）

## 1. 結論

**不是 MySQL 壞了，是同一個 datadir 被兩個 mysqld 搶。**

- 11:00:27 WSL Deck 套用 C 方案：停掉 `mysql.service`，改用 transient unit
  `wsl-deck-01edbb25-mysql.service` 在 netns 裡跑 mysqld（PID 1125），**這份是正常在跑的**，netns 內 `0.0.0.0:3306` 有在聽。
- 11:02:30 有人在 instance 內執行了 `sudo service mysql start`（auth.log 有記錄），於是**共用網路裡又起了第二個 mysqld**。
- 第二個 mysqld 搶不到 `./ibdata1` 的檔案鎖（`error: 11` Resource temporarily unavailable），
  `mysql.service` 帶 `Restart=on-failure`，於是每 101 秒重試一次，現在 restart counter 已 12。

## 2. 證據

| 證據 | 內容 |
|------|------|
| `fuser -v /var/lib/mysql/ibdata1` | `mysql 1125`（netns 內）與 `mysql 5819`（原 unit）同時持有 |
| `/var/log/mysql/error.log` | 連續 `[MY-012574] [InnoDB] Unable to lock ./ibdata1 error: 11` → `Cannot open datafile './ibdata1'` → `Aborting` |
| `systemctl status wsl-deck-01edbb25-mysql` | active (running) since 11:00:27，PID 1125，`ss` 顯示 netns 內 `0.0.0.0:3306` LISTEN |
| `journalctl -u mysql` | 10:59:29 起、11:00:24 被停、11:02:30 又被起、之後每 101 秒失敗重試 |
| `/var/log/auth.log` | 11:02:30 `kyo : COMMAND=/usr/sbin/service mysql start` |
| portproxy | `0.0.0.0:13306 → 192.168.163.231:3306`（本來就是指向 netns 那份） |

## 3. 附帶損傷

`mysql.service` 每次啟動都會重建 `RuntimeDirectory=mysqld`，把 `/run/mysqld` 清空，於是 netns 內那份 mysqld 的
`/var/run/mysqld/mysqld.sock` 被砍掉（現在 `/run/mysqld` 是空的）。TCP 仍正常，但 instance 內用 socket 連的 client 會報
`Can't connect ... (2)`。

## 4. 立即恢復（不寫永久檔案，可逆）

```bash
sudo systemctl stop mysql            # 停掉重試迴圈
sudo systemctl reset-failed mysql
ls -l /run/mysqld                   # 預期空
sudo systemctl restart wsl-deck-01edbb25-mysql   # 重建 socket
ip netns exec wsl-deck-01edbb25 ss -lntp | grep 3306
```

驗收：`Test-NetConnection 127.0.0.1 -Port 13306` 成功；`mysql -h 127.0.0.1 -P 13306 -u <user> -p` 可連。

## 5. 程式面要修的地方（`app/netns.py`）

1. **臨時模式沒有防呆**：[apply_temporary](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/netns.py#L450-L496) 只 `systemctl stop` 原 unit
   （L455），沒有阻止它被再次啟動。任何人／任何指令（`service mysql start`、`systemctl start`、腳本）都會再起一份，
   直接和 netns 內那份搶 datadir。
   → 停掉後加 `systemctl mask --runtime <unit>`（只寫 `/run`，重開機自動失效，符合 temporary 語意）；
   cleanup／`_restore_shared_network`／下次 `apply_temporary` 開頭先 `unmask --runtime` 再動。
2. **無衝突偵測**：套用完只檢查 transient 是否 active（L489-L495），沒檢查原 unit 是否同時處於
   `active`/`activating`/`failed`。有衝突時應該回一個明確 warning 給 UI：「服務已在隔離網路執行，請勿再啟動 <unit>」。
3. **socket 目錄被搶**：`_prepare_runtime_dirs`（L432-L447）預先建好 `/run/mysqld`，但原 unit 每次啟動會清空它。
   第 1 點做完後不會再發生，可先不改；若要保險，可讓 transient 也帶 `RuntimeDirectory=mysqld`
   （但兩 unit 同時宣告同一目錄時 systemd 會警告，故僅在 1 未落地時才需要）。
4. `cleanup_all` 依賴 App 正常退出（L632-L647）；App 崩潰時 transient 會殘留到今天這種狀態。
   可考慮下次啟動 `apply_temporary` 時先做一次一致性檢查（有 transient 在跑就別再 stop/start 原 unit）。

## 6. 影響檔案

| 檔案 | 改動 |
|------|------|
| `wsl-deck/app/netns.py` | `apply_temporary` 加 mask/unmask、衝突偵測；`cleanup_temporary`／`_restore_shared_network` 加 unmask |
| `wsl-deck/tests/test_netns.py` | 腳本內容斷言：mask、unmask、衝突 warning |

## 7. 驗收

| 項目 | 標準 |
|------|------|
| 單元測試 | `pytest wsl-deck/tests/test_netns.py` 全綠 |
| 實機 | 套用臨時 C 方案後，`sudo service mysql start` 被 mask 擋下並給出清楚訊息；netns 內 3306 正常 |
| 對外 | `13306` 可連，`/run/mysqld/mysqld.sock` 存在 |
| 還原 | 關閉 C 方案後 `mysql.service` 回到共用網路正常啟動（unmask 生效） |

## 8. 確認清單

- [ ] 先做 §4 立即恢復（含重啟 netns 內 mysqld 以重建 socket）
- [ ] 是否一併做 §5 第 1、2 點加固？
- [ ] 若做加固：mask 用 `--runtime`（重開機失效），還是永久 mask？
