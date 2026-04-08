# 本技能仓库结构说明

## 设计原则

- **`SKILL.md`**：入口与编排；具体写法分散在 **`prompts/`**，由执行方在运行时用 **`Read`** 加载，避免单文件过长。
- **`tools/`**：可选脚本扩展，与编排解耦。Word/PPT 转可扫描文本时用本仓库 `docx_to_md.py` / `pptx_to_md.py`（见 `SKILL.md`）。
- **`outputs/`**：整目录由 `.gitignore` 忽略；可随仓库提交的范例见 **`examples/`**。
- **`examples/`**：随仓库提交的虚构**原材料**示例（如 `knowledge/`）；流程产出在 `outputs/`。

## 目录一览

| 路径 | 说明 |
|------|------|
| `SKILL.md` | 触发条件、工具映射、步骤顺序、`prompts/` 索引 |
| `prompts/` | 分步模板（录入、扫描、专利点、查新、预览、成文、自检、迭代） |
| `prompts/template_reference.md` | 交底书章节细则与 mermaid 图示范例 |
| `tools/` | `mermaid_render.py`（mermaid → PNG）、`md_to_docx.py`、`docx_to_md.py`、`pptx_to_md.py` 等；mermaid 须 Node，见 `tools/README.md` |
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
