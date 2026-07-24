---
name: patent-disclosure-skill
description: "中国专利：从项目文档挖掘专利点并生成可交付技术交底书（查新、脱敏成文、自检与迭代）；或将已有专利解读为通俗笔记与 Obsidian 知识图谱（叙事故事线、公开线索辅助）。| China patents: draft technical disclosures from project docs, or read existing patents into plain-language notes and an Obsidian knowledge graph."
version: "2.0.0"
user-invocable: true
argument-hint: "[可选：项目路径 / 技术主题 / 专利号或 PDF 路径]"
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 中国专利 · 交底书编写与通俗解读

本技能支持两种用法；分步指令在 **`prompts/`**，执行前须 **`Read`** 对应文件。

| 模式 | 何时用 | 主入口 |
|------|--------|--------|
| **A · 交底书编写** | 从项目材料挖专利点 → 查新 → 成稿 `.md`/`.docx` → 迭代 | 下文「交底书主流程」 |
| **B · 专利通俗解读** | 已有公开号 / PDF / 全文，原文抽象难读，要通俗叙事 + 图谱 | 下文「专利通俗解读」+ `patent_plain_reader.md` |

提供**专利号或专利全文/PDF**且意图为「读懂」时 → **优先模式 B**，**不**默认跑交底书 Step 1–8。

## 环境与约定

- **语言**：默认与用户语种一致；专利与法律术语用行业常用表述。
- **交底书图示（Step 7）**：**3.2**/**3.4** 用 fenced **mermaid**；见工具表与 **`tools/README.md`**。
- **解读 + Obsidian**：**强烈推荐**配置库（`PATENT_READER_OBSIDIAN_VAULT`），以完整体验索引、Canvas 知识图谱、术语网、关系图配色与公开线索旁注；无库可降级 `outputs/patent_reader/`。入库时**自动** bootstrap（CSS / Bases / 关系图），勿再引导用户手动装 CSS。用户侧 Obsidian 安装与可选社区插件见 **`docs/obsidian-setup-guide.md`**。

---

## 触发条件

- **交底书**：专利挖掘、专利点、技术交底书、交底书、查新、现有技术对比；`/patent-disclosure-skill`、`/交底书` 等。
- **通俗解读**：专利解读、读专利、看懂专利、反向专利、专利翻译成通俗；`/patent-read`、`/读专利`；或用户给出公开号 / 专利 PDF / 全文且目标为理解而非写交底书。
- **交底书迭代（意图识别）**：在**已有交底书**上补材料、改章节、纠错等——**无需**固定「迭代」一词，也**不必**先问是否迭代。`Read` `iteration_context.md`，再 `merger.md`（扩合并）或 `correction_handler.md`（纠错）；**另存** `{案件名}_{YYYYMMDDHHmmss}.md`/`.docx`，**不覆盖**旧稿（除非用户明确要求）。**禁止**迭代意图成立时默认回到 Step 3–4 重挖专利点。对话中已有交底书路径/附件时优先按迭代处理。

---

## 工具与数据来源

按任务选用；工具名以当前 Agent 环境为准。扫描含 **`.docx`/`.pptx`** 时，Step 2 阅读前须先 `docx_to_md.py` / `pptx_to_md.py`（`pip install -r requirements.txt`）。

### 常见任务与建议方式

| 任务 | 建议方式 |
|------|----------|
| 加载分步指令 | **`Read`** → `${CLAUDE_SKILL_DIR}/prompts/*.md` |
| 读代码、设计文档、PDF、图片 | 文件读取；大仓库先检索再精读 |
| Word / PPT → Markdown | `docx_to_md.py` / `pptx_to_md.py`（见上） |
| 联网查新（交底书 Step 5） | **`Read`** `prior_art_search.md`。优先 **`cnipa_epub_search.py`**：先归纳 2～8 语义块，**每次工具调用仅一词**，自行按 `pub_number` 合并 `EPUB_HITS_JSON`；需 `tools/requirements-cnipa.txt` + Playwright Chromium。`abstract` 必用。异常或无果再 **WebSearch** |
| 交底书定稿（**.md + .docx**） | **3.2/3.4** 用 mermaid；`mermaid_render.py` → PNG 并默认出 docx。见 **`tools/README.md`** |
| 交底书落盘 | 建议 `./outputs/{案件标识}/`；文件名 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5 点，含首次与迭代） |
| 迭代对话留档 | 案件目录追加 **`交底书修订对话记录.md`**（`iteration_dialog_log.py`） |
| **专利通俗解读** | **`Read`** `patent_plain_reader.md`。**先** `check_obsidian_env.py`（**强烈推荐**有库；未检测到则询问并用 `--set`；用户明确不要库才跳过）。仅公开号时用 **`fetch_patent_pdf.py`**（源表 `references/patent_pdf_sources.yaml`；**禁止**会话内现写下载脚本）→ `extract` → 叙事/权要可视化 → 公开线索由 **Agent 读 URL 写 summary** → `write_patent_obsidian_note`（入库自动 bootstrap；线索脚本抓取仅 `--fetch-clues-fallback`）。交付后可选社区插件引导；库内 ≥2 篇**须反问**关联，同意后 `link_patent_notes.py` |

---

## Prompt 文件映射

### 交底书编写

| 步骤 | 文件 | 用途 |
|------|------|------|
| Step 1 | `prompts/intake.md` | 边界与输入 |
| Step 2 | `prompts/project_scan.md` | 项目扫描；Office 须先转换 |
| Step 3–4 | `prompts/patent_points_analyzer.md` | 专利点融合与选定 |
| Step 5 | `prompts/prior_art_search.md` | 查新 |
| Step 6 | `prompts/disclosure_preview.md` | 摘要预览 |
| Step 7 | `prompts/disclosure_builder.md` + `template_reference.md` | 成文、脱敏、符号/公式体例、mermaid |
| Step 8 | `prompts/disclosure_self_check.md` | 内部自检（不入正文） |
| 迭代 | `iteration_context.md` / `merger.md` / `correction_handler.md` | 扩合并 / 纠错另存 |

### 专利通俗解读

| 步骤 | 文件 | 用途 |
|------|------|------|
| 门禁 | `check_obsidian_env.py`（见 `patent_plain_reader.md` 第 0 步） | 探测/写入库路径；强烈推荐有库 |
| 仅公开号取 PDF | `tools/patent_reader/fetch_patent_pdf.py` + `references/patent_pdf_sources.yaml` | 固化下载（第 1 步前）；**禁止**会话内现写脚本 |
| 主流程 | `prompts/patent_plain_reader.md` | extract / 附图 / 权树校对 / 线索 / 写笔记 / 入库（须先 Read） |
| 写笔记时 | `prompts/obsidian_ofm_companion.md` + `references/patent_obsidian_format.md` + `assets/patent_note_template.md` | Callout / 结构 / 模板 |
| 写笔记时（按需） | `references/ipc_application_hints.yaml` | IPC 应用场景坐标 |
| 自检 | `prompts/patent_reader_self_check.md` | 交付前内部自检（不入笔记） |
| 交付时（对话） | `prompts/obsidian_plugin_guide.md` | 可选社区插件引导（不入笔记） |
| 用户文档 | `docs/obsidian-setup-guide.md` | 装 Obsidian / 社区插件（给人看，勿当主链全文 Read） |
| 按需 | `tools/patent_reader/README.md` | 解读工具链说明 |

顺序摘要：门禁 →（仅公开号）`fetch_patent_pdf` → 主流程（extract / 附图 / 线索 / 入库）→ 写笔记时读 ofm/format/模板 → lint 后自检 → 已入库则交付引导；用户已给 PDF/全文则跳过下载；`obsidian-setup-guide` 与工具 README 仅按需查阅。

---

## 模式 A · 交底书主流程

1. **`Read`** `intake.md` → Step 1  
2. **`Read`** `project_scan.md` → Step 2  
3. **`Read`** `patent_points_analyzer.md` → Step 3–4  
4. **`Read`** `prior_art_search.md` → Step 5  
5. **`Read`** `disclosure_preview.md` → Step 6（可跳过）  
6. **`Read`** `disclosure_builder.md` + `template_reference.md` → Step 7（文件名 §7.3 第 5 点；对话附 §7.6 权利要求偏向点，**不入正文**）  
7. **`Read`** `disclosure_self_check.md` → Step 8 内部自检后交付  

**禁止**：交底书正文出现「自检清单」章节。

---

## 模式 B · 专利通俗解读

**启用**：读懂已有专利（见触发条件），且**非**交底书迭代。

**目标能力**（交付物应体现）：

- **取证解读**：权要树、术语、特征—说明书—附图对照  
- **叙述故事线**：一句话 + 问题/思路/怎么做/效果/差别等连贯叙事  
- **知识图谱**：`*_图谱.canvas`、术语双链、关系图配色；多篇可 `_专利关联.canvas`  
- **公开线索辅助**：≤3 条公开材料，L1–L4 旁注与 `clues/`（**推测语境，非权要/说明书证据**）

**步骤**：

1. **`Read`** `patent_plain_reader.md` → **先跑** `check_obsidian_env.py`（强烈推荐有库；无库则询问路径/`--set`，或确认仅 outputs）→ **仅公开号、无本地全文时**跑 **`fetch_patent_pdf.py`**（源表 `patent_pdf_sources.yaml`；失败可 `cnipa_epub_search` 核验元数据，**勿**现写下载脚本）→ `extract_patent_text`（及附图）→ 校对 `claim_tree` / 写 `claim_deltas` → 叙事与可视化 → Agent 读线索 URL 写 summary → 写笔记 → lint → `write_patent_obsidian_note`（有库时入库并**自动** bootstrap）  
2. **`Read`** `obsidian_ofm_companion.md` + `patent_obsidian_format.md` + 模板  
3. **`Read`** `patent_reader_self_check.md` → lint 通过后复核  
4. 已入库：对话末尾 **`Read`** `obsidian_plugin_guide.md`（仅可选社区插件；勿要求用户再装 CSS）  
5. 库内 ≥2 篇解读时**须反问**是否关联；同意后 `link_patent_notes.py`  

**与模式 A 互斥**：解读**不**跑交底书 Step 1–8。若用户要「先解读再写交底书」，先完成模式 B 交付，再询问是否进入 intake。

---

## 迭代模式（交底书 · 摘要）

按自然语言意图启用（见触发条件），**不**为「是否迭代」打断用户。

- **补材料 / 扩展 / §7.6 侧重点已声明**：`iteration_context.md` → `merger.md` → 另存时间戳稿 + 追加修订对话记录 + 输出合并摘要  
- **纠错 / 与事实不符**：`iteration_context.md` → `correction_handler.md` → 另存 + 记录 + 纠正摘要；定稿仍附 §7.6 引导  

新稿定稿路径上仍内部执行 `disclosure_self_check.md`。

---

## Agent 自用工作流检查清单

```
□ 已区分模式 A（交底书）/ B（解读）/ 交底书迭代，未混跑
□ 已按步骤 Read 对应 prompts；Step 2 若含 Office，已 docx_to_md / pptx_to_md 并读产出 `.md`
□ 「在已有交底书上改」类意图：已 Read iteration_context 并走 merger/correction；交付为新时间戳文件，未无故覆盖旧稿；已追加交底书修订对话记录.md 并输出留档摘要
□ 查新：优先 cnipa_epub_search（分次一词并合并 EPUB_HITS_JSON）；abstract 必用；异常再 WebSearch；1.1 与区别论述已写
□ 除用户跳过外已做摘要预览；脱敏/mermaid/§7.7/3.4.1 与 .md+.docx 时间戳文件名符合要求；正文无技能仓库类脚注
□ 定稿对话含 §7.6 权利要求偏向点（不入正文、不捏造）；自检仅后台，正文无自检清单
□ 【模式 B】已 check_obsidian_env；仅公开号已用 fetch_patent_pdf（未现写下载脚本）；强烈推荐有库（无库已确认降级 outputs）；叙事/线索/图谱要点已覆盖；入库自动 bootstrap，未误导用户手装 CSS；≥2 篇已反问关联并按需 link_patent_notes
```
