# 入库流程

当用户要求把 Skill 或 MCP 加入能力库，或你判断某个能力值得保存时，按以下流程执行。

## Skill 入库

0. 先检查已有 skill 是否包含相同或相似内容（必须，避免重复创建）。
1. 在 `skills/` 下创建独立目录。
2. 将 Skill 正文保存为 `SKILL.md`。
3. 准备名称、描述、备注和相对路径。
4. 调用注册工具：

```powershell
python tools/registry/register_skill.py --name "名称" --path "skills/example/SKILL.md" --description "描述" --remark "用户备注（可选）"
```

注册工具会检查文件是否存在、路径是否在 `skills/` 下、清单是否重复，然后写入 `skills/manifest.json` 并刷新 `skills/manifest.md`。

## MCP 入库

第一版只接受能力库统一格式，不自动翻译其他平台格式。Key 和 Token 直接写在 params 中，不使用占位符。

### stdio 类型

**本地 Python 脚本：**

```json
{
  "command": "python",
  "args": ["D:\\path\\to\\run_mcp.py"],
  "env": {},
  "cwd": null
}
```

**npm/npx 全局命令（Windows 需完整路径）：**

```json
{
  "command": "C:\\Users\\用户名\\AppData\\Roaming\\npm\\npx.cmd",
  "args": ["@playwright/mcp@latest"],
  "env": {},
  "cwd": null
}
```

**需要环境变量：**

```json
{
  "command": "node",
  "args": ["D:\\path\\to\\mcp-server.cjs"],
  "env": {
    "SIYUAN_API_URL": "http://127.0.0.1:6806",
    "SIYUAN_TOKEN": "你的思源Token"
  },
  "cwd": null
}
```

### streamable_http 类型

**带 Authorization header：**

```json
{
  "url": "https://api.example.com/mcp",
  "headers": {
    "Authorization": "Bearer 你的API-Key"
  }
}
```

**带查询参数 Token：**

```json
{
  "url": "https://mcp.example.com/mcp/?apiKey=你的API-Key"
}
```

### 注册命令

```powershell
python tools/registry/register_mcp.py --name "名称" --description "描述" --remark "备注" --transport stdio --params-json "{...}"
```

Windows 路径复杂时用 `--params-file` 替代 `--params-json`：

```powershell
python tools/registry/register_mcp.py --name "名称" --description "描述" --remark "备注" --transport stdio --params-file "params.json"
```

注册工具会检查传输类型和必填字段，然后写入 `mcps/registry.json` 并刷新 `mcps/registry.md`。

## 描述字段建议

- `description` 写能力是什么、适合什么任务、主要工具有哪些。
- `remark` 写什么时候优先使用、什么时候不要使用、权限或网络注意事项。
