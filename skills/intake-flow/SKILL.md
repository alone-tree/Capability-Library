# 入库流程

当用户要求把 Skill 或 MCP 加入能力库，或你判断某个能力值得保存时，按以下流程执行。

## Skill 入库

1. 在 `skills/` 下创建独立目录。
2. 将 Skill 正文保存为 `SKILL.md`。
3. 准备名称、描述、备注和相对路径。
4. 调用注册工具：

```powershell
python tools/registry/register_skill.py --name "名称" --path "skills/example/SKILL.md" --description "描述" --remark "备注"
```

注册工具会检查文件是否存在、路径是否在 `skills/` 下、清单是否重复，然后写入 `skills/manifest.json` 并刷新 `skills/manifest.md`。

## MCP 入库

第一版只接受能力库统一格式，不自动翻译其他平台格式。

标准输入输出 MCP 参数：

```json
{
  "command": "node",
  "args": ["server.js"],
  "env": {},
  "cwd": null
}
```

可流式 HTTP MCP 参数：

```json
{
  "url": "https://example.com/mcp",
  "headers": {
    "Authorization": "Bearer ${TOKEN_NAME}"
  }
}
```

调用注册工具：

```powershell
python tools/registry/register_mcp.py --name "名称" --description "描述" --remark "备注" --transport stdio --params-json "{...}"
```

注册工具会检查传输类型和必填字段，然后写入 `mcps/registry.json` 并刷新 `mcps/registry.md`。

## 描述字段建议

- `description` 写能力是什么、适合什么任务、主要工具有哪些。
- `remark` 写什么时候优先使用、什么时候不要使用、权限或网络注意事项。
