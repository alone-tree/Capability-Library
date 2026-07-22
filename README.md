# Capability Library 开发版

本仓库是能力库开发版，负责通用运行程序、用户版 README、部署工具和首次安装模板，不保存用户真实能力清单。

用户版是独立目录。平台只接入其中的 `capability-entry`，具体 Skill 按需读取，MCP 通过 `load_mcp.py` 和 `use_tool.py` 调用。

## 文件边界

开发版拥有 `user-version/README.md`、`LICENSE` 和 `tools/` 中的通用程序。部署器按显式映射逐文件管理这些内容。

用户拥有 `capability-entry/`、`skills/`、`mcps/registry.json`、`CAPABILITY.md` 和所有未登记文件。模板只在首次安装且目标文件不存在时创建，后续更新不覆盖。

## 安装与更新

必须从开发版根目录运行。先预览变化：

```powershell
python scripts/deploy.py <用户版目录> --check
```

确认范围后执行：

```powershell
python scripts/deploy.py <用户版目录>
```

更新器按目标文件比较 SHA-256，只完整替换发生变化的受管文件。旧受管文件只有在内容仍与上次部署一致时才会删除；用户修改过的旧文件会保留并产生警告。更新器不执行局部文本补丁，也不扫描或同步整个目录。

用户版的 MCP 使用说明已经合并进根 README，旧 `docs/` 文档不再部署。已有用户需要自行把 `capability-entry/SKILL.md` 中的旧引用改为用户版 README，部署器不会修改用户入口。

## 开发版目录

```text
user-version/               用户版 README 源文件
templates/                  首次安装模板，仅在用户文件缺失时创建
tools/                      MCP 通用运行程序
scripts/deploy.py           文件级安全更新器
scripts/package_release.py  新用户安装包构建脚本
tests/                      自动化测试
```

`python scripts/package_release.py` 使用同一份部署清单生成干净的新用户安装包。安装包只用于首次安装；已有用户必须使用 `deploy.py` 更新，不能用 ZIP 覆盖。

开发规则见 [`AGENTS.md`](AGENTS.md)。提交前运行：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```
