# 能力库维护

当用户要求新增、修改、禁用、删除、整理能力库中的 Skill 或 MCP，或修正文档漂移时，读取本 Skill。

## 维护原则

1. 先读 `CAPABILITY.md` 和相关现有文件，再决定改法。
2. 改动克制，只改完成当前任务必需的文件。
3. `CAPABILITY.md` 只放入口和摘要，不放完整维护细则。
4. MCP 变更后必须运行 `load_mcp.py` 验证。
5. 不把密钥写进任何公开文件。

## 新增或修改 Skill

1. 检查 `skills/` 下是否已有相同或相近 Skill。
2. 创建或更新 `skills/<name>/SKILL.md`，写清楚触发场景、执行流程、验证方式。
3. 在 `CAPABILITY.md` 的 Skill 入口中补摘要。

## 新增或修改 MCP

1. 检查 `mcps/registry.json` 是否已有相同或相近 MCP。
2. 手动维护 `mcps/registry.json`，字段至少包含 `id`、`name`、`description`、`remark`、`enabled`、`transport`、`params`。
3. stdio：`params.command` 必填，`args` 必须是数组，`env` 必须是对象。
4. streamable_http：`params.url` 必填，`headers` 必须是对象。
5. 在 `CAPABILITY.md` 的 MCP 简表中更新摘要。
6. 运行 `python tools/mcp/load_mcp.py --name "<MCP名称>"` 验证。
7. 有安全测试参数时，再运行 `use_tool.py` 做最小调用。

## 禁用或删除能力

禁用优先于删除。

- 禁用 Skill：在 `CAPABILITY.md` 中移除入口，或标注已禁用。
- 禁用 MCP：将 `mcps/registry.json` 对应项的 `enabled` 设为 `false`，同步 `CAPABILITY.md`。
- 删除前必须得到用户明确确认。

## 更新 CAPABILITY.md

只写 AI 初始判断需要的信息：名称、路径、适用场景、重要限制。不写完整手册或长示例。

## 一致性检查

维护结束前检查：

1. `CAPABILITY.md` 是否让 AI 知道该能力存在。
2. `mcps/registry.json` 格式是否正确。
3. 新增或修改的 MCP 是否完成 load 测试。
4. 文档间是否一致。
