# Capability Library

能力库是一个本地、纯文件、跨 Agent 平台的能力注册与调用 demo。它不绑定 Hermes、Codex、Claude Code 或其他平台；主 AI 只需要能运行命令行和读取文件即可使用。

## 目录

```text
skills/     Skill 文档和清单
mcps/       MCP 注册表
tools/      前台咨询、MCP 加载/调用、注册维护工具
docs/       设计说明
```

## 配置

复制 `config.example.json` 为 `config.local.json`，填入 DeepSeek API Key。`config.local.json` 已加入忽略，不应提交真实密钥。

## 常用命令

咨询能力：

```powershell
python tools/advisor/ability_suggest.py "我需要检查一个本地网页并截图"
```

加载 MCP 并查看工具：

```powershell
python tools/mcp/load_mcp.py --name "示例 MCP"
```

调用 MCP 工具：

```powershell
python tools/mcp/use_tool.py --mcp "示例 MCP" --tool "工具名" --params-json "{}"
```

在 PowerShell 中传复杂 JSON 容易丢失双引号，也可以使用文件：

```powershell
python tools/mcp/use_tool.py --mcp "示例 MCP" --tool "工具名" --params-file "params.json"
```

注册 Skill：

```powershell
python tools/registry/register_skill.py --name "新 Skill" --path "skills/new-skill/SKILL.md" --description "描述" --remark "备注"
```

注册 MCP：

```powershell
python tools/registry/register_mcp.py --name "新 MCP" --description "描述" --remark "备注" --transport stdio --params-json "{""command"":""node"",""args"":[""server.js""],""env"":{},""cwd"":null}"
```

也可以使用 `--params-file` 传入 JSON 文件。

刷新 Markdown 清单：

```powershell
python tools/registry/refresh_manifest_md.py
```

## 使用流程

1. 主 AI 根据用户任务判断可能需要能力库。
2. 主 AI 调用 `ability_suggest.py`，传入自然语言需求。
3. 前台咨询 LLM 读取能力库说明、Skill 清单和 MCP 注册表，返回建议。
4. 主 AI 根据结果读取 Skill 文件，或调用 `load_mcp.py` 获取 MCP 工具描述。
5. 主 AI 调用 `use_tool.py` 执行具体 MCP 工具。

## 第一版边界

- Skill 只返回文件路径，不提供专门读取工具。
- MCP 支持 `stdio` 和 `streamable_http`。
- `load_mcp` 和 `use_tool` 每次独立连接，不维护常驻进程。
- 暂不实现远程能力库，只在接口中保留未来扩展位置。
