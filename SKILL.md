---
name: patent-disclosure-skill
description: "中国专利技能：专利点挖掘与交底书（发明/实用/外观）编写，通俗解读专利，嗅探政策动向，辅助审查答复。| China patents skill: mine patent points and draft disclosures (invention / utility model / design), plain-language reading, policy sniffing, assisted office-action response."
version: "3.6.0"
user-invocable: true
argument-hint: "[可选：项目路径 / 专利号或 PDF / 政策动向嗅探或技能进化 / 审查答复或案例入库]"
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 中国专利技能 · 交底编写 · 通俗解读 · 政策/审查动向嗅探 · 审查答复

本技能**单包模块化**：分步指令在 **`prompts/`**，执行前须 **`Read`** 对应文件。`SKILL.md` 只做路由。

| 模式 | 何时用 | 主入口 |
|------|--------|--------|
| **A · 交底书编写** | 挖专利点 → 查新 → 成稿 → 迭代 | `prompts/disclosure/`（类型子目录见下） |
| **B · 专利通俗解读** | 公开号 / PDF / 全文 → 通俗笔记 + 图谱 | `prompts/reader/patent_plain_reader.md` |
| **C · 技能进化旁路** | 政策/审查动向嗅探 → 带时间戳清单 → **人审后**才改技能 | `prompts/evolution/`（须显式触发） |
| **D · 审查答复辅助** | 案例脱敏入库；通知书 → 标签+向量检索 → 答复草稿 | `prompts/oa/`（须显式触发；须人审） |

提供**专利号或专利全文/PDF**且意图为「读懂」时 → **优先模式 B**，**不**默认跑交底书 Step 1–8。  
**禁止**因写交底/读专利自动进入模式 C/D。

## 目录约定（薄路由）

```
prompts/disclosure/          # 交底公共流程
  invention/                 # 发明：挖点 / builder / template
  utility_model/             # 实用新型：挖点 / builder / template（单独 md，勿套用发明 mermaid 主线）
  design/                    # 外观设计：挖点 / builder / template（单独 md）
prompts/reader/              # 通俗解读 + type_hooks
prompts/shared/              # 写读共用：Structure / Appearance 填表 + figure_plan + 外观/实用辅助线稿
prompts/evolution/           # 模式 C：政策/审查动向嗅探 · 进化清单（旁路，须显式触发）
prompts/oa/                  # 模式 D：审查答复 / 案例入库（旁路，须显式触发）
references/schemas/          # structure / appearance / figure_plan / formula_plan / lineart / evolution / oa_case
references/formulas/         # 发明公式推荐范式（paradigms.yaml，可外挂扩展）
tools/crawl/                 # 国知局等爬取
tools/shared/                # docx/mermaid/专利类型/可选 STEP / 可选辅助线稿门禁；browser.py + vendor/mermaid.min.js
tools/patent_reader/         # 解读工具：shared/ | extract/ | analyze/ | vault/
tools/oa/                    # 模式 D：config / embed / sqlite-vec / ingest / search
outputs/evolution/           # 模式 C 清单默认落盘（gitignore）
docs/evolution/              # 仅用户确认「沉淀」后可复制提交
docs/oa/                     # 模式 D：embedding 配置模板种子（运行时在系统文档目录）
```

## 环境与约定

- **脚本判读（尤其 Windows）**：stderr 有字 **不等于** 失败。以 **退出码 0** 和机读前缀为准：`EPUB_HITS_JSON:` / `EPUB_MERGE:`、`PROBE:` / `BROWSER:`、`MERMAID:` / `DOCX:` / `MATH:` / `omml_text_fallback=`。PowerShell 可能把 stderr 标成 `NativeCommandError` 或乱码；**禁止**因此重跑安装、或把查新降级 WebSearch。勿用 `2>&1` 把 JSON 混进错误流。
- **专利类型**：未显式指定时交底**默认发明**；材料更偏实用/外观时在汇总或预览阶段**反问**（见 `disclosure/intake.md`）。
- **交底书图示**：
  - **发明**：3.2 / 3.4 用 fenced **mermaid** → `tools/shared/mermaid_render.py`（Playwright + 内置 mermaid.js，见 `tools/shared/browser.py`）。
  - **实用新型**：先 `figure_plan.yaml` 排序入文图（优先线稿/CAD；总装+局部写 `relates_to`）+ 部件/关系表（见 `utility_model/disclosure_builder.md`）。
  - **外观**：先 `figure_plan.yaml` 选视图（实拍/线稿均可；多视写 `relates_to`；场景图默认低优先）（见 `design/disclosure_builder.md`）。
- **STEP / CAD（可选，默认关）**：Step 2 用 `cad_scan.py` 分类；遇 `.step`/`.stp` **先反问**再装 `requirements-step.txt` 并 `step_to_views.py --enable-step-parse`；仅有原生 CAD 则回复末尾提示导出 STEP。见 `project_scan.md`「CAD / STEP」。
- **外观辅助线稿（可选，默认关）**：有产品图时可反问；用户 **是** 后按 `shared/design_lineart_assist.md`（先 YAML 描述 + 多视联读，再**参考图**出线稿）；无图禁止；非申报终稿；**不**画部件序号。
- **实用结构辅助线稿（可选，默认关）**：有结构图且缺干净线稿时可反问；用户 **是** 后按 `shared/structure_lineart_assist.md`（对齐 `structure_schema.parts`；轮廓与序号分层，推荐 overlay；禁止自创件号）；无图禁止；非申报终稿。**勿**与外观 `design_lineart_*` 混用。
- **解读 + Obsidian**：强烈推荐配置库；见 **`docs/obsidian-setup-guide.md`**。
- **技能进化 / 动向嗅探（须显式触发）**：用户点名后走模式 C（政策/审查动向嗅探 → 清单）；清单含 **观点↔信源 URL 表**；未人审确认前**不**改技能正文。
- **审查答复（须显式触发）**：用户点名后走模式 D；向量模型**可选**（可 `skip-vector`，中途再 enable + 重建）；推荐智谱 `embedding-3`；标签检索始终可用，向量超时则回退。

---

## 触发条件

- **交底书**：专利挖掘、交底书、查新、实用新型、外观设计等；`/patent-disclosure-skill`、`/交底书`。
- **通俗解读**：读专利、公开号 / PDF 且目标为理解；`/patent-read`、`/读专利`。
- **交底书迭代**：已有交底上补材料/纠错 → `disclosure/iteration_context.md` → `merger` / `correction_handler`；另存时间戳稿。
- **完整申报包深化**：用户要求从候选评分切换为可交代理师复核的完整包、同步深化项目方案与申请文件、制作领导/事务所可直接转发的目录，或要求蒸馏既有交付经验 → `disclosure/iteration_context.md` → **`references/filing_ready_iteration_delivery.md`** → `merger.md` → `disclosure_self_check.md §8.6`。组合创造性风险须披露，但不得自动代替文件申报判断。
- **技能进化旁路**：技能进化、政策/审查动向嗅探、政策雷达、审查政策更新、自进化、`/patent-evolve`、`/技能进化` → **仅此时**进入模式 C。
- **审查答复 / 案例入库**：审查意见、意见陈述、OA、补正通知书、案例入库、`/oa`、`/审查答复` → **仅此时**进入模式 D。

---

## 工具与数据来源

| 任务 | 建议方式 |
|------|----------|
| 加载分步指令 | **`Read`** → `prompts/disclosure|reader|shared|evolution/…`（完整子路径） |
| Word / PPT → Markdown | `tools/shared/docx_to_md.py` / `pptx_to_md.py` |
| CAD 扫描 / STEP→多视图（可选，默认关） | `tools/shared/cad_scan.py`；用户确认后 `step_to_views.py --enable-step-parse` |
| 外观辅助线稿（可选，默认关） | `prompts/shared/design_lineart_assist.md`；门禁 `design_lineart_gate.py`（须参考图，禁止纯文生图） |
| 实用结构辅助线稿（可选，默认关） | `prompts/shared/structure_lineart_assist.md`；门禁 `structure_lineart_gate.py`（须参考图 + Structure；序号优先 overlay） |
| 联网查新 | **`Read`** `disclosure/prior_art_search.md`。优先 **`tools/crawl/cnipa_epub_search.py --type …`**（与 intake 类型一致）；`abstract` 必用；异常再 WebSearch。类型映射见 `references/patent_type_search.yaml` |
| 交底定稿 | 发明：`tools/shared/mermaid_render.py` → md+docx；实用/外观：按各类型 builder |
| 专利通俗解读 | **`Read`** `reader/patent_plain_reader.md`；实用/外观另 Read `reader/type_hooks.md` + `shared/fill_*` |
| 解读取 PDF / 入库 | `tools/patent_reader/extract/fetch_patent_pdf.py`；`…/vault/write_patent_obsidian_note.py` 等（见 `tools/patent_reader/README.md`） |
| 政策/审查动向嗅探 | **`Read`** `evolution/intake.md` → `research.md`（WebSearch + 官网抓取）→ `emit_backlog.md`；确认后 `apply_after_confirm.md` |
| 审查答复 / 案例库 | **`Read`** `oa/intake.md`；PDF 用 `oa/pdf_text.py` / `search_cases.py --pdf` / `ingest_case.py --pdf`；入库 `oa/ingest_case.md`；答复 `oa/respond_office_action.md`；配置 `oa/config.py` |

---

## Prompt 文件映射

### 交底书（公共 + 类型特化）

| 步骤 | 文件 | 用途 |
|------|------|------|
| Step 1 | `prompts/disclosure/intake.md` | 边界；**默认发明**；可反问实用/外观 |
| Step 2 | `prompts/disclosure/project_scan.md` | 项目扫描（Office + **可选 CAD/STEP**；三类示例加扫） |
| Step 3–4 | **发明** `disclosure/invention/patent_points_analyzer.md`；**实用** `utility_model/patent_points.md`；**外观** `design/patent_points.md` | 挖点（**分文件，勿混用**） |
| 填表（实用/外观） | `prompts/shared/fill_structure_schema.md` / `fill_appearance_schema.md` | 图→schema + **`figure_plan.yaml`** |
| 外观辅助线稿 | `prompts/shared/design_lineart_assist.md` | 可选；默认关；描述→参考图线稿（无件号） |
| 实用结构辅助线稿 | `prompts/shared/structure_lineart_assist.md` | 可选；默认关；轮廓→按 parts 叠序号 |
| Step 5 | `prompts/disclosure/prior_art_search.md` | 查新（`--type`） |
| Step 6 | `prompts/disclosure/disclosure_preview.md` | 摘要预览（按类型裁剪） |
| Step 7 | 对应类型目录 `disclosure_builder.md` + `template_reference.md` | 成文（**分文件**；发明含公式时先 `formula_plan.yaml`） |
| Step 8 | `prompts/disclosure/disclosure_self_check.md` | 内部自检（含 §8.4 / §8.5） |
| 迭代 | `disclosure/iteration_context.md` / `merger.md` / `correction_handler.md` | 另存 |
| 完整申报包深化 | `references/filing_ready_iteration_delivery.md` | 双门模型、五项申报硬门、证据追溯、五类差异、`MERGE_TAG`、文件生产与收件人目录 |

### 专利通俗解读

| 步骤 | 文件 |
|------|------|
| 主流程 | `prompts/reader/patent_plain_reader.md` |
| 类型挂钩 | `prompts/reader/type_hooks.md` |
| 写笔记 | `reader/obsidian_ofm_companion.md` + `references/patent_obsidian_format.md` |
| 自检 / 插件引导 | `reader/patent_reader_self_check.md` / `obsidian_plugin_guide.md` |
| 取 PDF | `tools/patent_reader/extract/fetch_patent_pdf.py` |
| 入库 | `tools/patent_reader/vault/write_patent_obsidian_note.py` |

### 技能进化旁路 · 政策/审查动向嗅探（模式 C）

| 步骤 | 文件 |
|------|------|
| 总则 | `prompts/evolution/guardrails.md` |
| 录入 | `prompts/evolution/intake.md` |
| 检索/抓取 | `prompts/evolution/research.md` |
| 出清单 | `prompts/evolution/emit_backlog.md` |
| 确认后改技能 | `prompts/evolution/apply_after_confirm.md`（须人审） |
| 交底交付低频提示 | `prompts/evolution/soft_nudge.md`（可选一句，不入正文） |
| 合同 | `references/schemas/evolution_backlog.schema.yaml` |

### 审查答复（模式 D）

| 步骤 | 文件 |
|------|------|
| 总则 | `prompts/oa/guardrails.md` |
| 录入 | `prompts/oa/intake.md` |
| 向量对话配置 | `prompts/oa/configure_embedding.md`（问答 → set/secrets → selftest） |
| 脱敏入库 | `prompts/oa/ingest_case.md` + `tools/oa/ingest_case.py`（支持 `--pdf`） |
| 答复草稿 | `prompts/oa/respond_office_action.md` + `tools/oa/search_cases.py --pdf` |
| PDF 抽取 | `tools/oa/pdf_text.py`（pymupdf；优先路径，禁止让用户手贴） |
| 案例模板 | `prompts/oa/case_note_template.md` |
| 合同 / 配置 | `references/schemas/oa_case.schema.yaml`；运行时 `{Documents}/…/oa/embedding.config.yaml`（仓库模板 `docs/oa/`） |

---

## 模式 A · 交底书主流程

1. **`Read`** `disclosure/intake.md` → Step 1（默认发明）  
2. **`Read`** `disclosure/project_scan.md` → Step 2  
3. 按类型 **`Read`** `invention|utility_model|design` 挖点；实用/外观先/并行 **`Read`** `shared/fill_*`  
4. **`Read`** `disclosure/prior_art_search.md` → Step 5（`--type` 对齐）  
5. **`Read`** `disclosure/disclosure_preview.md` → Step 6（可跳过；此处可类型反问）  
6. **`Read`** **同类型** `disclosure_builder` + `template_reference` → Step 7（**禁止**用发明 builder 写实用/外观）  
7. **`Read`** `disclosure/disclosure_self_check.md` → Step 8  

**禁止**：交底书正文出现「自检清单」章节。

---

## 模式 B · 专利通俗解读

1. **`Read`** `reader/patent_plain_reader.md`（门禁 / fetch / extract / 线索 / 入库）  
2. 若实用新型或外观：**`Read`** `reader/type_hooks.md` + 对应 `shared/fill_*`  
3. **`Read`** ofm + 自检；入库后可选插件引导；≥2 篇反问关联  

**与模式 A 互斥**：解读不跑交底 Step 1–8。

---

## 模式 C · 技能进化旁路 · 政策/审查动向嗅探

1. **`Read`** `evolution/guardrails.md` → `intake.md`  
2. **`Read`** `evolution/research.md`：WebSearch + 打开国知局等官网正文；默认近 12 个月  
3. **`Read`** `evolution/emit_backlog.md`：写入 `outputs/evolution/EVOL-YYYYMMDD-HHMM.md`  
   - **主表必为「观点 ↔ 信源 URL」**（一行一观点，附准确 `https://` 链接）  
   - 证据 C（自媒体等）不得单独支撑「改技能」建议  
4. 展示人审闸门；**等待**「全部采纳 / 采纳 E… / 全部搁置 / 沉淀到 docs/evolution/」  
5. 仅确认采纳后 → **`Read`** `apply_after_confirm.md` → 最小改动 prompts，并写 `.status.md`  

交底定稿交付后的**可选一句**提示见 `evolution/soft_nudge.md`（低频；**不**等于自动进入本模式）。

**与 A/B 互斥**：进化旁路不写交底书、不做专利解读成稿。

---

## 模式 D · 审查答复辅助

1. **`Read`** `oa/guardrails.md` → `intake.md`  
2. **首次 / 改向量**：`Read` `oa/configure_embedding.md` → 对话问清（可跳过 / 预设 / 自定义 URL+模型+Key）→ `config.py set … --api-key …`（默认 **selftest**）→ 需重建则人确认后 `rebuild_vectors.py --confirm`  
3. **入库**：`ingest_case.py`（支持 `--pdf`）；笔记进 `oa/cases/history/`（或 pending/drafts）；自动刷新 `_OA索引` / Canvas / Bases；无向量时仍写笔记 + 元数据  
4. **答复**：`search_cases.py --pdf …`（标签优先过滤；向量可用则 Top-K，失败/超时回退标签，展示 `retrieval_mode` + diff）→ 策略勾选 → 草稿 → 人审  
5. **仅刷新 Obs**：`python tools/oa/refresh_vault.py` 

依赖：`pip install -r tools/oa/requirements-oa.txt`。  
**与 A/B/C 互斥**：不写交底书主流程；草稿须复核后递交。

---

## 迭代模式（交底书 · 摘要）

- 补材料 / 扩展：`iteration_context` → `merger` → 新时间戳稿（实用/外观若改图或主题须同步 **`figure_plan`**）  
- 纠错：`iteration_context` → `correction_handler` → 新时间戳稿（同上）  
- 完整申报包 / 项目方案同步深化：`iteration_context` → `references/filing_ready_iteration_delivery.md` → `merger` → `disclosure_self_check §8.6`；用唯一 `MERGE_TAG` 防重复，不以内部综合评分替代五项申报硬门。

---

## Agent 自用工作流检查清单

```
□ 已区分模式 A / B / C / D / 迭代，未混跑
□ 交底未指定类型时已默认发明；材料偏实用/外观已按需反问
□ Step 3–4 / Step 7 已 Read 对应类型子目录 md（非发明套用实用/外观）
□ 查新 cnipa 已带与案件一致的 --type；abstract 必用
□ 发明含公式：已写 formula_plan（范式∈references/formulas）且可算数值例；禁装饰音；已 check_formula_plan 或等价自检
□ 实用/外观已走 schema 填表（shared）并写出 figure_plan（含必要 relates_to），未看图直接长文；成文只嵌清单入文图
□ Step 2/补材料已 cad_scan：遇 STEP 先反问再装依赖；仅原生 CAD 则回复末尾提示导出 STEP；未确认不开 step_to_views
□ 外观若开启辅助线稿：有用户「是」、有参考图、经 design_lineart_gate；未纯文生图；辅助条默认不入正文
□ 实用若开启结构辅助线稿：有用户「是」、有参考图+Structure、经 structure_lineart_gate；件号对齐 parts；优先 overlay；未自创件号；辅助条默认不入正文
□ 迭代改材料/主题时已重评 figure_plan（含图际关联）
□ 解读实用/外观：公开号种类码或 patent_type.py / fetch 状态已判别类型，并 Read type_hooks + 共用 schema（用户未口头声明也可）
□ 模式 C：已显式触发；清单含观点↔URL 主表；未确认前未改技能；确认后才 apply
□ 交底定稿交付：已按 evolution/soft_nudge 判断是否加低频一句（未每次必出、未写入正文）
□ 模式 D：已显式触发；向量可选已反问（可跳过）；PDF 已自动抽取；入库已脱敏；检索展示 retrieval_mode；向量失败已回退标签；需重建时已人确认；草稿已人审提示
□ 路径使用 prompts/disclosure|reader|shared|evolution|oa 与 tools/crawl|shared|oa|patent_reader/{extract,analyze,vault,shared}
□ 完整申报包已区分“发明探索门”与“文件申报门”；五项硬门逐项通过或明确阻断，I4/I5组合风险进入代理师风险说明而非被隐匿
□ 正式包增量已有唯一 MERGE_TAG，已查重并登记在迭代记录/差异清单/版本摘要；法定正文不含该内部tag
□ 收件人目录不含脚本、缓存、淘汰路线或内部评审稿；DOCX/PDF已做OOXML、中文可见文字、图号、分页和逐页渲染检查
```
