# AGENTS.md

给处理本仓库的 AI 看的工作规则。

务必先阅读开发版说明 `README.md`。

## 关于本仓库

这是一个开发版仓库，不含用户能力清单。`capability-entry/`、`skills/`、`CAPABILITY.md` 和 `mcps/registry.json` 属于用户实例，首次安装模板在 `templates/` 下。

开发版目录：
```
user-version/ # 用户版 README 源文件，不是开发版说明
templates/   # 新用户模板，仅在目标文件缺失时初始化
tools/mcp/   # MCP 调用工具
tools/lib/   # 共享库
scripts/     # 部署和打包脚本
tests/       # 自动化测试和测试用假 MCP
```

## 部署

先预览，再更新：

```powershell
python scripts/deploy.py <目标目录> --check
python scripts/deploy.py <目标目录>
```

更新器只按显式源文件到目标文件映射完整替换开发版受管文件。它不得覆盖 `capability-entry/`、`skills/`、`CAPABILITY.md`、`mcps/registry.json` 或其他未登记文件。

不部署到用户版：开发版 `README.md`、开发版 `AGENTS.md`、`tests/`、`scripts/`、`templates/`、`.gitignore`。

## 用户版更新铁律

当任务是把开发版更新或部署到用户版时：

1. 对用户版的写入只能由 `python scripts/deploy.py <目标目录>` 完成；执行前必须先运行 `--check` 并核对范围。
2. AI 可以做只读检查和哈希验证，但不得直接创建、修改、删除或移动用户版中的任何文件。
3. 不得直接修改 `capability-entry/SKILL.md`、其他 Skill、MCP 注册表、用户能力清单、会话文件、临时文件或运行状态；不得代替用户完成脚本提示的手动迁移。
4. 如果脚本输出警告或提示需要手动迁移，只向用户报告原因、目标文件和建议改动，由用户决定并另行授权。
5. “更新用户版”只授权运行更新脚本，不构成维护用户数据或清理运行环境的授权。只有用户另行明确提出用户数据维护任务时，才按新的任务边界处理。

反例：更新脚本提示 `capability-entry/SKILL.md` 尚未引用新指南，AI 随后直接重写该 Skill。这属于越权，即使内容正确也禁止执行。
