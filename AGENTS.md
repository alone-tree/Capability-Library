# AGENTS.md

给处理本仓库的 AI 看的工作规则。

务必先阅读架构文档 `docs/能力库产品架构.md`。

## 关于本仓库

这是一个开发版仓库，不含用户能力清单。`CAPABILITY.md` 和 `mcps/registry.json` 属于用户实例，模板在 `templates/` 下。

开发版目录：
```
docs/        # 架构文档和引导提示词
templates/   # 新用户模板（CAPABILITY.md、mcps/registry.json）
skills/      # 内置维护 Skill
tools/mcp/   # MCP 调用工具
tools/lib/   # 共享库
scripts/     # 部署脚本
tests/       # 测试用假 MCP
```

## 部署

改了代码后运行：

```powershell
python scripts/deploy.py <目标目录>
```

更新模式：覆盖代码和内置 Skill，不碰用户的能力清单和自建 Skill。`--overwrite` 会连 `CAPABILITY.md` 和 `mcps/registry.json` 一起覆盖，仅在用户数据损坏时用。

不部署到用户版：`tests/`、`scripts/`、`.gitignore`。
