# 计划：替换自定义 App 图标（App 内 + exe + 快捷方式）

## 1. 输入资产（已验证可用）

仓库根目录三个文件：

| 文件 | 验证结果 |
| --- | --- |
| `wsl-desk-icon.ico` | 9 帧：16/20/24/32/40/48/64/128/256，32bpp，PNG 压缩帧，39,494 bytes；Qt `QIcon` 可读出全部 9 个尺寸 |
| `wsl-desk-icon-1024.png` | 1024×1024，带 Alpha |
| `wsl-desk-icon-master.svg` | 1024×1024，Qt（qsvg）可渲染，带 Alpha |

目视检查：256px 主体（蓝色圆角底板 + 叠层实例卡片 + 深色终端 `>_` + 右下齿轮）清晰；16px 仍可辨识终端符号，细节按预期简化。

## 2. 目标位置（统一资产目录）

新建 `wsl-deck\assets\`，把三个文件移入并统一命名为 `wsl-deck-*`：

- `wsl-deck\assets\wsl-deck-icon.ico` ← `wsl-desk-icon.ico`
- `wsl-deck\assets\wsl-deck-icon-1024.png` ← `wsl-desk-icon-1024.png`
- `wsl-deck\assets\wsl-deck-icon-master.svg` ← `wsl-desk-icon-master.svg`

根目录原文件删除（移动而非复制，保持仓库根干净）。

## 3. 代码改动

| 文件 | 改动 |
| --- | --- |
| `app\ui\app_icon.py` | `app_icon()` 优先加载 assets 内的 ICO；开发态取 `app_dir()\assets`，冻结后取 PyInstaller 的 `sys._MEIPASS`（即 `_internal`）。文件缺失时回退到现有 QPainter 绘制。窗口、托盘、快照对话框自动继承。 |
| `WSL Deck.spec` | `icon="assets/wsl-deck-icon.ico"`；`datas` 增加 `("assets/wsl-deck-icon.ico", "assets")`，PyInstaller 6 会把它收进 `_internal\assets`。 |
| `build.ps1` | 删除调用 `make_app_icon.py` 的两段；同时修复 PowerShell 5.1 把 PyInstaller stderr 当终止错误的问题（改 `Continue` + 日志档 + 退出码判断）。 |
| `installer\make_app_icon.py` | 删除（不再使用）。 |
| `installer\WSL Deck.ico` | 删除旧生成图标（仅被旧 spec 引用）。 |
| `installer\WSL Deck.iss` | 不改快捷方式图标（`IconFilename` 指向 exe，自动继承）；仅新增 `SetupIconFile=..\assets\wsl-deck-icon.ico`，让安装程序本身也用新图标（依确认）。 |

## 4. 三处覆盖关系

1. **App 内**：`app_icon() → assets\wsl-deck-icon.ico`，覆盖主窗口、托盘、快照对话框。
2. **exe**：spec 的 `icon=` 嵌入 `assets\wsl-deck-icon.ico`。
3. **桌面 / 开始菜单**：安装器快捷方式使用 `{app}\WSL Deck.exe` 的嵌入图标，无需额外配置。

> 依确认一并替换：`WSL-Deck-Setup-1.0.0.exe`（Inno Setup 安装程序）通过 `SetupIconFile` 使用同一枚 ICO。

## 5. 执行步骤

1. 建 `wsl-deck\assets`，移动并改名为 `wsl-deck-icon.ico` / `-1024.png` / `-master.svg`。
2. 改 `app_icon.py`、`WSL Deck.spec`、`build.ps1`。
3. 删除 `installer\make_app_icon.py`、`installer\WSL Deck.ico`。
4. 跑 `python -m unittest discover -s tests -q`（预期 129 项全过）。
5. 跑 `.\build.ps1` → 检查 `dist\WSL Deck\assets\wsl-deck-icon.ico` 存在。
6. 用 `System.Drawing.Icon.ExtractAssociatedIcon` 从 `dist\WSL Deck\WSL Deck.exe` 提取图标并存 PNG，目视确认是新图标。
7. 用 Qt 从 `app_icon()` 渲染 16/32/48/256 存 PNG，目视确认 App 内图标为新图标。
8. 跑 `.\build-installer.ps1`，确认 `dist\WSL-Deck-Setup-1.0.0.exe` 重新生成，并提取其图标目视确认为新图标。
9. 可选：安装后检查桌面与开始菜单快捷方式图标。

## 6. 风险与回滚

| 风险 | 处理 |
| --- | --- |
| 冻结后找不到 ico | spec `datas` 显式打包；若仍缺失，`app_icon()` 回退旧绘制图标，不崩溃 |
| Qt 冻结后缺 qico 插件 | PyInstaller 的 PySide6 hook 会收集 `imageformats`；构建后检查 `_internal` 下是否有 `qico.dll` |
| 桌面/开始菜单仍显示旧图标 | Windows 图标缓存；重装或重建快捷方式后刷新 |
| 旧图标仍被引用 | 全仓 grep `WSL Deck.ico` / `make_app_icon`，确认无残留引用 |
| 误删资产 | 三个源文件已复制进 `assets` 并纳入 git；根目录原文件才删除 |

回滚：`git revert` 或恢复 `installer\WSL Deck.ico`、`make_app_icon.py` 与旧 `spec`/`build.ps1`。

## 7. 确认事项（2026-11-04）

- [x] 资产放到 `wsl-deck\assets\` 并统一命名 `wsl-deck-icon*`
- [x] 删除 `installer\make_app_icon.py` 与 `installer\WSL Deck.ico`
- [x] 构建验证（重跑 `build.ps1` 与 `build-installer.ps1`，覆盖 `dist` 产物）
- [x] 安装程序 Setup.exe 图标一并替换（`SetupIconFile`）
- [x] 验证通过后提交并推送

## 8. 执行结果（2026-11-04）

- 资产已移入 `wsl-deck\assets\`：`wsl-deck-icon.ico`（39,494 B）、`wsl-deck-icon-1024.png`（83,848 B）、`wsl-deck-icon-master.svg`（2,926 B）；仓库根目录已清空。
- 单元测试：`129` 项全过。
- `build.ps1` 首次执行失败：PowerShell 5.1 把 PyInstaller 的 stderr `INFO` 当成终止错误。已改为 `Continue` + `build\pyinstaller.log` + `$LASTEXITCODE` 判断；再次执行成功。
- PyInstaller 6 的 `datas` 落在 `dist\WSL Deck\_internal\assets\wsl-deck-icon.ico`，`app_icon.py` 已用 `sys._MEIPASS` 解析；模拟冻结路径验证 9 个尺寸全部可读。
- exe 图标：从 `dist\WSL Deck\WSL Deck.exe` 提取 32px 目视确认为新图标；`_internal\PySide6\plugins\imageformats\qico.dll` 存在。
- App 内图标：开发态与模拟冻结态均可读出 9 个尺寸（16/20/24/32/40/48/64/128/256）。
- 安装包：`dist\WSL-Deck-Setup-1.0.0.exe` 重新生成（28,986,507 B），提取图标确认已使用新图标。
- 桌面 / 开始菜单：快捷方式 `IconFilename={app}\WSL Deck.exe`，自动继承新 exe 图标。
