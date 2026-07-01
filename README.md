<div align="center">

# 中国专利.skill

> 从项目文档到**可交付的技术交底书**：专利点挖掘、**查新优先国知局公布公告站**、脱敏成文与自检闭环。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-mermaid%2Fmmdc-339933.svg)](https://nodejs.org/)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)

**从项目文档到可交付技术交底书：专利点挖掘、查新避让、YH 15 项成稿、图示、Word 输出与迭代留档。**

[功能特性](#功能特性) · [安装](#安装) · [使用](#使用) · [项目结构](#项目结构) · [参考文档](#参考文档) · [详细安装说明](INSTALL.md) · [技能入口](SKILL.md)

</div>

---

## 功能特性

- **项目扫描**：`.docx` / `.pptx` 先转 Markdown，再按 `project_scan.md` 扫描材料。
- **专利点与查新**：按 `patent_points_analyzer.md` 与 `prior_art_search.md` 做候选点、国知局查新、避让、建议和反问。
- **YH 15 项成稿**：按 `disclosure_builder.md` 与 `template_reference_yh.md` 生成 Markdown、图示规划和 Word。
- **自检与迭代**：`disclosure_self_check.md` 作为唯一质量门；已有稿补充/纠错走 `iteration_context.md`、`merger.md`、`correction_handler.md`。

**Office 抽取**：`.docx` / `.pptx` 先用本仓库 `docx_to_md.py` / `pptx_to_md.py` 转为 Markdown 再扫描（见 `SKILL.md`）。

**Python 依赖（分文件）**：
- **基础（Office / 交底书转换）**：根目录 [`requirements.txt`](requirements.txt) — `pip install -r requirements.txt`
- **查新（国知局公布公告站，可选）**：[`tools/requirements-cnipa.txt`](tools/requirements-cnipa.txt) — `pip install -r tools/requirements-cnipa.txt`，再执行 `python -m playwright install chromium`  
  不装亦可：C 阶段将按 `prior_art_search.md` 仅用 **WebSearch** 降级。详见 [INSTALL.md](INSTALL.md)、[tools/README.md](tools/README.md)。

---

## 安装

### Claude Code

> 请在 **git 仓库根目录** 或全局 skills 路径下放置本目录，使 `SKILL.md` 位于技能文件夹根级（与 [INSTALL.md](INSTALL.md) 一致）。

```bash
# 示例：安装到当前项目的 skills 目录
mkdir -p .claude/skills
git clone <本仓库 URL> .claude/skills/yh-patent-disclosure-skill
```

### Cursor

将本仓库完整内容放到 Cursor 约定的 skills 路径（见 [INSTALL.md](INSTALL.md) 表格），重启后在 **Settings → Rules** 中确认技能已被发现。

### 依赖

```bash
# 基础（Office 转换、交底书相关 Python 包）
pip install -r requirements.txt
```

```bash
# 可选：国知局查新（epub.cnipa.gov.cn）
pip install -r tools/requirements-cnipa.txt
python -m playwright install chromium
```

Images 2.0 是否可调用取决于实际 Agent 环境；若使用 mermaid 降级图示，另需 **Node.js**，在 `tools/` 下执行 `npm install` 或使用 `npx mmdc`（详见 [tools/README.md](tools/README.md)）。

---

## 使用

在 Agent 中用自然语言描述需求即可，例如：

- 专利挖掘、专利点、**技术交底书**、查新、现有技术对比  
- 斜杠指令（视宿主配置）：如 `/yh-patent-disclosure-skill`、`/patent-disclosure-skill`、`/交底书`

建议同时说明 **项目路径** 或 **技术主题**。  
**查新** 会优先通过 [中国专利公布公告](http://epub.cnipa.gov.cn/) 检索中国专利公开信息，再按需补充其他来源；流程见 `prompts/prior_art_search.md`。  
**成稿** 默认使用 YH 15 项技术底稿模板（`disclosure_builder.md + template_reference_yh.md`），图示由 LLM 规划并按 Images 2.0 规范生成到 `images/`，附图统一放在第 13 章；默认白底黑蓝线条，仅在流程状态必要时使用少量绿色/红色。  
在**已有交底书文件**上补充材料或纠错时，无需说「迭代」——技能会按 `merger.md` / `correction_handler.md` 处理；细则见 [SKILL.md](SKILL.md)。

---

## 项目结构

本仓库遵循 [AgentSkills](https://agentskills.io)，根目录即一个 skill：

```
YH-patent-disclosure-skill/
├── SKILL.md                    # 入口：触发条件、阶段路由、执行要点
├── prompts/                    # 分步指令（Agent Read 后遵循）
│   ├── intake.md
│   ├── project_scan.md
│   ├── patent_points_analyzer.md
│   ├── patent_avoidance_methods.md
│   ├── prior_art_search.md
│   ├── disclosure_builder.md
│   ├── template_reference_yh.md
│   ├── disclosure_self_check.md
│   ├── iteration_context.md
│   ├── merger.md
│   └── correction_handler.md
├── tools/                      # figure_check、mermaid_render、md_to_docx、docx_to_md、pptx_to_md；国知局 cnipa_epub_*；iteration_dialog_log 等
├── tests/                      # 工具行为测试
├── requirements.txt
├── LICENSE
├── INSTALL.md
└── .gitignore
```

---

## 参考文档

- [技能入口与 Agent 流程](SKILL.md)（触发条件、阶段路由、执行要点）
- [详细安装说明](INSTALL.md)（Claude Code / Cursor 路径）
- [工具与脚本说明](tools/README.md)（Office 转换、国知局查新、图示/公式渲染、附图校验、迭代留档）
- [YH 默认交底书模版细则](prompts/template_reference_yh.md)

<div align="center">

MIT License © [handsomestWei](https://github.com/handsomestWei/)

</div>
