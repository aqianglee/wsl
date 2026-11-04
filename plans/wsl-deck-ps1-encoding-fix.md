# 修复计划：build-installer.ps1 输出乱码

## 1. 现象
执行 `build-installer.ps1` 成功后，控制台最后一行显示：

```
瀹屾垚锛?setup
```

本应为 `完成：D:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck\dist\WSL-Deck-Setup-1.0.0.exe`。

## 2. 根因
- 运行环境：Windows PowerShell `5.1.26100.9818`。
- [build-installer.ps1](file:///D:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/build-installer.ps1) 以 **UTF-8 无 BOM** 保存（首字节 `24 45 72 72 6F 72`）。
- PowerShell 5.1 对无 BOM 的 `.ps1` 按系统 ANSI（GBK）解码，UTF-8 字节被错误解读，产生 `瀹屾垚锛?`。
- [build.ps1](file:///D:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/build.ps1) 带 UTF-8 BOM（`EF BB BF`），所以中文输出正常。
- 控制台代码页已是 `65001`，不是输出端问题，而是脚本解析阶段的解码问题。

## 3. 修复方案（推荐）
把 `build-installer.ps1` 重新以 **UTF-8 with BOM** 保存，文件内容一字不改：
- 仅改变编码标记，不改逻辑、不改文案。
- PowerShell 5.1 与 PowerShell 7 都兼容 BOM。
- `WSL Deck.iss` 不含中文输出文案（仅注释），编译已成功，本次不动。

## 4. 验证
1. 检查首字节为 `EF BB BF`。
2. `git diff -- wsl-deck/build-installer.ps1` 应无文本增删（仅编码变化，git 可能视为无变更）。
3. 重跑 `.\build-installer.ps1`，末行应为 `完成：<setup 路径>`，无乱码。

## 5. 风险与回滚
| 风险 | 处理 |
| --- | --- |
| BOM 影响脚本执行 | PowerShell 5.1/7 均支持 UTF-8 BOM，无兼容问题 |
| 重复编译覆盖安装包 | ISCC 覆盖 `dist\WSL-Deck-Setup-1.0.0.exe`，产物一致 |
| 误改脚本逻辑 | 仅重写编码，不改内容；`git diff` 校验 |

回滚：去掉 BOM 存回即可（但乱码会复现）。

## 6. 确认清单
- [x] 同意只对 `build-installer.ps1` 添加 UTF-8 BOM
- [x] 同意重跑一次安装包编译做验证（约覆盖 `dist\WSL-Deck-Setup-1.0.0.exe`）

## 7. 执行结果（2026-11-04）

- `build-installer.ps1` 首字节已变为 `EF BB BF`；`git diff` 仅首行 BOM 变化，脚本逻辑未改。
- 重跑编译成功（ISCC：`Successful compile (31.828 sec)`）。
- 末行输出已正常：`完成：D:\workspaces\workspace-wsl-deck\wsl-deck\wsl-deck\dist\WSL-Deck-Setup-1.0.0.exe`。
