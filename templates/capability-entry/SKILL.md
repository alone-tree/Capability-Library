---
name: capability-entry
description: 能力库的唯一跨平台入口和能力地图。用于发现能力库中未直接注入平台的低频 Skill 与 MCP，并按需读取和调用。
---

# 能力库入口

能力库根目录是本文件所在目录的上一级。

## 使用流程

1. 根据下方能力清单判断是否有适用的 Skill 或 MCP。
2. 使用 Skill 时读取对应 `SKILL.md` 全文。
3. 使用 MCP 前读取 `../README.md` 中的 MCP 使用说明，先 load 获取实时工具描述，再用 use 调用。
4. 保活会话使用完后，执行 `python tools/mcp/load_mcp.py --name "<MCP 名称或 ID>" --close` 显式关闭。

## Skill 能力

<!-- 用户在这里维护低频 Skill 组及其入口。 -->

## MCP 能力

注册表：`../mcps/registry.json`

加载工具：`../tools/mcp/load_mcp.py`

调用工具：`../tools/mcp/use_tool.py`

<!-- 用户在这里维护已注册 MCP 的简要能力地图。 -->

## 维护能力库

新增或修改能力前先检查是否已有相同能力。修改 Skill 后同步更新本入口的能力地图；修改 MCP 后同步更新注册表和本入口摘要，并完成最小 load/use 验证。删除能力前必须获得用户明确确认，并检查入口、注册表和平台链接是否仍有引用。
