# Capability Library

## 核心理念与价值

能力库是一个全本地、纯文件、跨 Agent 平台的能力注册与调用层。它不绑定 Hermes、Codex、Claude Code 或其他平台；特别适用于多台设备、每个设备都有多个Agent平台的用户。

主 AI 只需要能运行命令行和读取文件即可使用。Skills 和 MCP 仅在实际需要时按需加载，不会在会话启动时就固定在系统提示词内。

本工具的核心价值有：

- **降低无效token**：可以注册任意数量的能力，不用担心MCP和skill太多而占用token。还能提高接收到首个 token 的速度（理论上）。
- **MCP 完全热加载**：修改或新增 MCP 后再次 load 立即可用，无需重启 Agent 或执行 `/reload-mcp`
- **MCP 与 Agent 平台完全解绑**：每个 MCP 只需维护一份配置，所有平台共用。且纯文本的设计让跨设备云同步非常容易。


## 项目架构

能力库由三个部分组成：**技能库**、**工具库**、**配套设施**。

### 技能库（skills/）

Markdown 文档合集，每篇文档就是一个 Skill——本质是给 AI 读的操作指南。每个 Skill 在 `skills/manifest.json` 中登记：

| 字段 | 说明 |
|------|------|
| name | Skill 名称 |
| id | 随机生成的唯一 ID |
| path | Skill 文件的相对路径 |
| description | 这个 Skill 是什么、适合什么场景 |
| remark | 使用建议或注意事项（人类标注） |

Skill 本身不执行任何代码，能力库只返回文件路径，由主 AI 自行读取。

### 工具库（mcps/）

MCP 注册表（`mcps/registry.json`），使用自建的统一格式登记所有 MCP 服务。每条记录包含名称、传输协议（stdio 或 streamable_http）、连接参数和说明文字。注册表同时会自动生成给人读的`registry.md`文档。API Key、Token 等直接写在配置中，配置即所见。

### 配套设施（tools/）

配套设施包括三个主要部分：前台咨询、MCP加载与调用接口、能力登记入库工具，主要包括：

| 模块 | 功能 |
|------|------|
| `advisor/ability_suggest.py` | 前台咨询LLM：接收自然语言需求，调用 DeepSeek 分析已注册的 Skill 和 MCP，返回推荐结果 |
| `mcp/load_mcp.py` | MCP 加载：按名称或 ID 连接 MCP 服务，获取完整工具列表和参数 schema，每次load会创建一个持续的会话进程 |
| `mcp/use_tool.py` | MCP 调用：连接指定 MCP，执行具体工具并返回结果 |
| `mcp/mcp_client.py` | MCP 客户端核心：实现 JSON-RPC 协议，支持 stdio 和 streamable_http 两种传输 |
| `registry/register_skill.py` | Skill 注册：校验路径、去重、写入清单并刷新 Markdown |
| `registry/register_mcp.py` | MCP 注册：校验传输类型和必填字段、写入注册表并刷新 Markdown |


## 使用流程

```
用户发出任务指令
        │
        ▼
  主 AI 分析需求，判断是否需要外部能力
        │
        ├── 不确定 → ① ability_suggest.py "需求描述"
        │              前台咨询 LLM 读取 Skill 清单 + MCP 注册表
        │              返回：推荐哪些 Skill、哪些 MCP、推荐理由
        │
        ▼
  ② 获取能力详情
        │
        ├── Skill → 直接读取返回的 Markdown 文件路径
        │
        └── MCP  → load_mcp.py --name "MCP名称"
        │           连接 MCP，列出所有可用工具及参数
        │
        ▼
  ③ 执行工具
        │
        └── use_tool.py --mcp "MCP名称" --tool "工具名" --params-json "{...}"
             MCP 执行工具，返回结果给主 AI
        │
        ▼
  主 AI 整合结果，完成用户任务
```

整个过程主 AI 只需运行命令行和读取文件，不需要任何平台特定的 SDK 或 API。

## 目录

```text
skills/                          Skill 文档和清单
  manifest.json                    Skill 注册清单（程序读）
  manifest.md                      Skill 注册清单（人读）
  capability-library-guide/        能力库使用说明
  intake-flow/                     入库流程说明
mcps/                             MCP 注册表
  registry.json                    MCP 注册表（程序读）
  registry.md                      MCP 注册表（人读）
tools/                            配套设施
  advisor/ability_suggest.py       前台咨询
  mcp/load_mcp.py                  MCP 加载
  mcp/use_tool.py                  MCP 工具调用
  mcp/mcp_client.py                MCP JSON-RPC 客户端
  mcp/relay.py                     stdio MCP relay 守护
  registry/register_skill.py       Skill 注册
  registry/register_mcp.py         MCP 注册
  registry/refresh_manifest_md.py  清单刷新
  lib/caplib.py                    公共库
docs/                             文档
  能力库设计思路.md
  AI引导提示词.md                  复制发给 AI 即可初始化能力库
tests/                            测试桩和参数文件
scripts/                          打包脚本
```

## 快速开始

1. 解压 release 包
2. 复制 `docs/AI引导提示词.md` 的全部内容发给你的 AI，AI 会自动完成初始化（了解机制、迁移现有 MCP/skill 入库）。
3. 确认可用后，移除Agent内部配置的MCP和skill。

### 日常命令速查

```powershell
python tools/advisor/ability_suggest.py "自然语言需求描述"          # 咨询该用什么
python tools/mcp/load_mcp.py --name "MCP名称"               # 加载 MCP，获取工具列表
python tools/mcp/use_tool.py --mcp "MCP名称" --tool "工具" --params-json "{...}"  # 调用工具
python tools/registry/register_skill.py --name "..." --path "..." --description "..." --remark "..."
python tools/registry/register_mcp.py --name "..." --transport stdio --params-file "params.json" --description "..." --remark "..."
```

详细用法见 `docs/能力库设计思路.md` 和内置 skill（`skills/capability-library-guide/SKILL.md`、`skills/intake-flow/SKILL.md`）。
