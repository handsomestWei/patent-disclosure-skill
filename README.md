<div align="center">

# 中国专利.skill

> 从项目文档到**可交付的技术交底书**：专利点挖掘、**查新优先国知局公布公告站**、脱敏成文与自检闭环。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-mermaid%2Fmmdc-339933.svg)](https://nodejs.org/)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)

<br>

有设计文档和代码，但**专利点还没梳**？<br>
交底书要**系统框图、流程图**，还要**代理人能直接改的 Word**？<br>
定稿之后还要**多轮补材料、纠错**，并希望**文件修改追溯**？<br>
国知局公布站检索，期望 **次次爬成功、精准检索**？

**本 Skill 按 AgentSkills 约定编排全流程，`SKILL.md` + `prompts/` 分步可读可迭代。**

[功能特性](#功能特性) · [安装](#安装) · [使用](#使用) · [项目结构](#项目结构) · [示例](#示例) · [运行效果](#运行效果) · [参考文档](#参考文档) · [详细安装说明](INSTALL.md) · [技能入口](SKILL.md)

</div>

---

## 功能特性

| 能力 | 说明 |
|------|------|
| 项目扫描 | 按优先级读文档 / 代码；`.docx` / `.pptx` 先转 Markdown 再扫（见 `prompts/project_scan.md`） |
| 专利点 | 候选点讨论与融合（`patent_points_analyzer.md`） |
| 查新 | **优先** [国家知识产权局 · 中国专利公布公告](http://epub.cnipa.gov.cn/)：使用 `tools/cnipa_epub_search.py`精准爬取；异常或无果时降级 **WebSearch**（如 Google 学术 / Patents）。著录与外链写入第一章（`prior_art_search.md`） |
| 交底书成稿 | 脱敏模版 + **mermaid** 系统框图与流程图；`mermaid_render.py` → PNG，默认再出 **.docx** |
| 交付命名 | 凡落盘交付：**`{案件名}_{YYYYMMDDHHmmss}.md`** 与同名 **.docx**（`disclosure_builder.md` §7.3） |
| 自检 | 逻辑闭环、公式与参数一致（`disclosure_self_check.md`，不写入正文） |
| 迭代 | **合并** / **纠正** 另存新文件；**`交底书修订对话记录.md`** 逐条追加（`iteration_context.md`、`iteration_dialog_log.py`） |

**Office 抽取**：`.docx` / `.pptx` 先用本仓库 `docx_to_md.py` / `pptx_to_md.py` 转为 Markdown 再扫描（见 `SKILL.md`）。

**Python 依赖（分文件）**：
- **基础（Office / 交底书转换）**：根目录 [`requirements.txt`](requirements.txt) — `pip install -r requirements.txt`
- **查新（国知局公布公告站，可选）**：[`tools/requirements-cnipa.txt`](tools/requirements-cnipa.txt) — `pip install -r tools/requirements-cnipa.txt`，再执行 `python -m playwright install chromium`  
  不装亦可：Step 5 将按 `prior_art_search.md` 仅用 **WebSearch** 降级。详见 [INSTALL.md](INSTALL.md)、[tools/README.md](tools/README.md)。

---

## 安装

### Claude Code

> 请在 **git 仓库根目录** 或全局 skills 路径下放置本目录，使 `SKILL.md` 位于技能文件夹根级（与 [INSTALL.md](INSTALL.md) 一致）。

```bash
# 示例：安装到当前项目的 skills 目录
mkdir -p .claude/skills
git clone <本仓库 URL> .claude/skills/patent-disclosure-skill
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

图示定稿另需 **Node.js**；在 `tools/` 下执行 `npm install` 或使用 `npx mmdc`（详见 [tools/README.md](tools/README.md)）。

---

## 使用

在 Agent 中用自然语言描述需求即可，例如：

- 专利挖掘、专利点、**技术交底书**、查新、现有技术对比  
- 斜杠指令（视宿主配置）：如 `/patent-disclosure-skill`、`/交底书`

建议同时说明 **项目路径** 或 **技术主题**（与 `SKILL.md` 中 `argument-hint` 一致）。  
**查新（Step 5）** 会优先通过 [中国专利公布公告](http://epub.cnipa.gov.cn/) 检索中国专利公开信息，再按需补充其他来源；流程见 `prompts/prior_art_search.md`。  
在**已有交底书文件**上补充材料或纠错时，无需说「迭代」——技能会按 `merger.md` / `correction_handler.md` 处理；细则见 [SKILL.md](SKILL.md)。

---

## 项目结构

本仓库遵循 [AgentSkills](https://agentskills.io)，根目录即一个 skill：

```
patent-disclosure-skill/
├── SKILL.md                    # 入口：触发条件、工具表、步骤与 prompts 引用
├── prompts/                    # 分步模板（Agent Read 后遵循）
│   ├── intake.md
│   ├── project_scan.md
│   ├── patent_points_analyzer.md
│   ├── prior_art_search.md
│   ├── disclosure_preview.md
│   ├── disclosure_builder.md
│   ├── disclosure_self_check.md
│   ├── iteration_context.md
│   ├── merger.md
│   ├── correction_handler.md
│   └── template_reference.md
├── tools/                      # mermaid_render、md_to_docx、docx_to_md、pptx_to_md；国知局 cnipa_epub_*（查新）；iteration_dialog_log 等
├── docs/                       # PRD、仓库结构说明、运行效果截图（效果例-*.jpg）
├── examples/                   # 原材料示例（如 example_batch_job_scheduler/knowledge/）
├── outputs/                    # 用户产出，整目录 .gitignore
├── requirements.txt
├── LICENSE
├── INSTALL.md
└── .gitignore
```

---

## 示例

虚构扫描原材料见 [examples/README.md](examples/README.md)（如 `examples/example_batch_job_scheduler/knowledge/`）。  
专利点、查新笔记、交底书等**完整产物**由流程生成到本地 **`outputs/{案件标识}/`**。

---

## 运行效果

**初版生成**（首次落盘交付）

![初版生成：outputs 目录下的时间戳交底书、mermaid 图目录等](docs/效果例-初版生成.jpg)

**迭代更新**（合并/纠正后再交付，多版本并存 + 对话记录）

![迭代更新：新时间戳文件与交底书修订对话记录](docs/效果例-迭代更新.jpg)

---

## 参考文档

- [技能入口与 Agent 流程](SKILL.md)（触发条件、`prompts/` 映射、工具表）
- [详细安装说明](INSTALL.md)（Claude Code / Cursor 路径）
- [图示与转换脚本](tools/README.md)（mermaid / mmdc、Word 导出、国知局 epub 查新工具）
- [示例案件与原材料说明](examples/README.md)
- [产品流程与目录约定](docs/PRD.md)
- [工程结构说明](docs/skill-structure.md)
- [交底书模版细则](prompts/template_reference.md)

---

<div align="center">

MIT License © [handsomestWei](https://github.com/handsomestWei/)

</div>
