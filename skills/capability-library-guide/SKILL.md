# 能力库说明

当你需要发现或使用能力库中的能力时，按以下方式工作。

## 什么时候使用

- 用户任务可能需要专门的工作流程、领域知识或工具。
- 你不确定本地是否已有相关 Skill 或 MCP。
- 用户明确要求“查能力库”“加载 MCP”“使用某个能力”。

## 推荐流程

1. 调用 `python tools/advisor/ability_suggest.py "需求描述"`。
2. 查看返回的 Skill 路径、MCP 名称、描述、备注和推荐原因。
3. 如果需要 Skill，直接读取返回的 `path`。
4. 如果需要 MCP，先调用 `python tools/mcp/load_mcp.py --name "名称或ID"` 获取完整工具列表。
5. 选择具体工具后，调用 `python tools/mcp/use_tool.py --mcp "名称或ID" --tool "工具名" --params-json "{...}"`。

## 注意事项

- Skill 是普通 Markdown 文件，能力库不提供专门读取工具。
- MCP 不注册到任何 Agent 平台，由能力库脚本直接连接和调用。
- MCP 每次加载或调用都会重新连接，因此新增或更新 MCP 后不需要重启主 AI。
- `scope=remote` 和 `scope=all` 是未来扩展，第一版只实现本地。
