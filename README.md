# Capability Library

能力库是一个本地纯文件的能力管理层，让不同 AI 平台共用同一套 Skill 和 MCP。

```text
CAPABILITY.md（能力地图）
  → 按需读取 Skill
  → 按需 load MCP → use MCP
```

## 安装

```powershell
python scripts/deploy.py <目标目录>
```

部署后在目标目录得到可用的用户版实例。详细说明见 [`docs/初始化引导提示词.md`](docs/初始化引导提示词.md)。

## 架构

开发版和用户版的区别、设计决策，见 [`docs/能力库产品架构.md`](docs/能力库产品架构.md)。

## 开发

开发规则见 [`AGENTS.md`](AGENTS.md)。

## 目录

```
README.md
AGENTS.md
docs/
templates/        # 新用户模板
skills/           # 内置维护 Skill
tools/mcp/        # MCP 调用工具
scripts/          # 部署脚本
tests/
```
