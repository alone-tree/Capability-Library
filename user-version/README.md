# Capability Library 用户版

这里是能力库用户版，不是开发仓库。平台通过 `capability-entry/SKILL.md` 发现能力，再按需读取 Skill 或调用 MCP。

## 目录

- `capability-entry/`：用户维护的能力库入口和能力地图。
- `skills/`：用户维护的低频 Skill 或能力组。
- `mcps/registry.json`：用户维护的 MCP 注册表。
- `tools/`：开发版提供的 MCP 通用运行程序。
- `CAPABILITY.md`：旧平台兼容入口，可按需保留。

`capability-entry/`、`skills/`、`mcps/registry.json` 和 `CAPABILITY.md` 属于用户数据，普通程序更新不会覆盖。

## 使用 MCP

以下命令在能力库用户版根目录执行。

默认 load 是一次性连接：获取实时工具描述后立即关闭，不留下后台进程。

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>"
```

需要连续复用同一个 stdio MCP 时，显式启用保活：

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>" --keep-alive
```

保活默认空闲 300 秒后退出，并监控调用平台进程。Windows 默认使用 Job Object，在 relay 结束时关闭 MCP 及其派生进程。可以使用 `--idle-timeout`、`--owner-pid`、`--owner none` 和 `--no-kill-process-tree` 调整。

任务完成后必须显式关闭保活会话：

```powershell
python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>" --close
```

调用工具：

```powershell
python tools/mcp/use_tool.py --mcp "<MCP 名称或 ID>" --tool "<工具名>" --params-file "params.json"
```

复杂参数优先写入 JSON 文件，再通过 `--params-file` 传入。

## 维护与更新

新增或修改 Skill、MCP 和能力地图时，维护对应的用户文件，并在删除能力前检查入口、注册表和平台链接是否仍有引用。

如需更新能力库程序或本说明文档，请前往能力库开发版处理；不要在当前用户版中寻找部署脚本。
