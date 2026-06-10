# Skill 清单

> 本文件由 `tools/registry/refresh_manifest_md.py` 根据 `skills/manifest.json` 生成。

## 能力库说明

- ID：`skill_7b4f0a9c2d1e`
- 路径：`skills/capability-library-guide/SKILL.md`
- 启用：是
- 描述：说明能力库的定位、目录结构、使用流程，以及主 AI 如何通过能力库发现 Skill 和 MCP。
- 备注：主 AI 不理解能力库机制，或需要确认如何使用能力库时优先阅读。

## 入库流程

- ID：`skill_3d9a61f8c0b2`
- 路径：`skills/intake-flow/SKILL.md`
- 启用：是
- 描述：说明如何把新的 Skill 或 MCP 放入能力库，包括文件放置、注册工具调用、清单刷新和注意事项。
- 备注：用户要求“入库”或主 AI 准备保存新能力时优先阅读。

## 研究报告写作

- ID：`skill_2ac9c1408f14`
- 路径：`skills/research-report-writing/SKILL.md`
- 启用：是
- 描述：行业研究、公司研究的调查、研究。撰写公司深度研究报告、行业分析报告、投资研究报告时触发。关键词：写报告、分析公司、深度研究、估值分析、行业研究、投资报告、调研报告。
- 备注：目标读者：投资委员会成员。用投资人语言回答商业模式、成长空间、竞争壁垒、估值判断、风险五个核心问题。

## 网页搜索工作流

- ID：`skill_6259eb92ba83`
- 路径：`skills/web-search-workflow/SKILL.md`
- 启用：是
- 描述：通用网页搜索工作流。当需要搜索网页、查找文章、获取最新新闻、研究话题、提取URL内容、爬取网站时触发。关键词：搜索、找一下、查一下、研究一下、最新消息、读取网页、爬取。
- 备注：优先使用Tavily MCP，内置WebSearch为备用。支持多语言搜索策略。
