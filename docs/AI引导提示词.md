# AI 引导提示词

> 以下内容是一个可直接发给 AI 的提示词。
> 复制全部内容，粘贴到 Hermes、Claude Code 等任意 AI 平台，AI 将自动完成能力库的初始化。

---

我现在开始使用一个叫"能力库"的本地工具。它是一个跨 AI 平台的 skill 和 MCP 注册与调用系统。项目路径：`填入你的能力库解压路径`。

## 请你按以下步骤操作

### 第一步：了解能力库

读取以下两个文件，理解能力库的机制：

1. `skills/capability-library-guide/SKILL.md` — 能力库使用说明
2. `skills/intake-flow/SKILL.md` — 入库流程

### 第二步：将能力库注册为平台内置 skill

读取 `skills/capability-library-guide/SKILL.md` 后，将其内容注册到当前 AI 平台的内置 skill（或全局记忆）中，确保每次新会话启动时都能自动加载该指引。

这样 AI 在任何新会话中都知道能力库的存在和使用方式，不需要每次手动告知。

### 第三步：配置 API Key

复制 `config.example.json` 为 `config.local.json`，填入 DeepSeek API Key（用于前台咨询）。

### 第四步：盘点当前 MCP 和 skill

查看当前 AI 平台已配置的 MCP 服务列表和 skill 列表。

### 第五步：逐个迁移入库

对于每个 MCP：
- 按照 `skills/intake-flow/SKILL.md` 中的入库流程
- 将 MCP 配置转换为能力库统一格式
- 运行 `register_mcp.py` 注册

对于每个 skill：
- 将 skill 文件复制到 `skills/` 下
- 运行 `register_skill.py` 注册

### 第六步：更新全局记忆

在 AI 平台的全局记忆中记录：

1. 能力库路径
2. 使用方式：不确定需要什么能力时先调 `ability_suggest.py`；需要 MCP 时调 `load_mcp.py` + `use_tool.py`
3. load 默认保持连接，无需反复加载

---

## 备注

- 迁移完成后，可从 AI 平台配置中删除已迁移的 MCP 和 skill，由能力库统一管理【特别提示，这一步必须要先向用户确认，严禁在迁移后自动删除配置】。
- 能力库的 `config.local.json` 只需填 DeepSeek Key，MCP 的 Key 直接写在 `mcps/registry.json` 里。
- 想知道更多设计细节可读 `docs/能力库设计思路.md`。
