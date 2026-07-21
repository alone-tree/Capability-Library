# 能力库维护

当用户要求新增、修改、禁用、删除、整理能力库中的 Skill 或 MCP，或修正文档漂移时，读取本 Skill。

## 维护原则

1. 先读 `CAPABILITY.md` 和相关现有文件，再决定改法。
2. 改动克制，只改当前任务必需的文件，不要顺手修改其他文件看起来不合理的地方。
3. `CAPABILITY.md` 只放skill和MCP的描述，不放完整skill、不放完整MCP工具描述。
4. MCP 变更后必须运行 `load_mcp.py` 验证。
5. 不把密钥写进任何公开文件（若涉及密匙，需要询问用户意见）。

## 新增或修改 Skill

1. 检查 `skills/` 下是否已有相同或相近 Skill。
2. 创建或更新 `skills/<name>/SKILL.md`，写清楚触发场景、执行流程、验证方式。
3. 在 `CAPABILITY.md` 的 Skill 入口中补摘要和skill文档的相对路径（以能力库为根目录）。
4. 可以根据实际，对相互关联的一组skill放到同一组内，并只给这一组skill写一个详细描述，而非每个skill写一个描述。必要时可以创建一组skill的入口skill，并在入口skill中写各skill的描述、使用场景等。

## 新增或修改 MCP

1. 检查 `mcps/registry.json` 是否已有相同或相近 MCP。
2. 手动维护 `mcps/registry.json`，完整填写所需字段。
3. stdio：`params.command` 必填，`args` 必须是数组，`env` 必须是对象。
4. streamable_http：`params.url` 必填，`headers` 必须是对象。
5. 在 `CAPABILITY.md` 的 MCP 表中更新MCP的描述。一个MCP一条描述，内容可以稍详细，写清楚核心用途、主要工具，但不必加具体参数。
6. 运行 `python tools/mcp/load_mcp.py --name "<MCP名称>"` 验证。
7. 有测试参数时，再运行 `use_tool.py` 做最小调用。

需要连续调用同一个 stdio MCP 时，可在 load 命令后加 `--keep-alive`。保活会话默认空闲 300 秒后退出、自动跟随调用平台退出，并在 Windows 下连同 MCP 派生进程一起关闭；可用 `--idle-timeout`、`--owner`、`--owner-pid` 和 `--no-kill-process-tree` 调整。任务完成后执行 `python tools/mcp/load_mcp.py --name "<MCP名称>" --close` 显式关闭。

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
