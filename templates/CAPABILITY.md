# 能力库上下文

本文件是注入 AI 初始上下文的能力地图。不是 Skill，不包含完整维护流程，不展开 MCP 工具 schema。

## 能力库位置

```text
<能力库根目录>
```

## 使用原则

1. 处理非简单任务前，先看本文件判断是否已有可用 Skill 或 MCP。
2. 需要 Skill：读取对应 `SKILL.md`。
3. 需要 MCP：先运行 `load_mcp.py` 获取完整工具描述，再运行 `use_tool.py` 调用。
4. 维护能力库本身时，读取 `skills/capability-library-maintenance/SKILL.md`。

## 日常流程

```text
根据任务判断能力
  → 需要 Skill：读取对应 SKILL.md
  → 需要 MCP：load MCP 获取工具描述 → use MCP 调用
  → 整合结果回复用户
```

## Skill 入口

### 能力库维护

- 路径：`skills/capability-library-maintenance/SKILL.md`
- 用途：新增、修改、禁用、删除、整理能力库中的 Skill 或 MCP
- 触发：用户要求维护能力库时读取

<!-- 用户新增的 Skill 入口在此处补充 -->

## MCP 简表

MCP 配置以 `mcps/registry.json` 为准，完整工具列表必须通过 `load_mcp.py` 获取。

### 本地回声 MCP

- 名称：`本地回声 MCP`
- 用途：demo 和基础链路测试

<!-- 用户新增的 MCP 在此处补充 -->

## MCP 命令

所有命令在能力库根目录运行。

```powershell
python tools/mcp/load_mcp.py --name "<MCP名称或ID>"
python tools/mcp/use_tool.py --mcp "<MCP名称或ID>" --tool "<工具名>" --params-json "{...}"
python tools/mcp/use_tool.py --mcp "<MCP名称或ID>" --tool "<工具名>" --params-file "params.json"
```

Windows 下参数包含复杂引号时，优先使用 `--params-file`。

## 维护入口

维护能力库时读取 `skills/capability-library-maintenance/SKILL.md`。

维护完成后检查 `CAPABILITY.md` 和 `mcps/registry.json` 是否需要同步。
