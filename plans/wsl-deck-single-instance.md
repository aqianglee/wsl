# 计划：单实例启动与托盘唤醒

## 1. 现状与问题

- 全仓无 `QLocalServer` / `QLocalSocket` / `QLockFile` 等单实例机制。
- [main.py](file:///D:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/main.py) 每次启动都直接 `QApplication` → `MainWindow`。
- 结果：托盘已有实例时再点桌面快捷方式，会再起一个进程，出现两个托盘图标、两套轮询、两次网络规则重套，且两个窗口互不同步。

## 2. 目标行为

| 场景 | 期望行为 |
| --- | --- |
| 无实例，普通启动 | 显示主窗口 |
| 无实例，`--silent`（开机自启） | 隐藏启动，只留托盘 |
| 已有实例，普通启动 | 唤醒并前置已有窗口，第二个进程直接退出 |
| 已有实例，`--silent` | 静默退出，不打扰当前窗口 |
| `--admin-job` | 保持现状：在单实例守卫之前处理，不受影响 |

## 3. 实现方案

### 3.1 新增 `app\single_instance.py`

实现采用「锁档判存在 + 本地管道触发唤醒」两层，避免小消息在进程立刻退出时丢失：

- `SingleInstance(key)`：
  - `acquire()`：`QLockFile`（放在用户 TEMP 下 `<key>.lock`）`tryLock(100)`；成功则再 `QLocalServer.listen(key)`，失败（已有实例）返回 `False`。
  - `activate_existing()`：连接既有实例的本地管道；连接成功即代表唤醒请求，立即断开；未连上重试 5 次（每次 100ms）。
  - `activated` 信号：服务端收到任意新连接就发出，无需传消息体。
  - `close()`：关闭服务端、移除管道、释放锁（测试与异常清理用）。
- `QLockFile` 自带异常退出检测：进程被杀留下的锁会被判为 stale 并回收，无需手工删除。
- 键名：`WSL Deck`（按确认，开发态与已安装版共用同一把锁）。

### 3.2 修改 `main.py`

`QApplication` 创建后、加载配置前插入：

1. 构造 `SingleInstance("WSL Deck")`。
2. `acquire()` 成功 → 继续原有启动流程。
3. `acquire()` 失败（已有实例）：
   - `--silent`：直接 `return 0`，静默退出，不打扰；
   - 普通启动：`activate_existing()` 后 `return 0`。
4. 窗口创建后：`instance.activated.connect(window.show_window)`。

`--admin-job` 分支位置不变，仍在最前面。

### 3.3 修改 `app\ui\main_window.py`

把现有 `_restore_window()` 改名为公开的 `show_window()`，并更新三处调用（托盘 `show_requested`、`_tray_reapply`、以及新的单实例信号）。行为仍是 `showNormal()` + `activateWindow()` + `raise_()`。

### 3.4 测试

- 新增 `tests\test_single_instance.py`：验证第二个实例 `acquire()` 失败、`activate_existing()` 能触发 `activated`、无服务端时返回 `False`；测试需 `QApplication`。
- 原有 129 项单测保持通过（实际共 132 项）。

## 4. 手工验收

1. 启动 `dist\WSL Deck\WSL Deck.exe --silent`，确认进程 1 个、窗口不显示、托盘有图标。
2. 再双击同一 exe：窗口应弹出并前置，`Get-Process "WSL Deck"` 仍为 1 个。
3. 退出应用后再启动：应正常打开（验证残留管道已清理）。
4. 连续快速双击两次：仍只保留 1 个进程（验证竞态处理）。

## 5. 风险与回滚

| 风险 | 处理 |
| --- | --- |
| 异常退出残留锁/管道导致无法启动 | `QLockFile` 自动识别 stale 锁；`listen()` 前 `removeServer` |
| 两个进程同时冷启动竞态 | `tryLock(100)` 原子抢锁，只有一个 `acquire()` 成功 |
| 旧版（已安装）进程不持锁 | 旧版无单实例逻辑，重装前可能与新版并存；新版互相之间仍只允许一个 |
| 唤醒时窗口最小化/隐藏 | `showNormal()` + `activateWindow()` + `raise_()` |
| 管理员助手被单实例拦截 | `--admin-job` 在校验前返回，不受影响 |

回滚：删除 `app\single_instance.py`，还原 `main.py`、`main_window.py` 即可。

## 6. 确认事项

- [x] 单实例范围：开发态与已安装版共用键名 `WSL Deck`
- [x] 已有实例时 `--silent` 静默退出，不唤醒
- [x] 新增单实例测试
- [x] 验证通过后提交并推送

## 7. 执行结果（2026-11-04）

- 实现改用 `QLockFile` + `QLocalServer`：锁档判存在，管道连接即唤醒，避免消息体在第二个进程立即退出时丢失。
- 单测：`132` 项全过（新增 3 项单实例测试）。
- 实机验证（`dist\WSL Deck\WSL Deck.exe`）：
  - `--silent` 启动后窗口 `MainWindowHandle = 0`（隐藏）；
  - 同命令内再普通启动：第二个进程 `ExitCode = 0`，进程数不增加，原实例窗口句柄变为 `987278`（已唤醒显示）；
  - 连续第二次 `--silent`：直接退出，不新增进程；
  - 强制杀掉实例后残留 `%TEMP%\WSL Deck.lock`，再次启动成功（stale 锁被回收）。
- 已安装的旧版本（15:43 启动）不持锁，重装新包后才会纳入同一单实例约束。
