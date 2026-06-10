# 能力库说明

当你需要使用能力库中的能力时，按以下方式工作。

## 什么时候使用

- 用户任务可能需要专门的工作流程、领域知识或工具。
- 你不确定本地是否已有相关 Skill 或 MCP。
- 用户明确要求"查能力库""加载 MCP""使用某个能力"。

## 推荐流程

1. 调用 `python tools/advisor/ability_suggest.py "需求描述"`。
   前台咨询 LLM 读取 Skill 清单和 MCP 注册表，返回建议的 Skill 和 MCP。
2. 查看返回的 Skill 路径、MCP 名称、描述、备注和推荐原因。
3. 如果需要 Skill，直接读取返回的 `path`。
4. 如果需要 MCP，调用 `python tools/mcp/load_mcp.py --name "名称或ID"` 获取完整工具列表。
   load 默认保持连接（启动 relay 子进程），后续 use 自动复用。
5. 调用 `python tools/mcp/use_tool.py --mcp "名称或ID" --tool "工具名" --params-json "{...}"` 执行工具。
   复杂参数可用 `--params-file` 替代 `--params-json`（避免转义问题）。

如果不想保持连接：`load_mcp --no-keep-alive --name "名称"`。

## 注意事项

- Skill 是 Markdown 文件，能力库返回路径，你自行读取。不提供 read_skill 函数。
- MCP 不注册到任何平台，由能力库自己的 relay/HTTP client 直接连接和调用。
- 再次 load 同一个 MCP 会自动杀掉旧连接起新的（热加载）。
- Session 文件存在系统临时目录，不参与项目同步。
