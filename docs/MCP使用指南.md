# MCP 使用指南

能力库通过 `load_mcp.py` 获取 MCP 的实时工具描述，再通过 `use_tool.py` 调用具体工具。

## 默认模式

`load_mcp.py` 默认使用一次性连接：完成初始化和工具枚举后立即关闭 MCP，不留下 relay 或 MCP 子进程。

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>"
```

随后使用 `use_tool.py` 调用工具。没有保活会话时，每次调用建立一次临时连接并在完成后关闭。

## 保活模式

只有需要连续复用同一个 stdio MCP 时才显式启用保活：

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>" --keep-alive
```

保活会话默认在空闲 300 秒后退出，并自动监控调用平台的 Owner 进程。Windows 下默认使用 Job Object，在 relay 结束时关闭 MCP 及其派生进程。

可通过 `--idle-timeout <秒>` 调整空闲超时，通过 `--owner-pid <PID>` 显式指定调用平台进程，通过 `--owner none` 禁用 Owner 监控，通过 `--no-kill-process-tree` 禁用 Windows 子进程树联动关闭。

## 显式关闭

任务完成后应主动关闭保活会话：

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>" --close
```

关闭成功后，relay、MCP 子进程和会话文件都会被清理。

## 调用工具

简单参数可以使用 `--params-json`；Windows 中文路径或复杂引号优先写入 JSON 文件，再使用 `--params-file`。

```powershell
python tools/mcp/use_tool.py --mcp "<MCP 名称或 ID>" --tool "<工具名>" --params-file "params.json"
```

## 最小自测

首次安装或更新运行程序后，使用“本地回声 MCP”完成一次默认 load 和 use。需要验证保活生命周期时，再依次执行 keep-alive、use 和 close，并确认没有残留会话或进程。
