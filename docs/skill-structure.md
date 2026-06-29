# 本技能仓库结构说明

## 设计原则

- **`SKILL.md`**：入口与编排；具体写法分散在 **`prompts/`**，由执行方在运行时用 **`Read`** 加载，避免单文件过长。
- **`tools/`**：可选脚本扩展，与编排解耦。Word/PPT 转可扫描文本时用 `docx_to_md.py` / `pptx_to_md.py`；查新优先 `cnipa_epub_search.py`（一步；需落盘或仅解析文件时用 `cnipa_epub_crawler.py` / `cnipa_epub_parse.py`，见 `prior_art_search.md`）。
- **`outputs/`**：整目录由 `.gitignore` 忽略；可随仓库提交的范例见 **`examples/`**。
- **`examples/`**：随仓库提交的虚构**原材料**示例（如 `knowledge/`）；流程产出在 `outputs/`。

## 目录一览

| 路径 | 说明 |
|------|------|
| `SKILL.md` | 触发条件、工具映射、步骤顺序、`prompts/` 索引 |
| `prompts/` | 分步模板（录入、扫描、专利点、查新、预览、成文、自检、迭代） |
| `prompts/template_reference_yh.md` | 默认 YH 15 项技术底稿章节细则、Images 2.0 图示提示词规范、`images/` 目录规则、附图说明与附图标记表；附图统一放在第 13 章，默认白底黑蓝线条，仅在流程状态必要时使用少量绿色/红色 |
| `prompts/disclosure_builder.md` | 默认 Step 7 成文入口，读取 `template_reference_yh.md` 并保留命名、查新、公式体例、Word 交付规则 |
| `tools/` | `figure_check.py`、`mermaid_render.py`、`md_to_docx.py`、`docx_to_md.py`、`pptx_to_md.py`、`cnipa_epub_search.py`、`cnipa_epub_crawler.py`、`cnipa_epub_parse.py` 等；mermaid 须 Node；国知局抓取须 Playwright，见 `tools/README.md` |
| `examples/example_batch_job_scheduler/` | 示例案件：仅 **`knowledge/`** 虚构原材料（专利点 / 交底书等由流程生成到 `outputs/`） |
| `docs/PRD.md` | 流程与约束摘要 |
| `docs/skill-structure.md` | 本仓库结构说明 |
| `docs/效果例-*.jpg` | README「运行效果」配图 |

## 环境变量 `CLAUDE_SKILL_DIR`

在 Claude Code、OpenClaw 等环境中，常由平台将 **`CLAUDE_SKILL_DIR`** 设为技能根目录，即包含 `SKILL.md` 的目录。在本地用 Cursor 打开本仓库时，该目录即仓库根；`${CLAUDE_SKILL_DIR}/prompts/...` 与 `./prompts/...` 等价。

## 用户定稿建议路径

推荐将每次案件的定稿放在：

`outputs/{案件标识}/`

可将 `examples/example_batch_job_scheduler/knowledge/` 的结构复制到自建案件目录（或 `outputs/{案件标识}/knowledge/`）后替换为真实原材料。

**交付留档**：凡写入用户产出目录的交底书定稿（**含首次 Step 7 与迭代**），主名均为 **`{案件名}_{YYYYMMDDHHmmss}.md`** 及同名 **`.docx`**（见 **`prompts/disclosure_builder.md` §7.3 第 5 点**），旧稿保留同目录。迭代时另在案件目录维护 **`交底书修订对话记录.md`**（**`tools/iteration_dialog_log.py`** 或手工）。流程见 **`prompts/iteration_context.md`**。

**YH 默认模板**：Step 7 默认采用 **YH 15 项技术底稿结构**，并由 LLM 规划图示、生成 **Images 2.0** 提示词、将图示保存到交付目录同级 **`images/`** 后集中放入第 13 章。附图统一放在第 13 章，默认白底黑蓝线条，仅在流程状态必要时使用少量绿色/红色。`images/` 与 `.md`、`.docx` 共同构成交付物；若 Images 2.0 不可调用，按 `disclosure_builder.md` 的规则输出图示规划和提示词，不伪造图片。mermaid 仍可作为降级线条图来源。

**查重与避让**：默认先检索查重，避开已有专利点，再基于差异化提出建议和反问；本行业内相近方案过密时，可借鉴其他行业类似专利的技术逻辑挖掘新的金点子。定稿 Word 前运行 **`tools/figure_check.py`**，校验第 13 章附图、其他章节图号引用、图注、附图说明、附图标记表和图片文件路径是否对应。
