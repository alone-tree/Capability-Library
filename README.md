# Capability Library

能力库是一个本地纯文件的能力管理层，让不同 AI 平台共享低频 Skill 和按需 MCP。

平台只接入 `capability-entry`。用户能力清单、Skill 和 MCP 注册表留在用户版；开发版负责通用运行程序、一般性文档和首次安装模板。

## 安装与更新

首次安装和后续更新使用同一个命令：

```powershell
python scripts/deploy.py <用户版目录>
```

先预览变化、不写文件：

```powershell
python scripts/deploy.py <用户版目录> --check
```

更新器按文件比较 SHA-256，只完整替换发生变化的开发版受管文件。它不会覆盖：

- `capability-entry/`
- `skills/`
- `mcps/registry.json`
- `CAPABILITY.md`
- 其他未登记文件

详细边界见 [`docs/能力库产品架构.md`](docs/能力库产品架构.md)，MCP 调用方式见 [`docs/MCP使用指南.md`](docs/MCP使用指南.md)。

## 开发版目录

```text
docs/                       通用说明文档
templates/                  首次安装模板，仅在用户文件缺失时创建
tools/                      MCP 通用运行程序
scripts/deploy.py           文件级安全更新器
scripts/package_release.py  开发版发布包脚本
tests/                      自动化测试
```

开发规则见 [`AGENTS.md`](AGENTS.md)。
