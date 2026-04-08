---
name: patent-disclosure-skill
description: "通用中国专利挖掘发现与交底书生成全流程：扫描项目文档挖掘专利点、讨论融合、基于脱敏模版生成技术交底书、联网查新、生成后自检含逻辑闭环与公式参数一致性。| Patent mining, disclosure drafting, prior-art search, and consistency self-check."
version: "1.8.1"
user-invocable: true
argument-hint: "[可选：项目路径或技术主题关键词]"
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 专利挖掘与交底书生成

本技能覆盖 **专利点挖掘** → **查新与差异化** → **交底书生成** → **自检完善** 全流程；分步指令在 **`prompts/`**，每步执行前 **`Read`** 对应文件，与步骤的对照见「Prompt 文件映射」。

## 环境与约定

- **语言**：默认与用户语种一致；专利与法律术语采用行业常用表述。
- **图示定稿（Step 7）**：**3.2**/**3.4** 用 fenced **mermaid**；执行方式、**`mmdc`** 安装与降级规则见下表「交底书定稿交付」行及 **`tools/README.md`**（正文不要求 ASCII 框图或 PlantUML）。

---

## 触发条件

在用户使用以下任一方式时启用本技能：

- 明确提及：专利挖掘、专利点、技术交底书、交底书、专利交底书、查新、现有技术对比等
- 斜杠或简短指令：如 `/patent-disclosure-skill`、`/patent-disclosure`、`/交底书`
- **迭代模式（按意图识别）**：当用户意图明显是在**已有交底书或上一轮输出**上继续工作（如改章节、补实施例、补材料、修正参数/事实、调整表述等），**无需**用户写出「迭代」等固定词，也**不必**询问是否进入迭代——Agent 应 **`Read`** **`prompts/iteration_context.md`**，再 **`Read`** `prompts/merger.md`（侧重**新材料、扩展合并**）或 `prompts/correction_handler.md`（侧重**纠错、与事实或风格不符**），**严格按该文件开头的「执行门禁」**（优先执行，不可跳过）**做完合并或纠正**，**另存为新文件**：**`{案件名}_{YYYYMMDDHHmmss}.md`** 与同名 **`.docx`**（与首次定稿同一命名规则，见 **`disclosure_builder.md` §7.3 第 5 点**），**不覆盖**旧稿（除非用户明确要求）。**禁止**在迭代意图已成立时默认回到 Step 3–4 专利点全文分析（除非用户明确要求重新挖掘专利点）。对话中**已出现**交底书路径、附件或上文刚交付的草稿时，优先按迭代处理。

---

## 工具与数据来源

按任务选用能力；具体工具名称以当前 Agent 环境为准。

若扫描范围内含 **Word（.docx）** 或 **PowerPoint（.pptx）**，须在 Step 2 纳入阅读前用本仓库 **`docx_to_md.py`** / **`pptx_to_md.py`** 转为 Markdown；依赖 **`pip install -r requirements.txt`**，命令与说明见下表对应行。

### 常见任务与建议方式

| 任务 | 建议方式 |
|------|----------|
| 加载分步指令 | **`Read`** → `${CLAUDE_SKILL_DIR}/prompts/*.md`，见下表 |
| 读代码、设计文档、PDF、图片 | 文件读取工具；大仓库先用搜索/语义检索定位再精读 |
| Word（.docx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/docx_to_md.py --input {path}.docx --output {dir}/{name}.md`；图片默认写入与 `.md` 同级的 `{name}_media/`；需 `pip install -r requirements.txt`（含 mammoth）；复杂版式可改由所内导出 PDF/MD 再扫 |
| PowerPoint（.pptx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/pptx_to_md.py --input {path}.pptx --output {dir}/{name}.md`；默认 `{name}_media/`；需 `pip install -r requirements.txt`（含 python-pptx）；**旧版 .ppt 不支持**，请先另存为 `.pptx`；图表/SmartArt 等若未以图片形状嵌入则可能仅能从备注或另行导出补全 |
| 罗列目录、按名找文件 | 目录列举 / 按文件名搜索 |
| 联网查新（Step 5） | 执行前 **`Read`** `prompts/prior_art_search.md`；著录与外链要求以该文件为准 |
| 交底书定稿交付（**须同时** .md + .docx） | **3.2** 系统框图与 **3.4** 流程图均用 fenced ``mermaid``，**不要** ASCII 文字流程图/框图。定稿执行 **`tools/mermaid_render.py`**：mermaid 转 PNG（失败块保留围栏）后默认生成同名 **.docx**；若 Word 失败，按 stderr 提示手动运行 **`md_to_docx.py`**。详见 **`tools/README.md`** |
| 保存交底书路径 | 写入用户指定路径；未指定时可建议 `./outputs/{案件标识}/`；**凡交付的** `.md` / `.docx` 须为 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5 点，**含首次定稿与迭代**），勿默认覆盖旧稿；`outputs/` 整目录默认由 `.gitignore` 忽略 |
| 迭代对话留档 | 每轮 **merger / correction** 交付后，在案件目录追加 **`交底书修订对话记录.md`**（**`tools/iteration_dialog_log.py`** 或等价手工），见 **`prompts/iteration_context.md`** |

---

## Prompt 文件映射

| 步骤 | 文件 | 用途 |
|------|------|------|
| Step 1 | `prompts/intake.md` | 边界与输入问题 |
| Step 2 | `prompts/project_scan.md` | 项目文档扫描；**须**对 `.docx`/`.pptx` 先转换再读（见该文件「Office 文档」节）；独立图片目录可跳过 |
| Step 3–4 | `prompts/patent_points_analyzer.md` | 候选专利点、融合与选定 |
| Step 5 | `prompts/prior_art_search.md` | 联网查新与分析要求 |
| Step 6 | `prompts/disclosure_preview.md` | 全文前的摘要预览 |
| Step 7 | `prompts/disclosure_builder.md` + `prompts/template_reference.md` | 交底书结构、脱敏与图示规范；**mermaid 系统框图与流程图范例在 template_reference** |
| Step 8 | `prompts/disclosure_self_check.md` | 内部自检，不写入正文 |
| 迭代 | `prompts/iteration_context.md` | 迭代意图、落盘命名、**修订对话记录 md**（含对话/记录时间） |
| 迭代 | `prompts/merger.md` | 新材料增量合并；**文首含门禁**；输出 `{案件名}_{时间戳}.md`/`.docx` |
| 迭代 | `prompts/correction_handler.md` | 对话纠正；**文首含门禁**；输出 `{案件名}_{时间戳}.md`/`.docx` |

---

## 主流程（执行顺序）

1. **`Read`** `intake.md` → 执行 Step 1  
2. **`Read`** `project_scan.md` → 执行 Step 2  
3. **`Read`** `patent_points_analyzer.md` → 执行 Step 3–4  
4. **`Read`** `prior_art_search.md` → 执行 Step 5  
5. **`Read`** `disclosure_preview.md` → 执行 Step 6；用户可跳过  
6. **`Read`** `disclosure_builder.md` 与 **`Read`** `template_reference.md` → 执行 Step 7（**首次交付**的 `.md`/`.docx` 亦须 **`{案件名}_{YYYYMMDDHHmmss}`**，§7.3 第 5 点）  
7. **`Read`** `disclosure_self_check.md` → 内部执行 Step 8，修订后交付  

**禁止**：交底书正文中包含「自检清单」章节；自检仅内部使用。

---

## 迭代模式（摘要）

**启用方式**：根据用户**自然语言意图**判断（见上文「触发条件」），**不要求**固定关键词，**默认不**为「是否迭代」打断用户。

- **补充材料 / 扩展章节**：`Read` → `iteration_context.md` → `merger.md`；合并结果**另存为**带时间戳的 `.md`/`.docx`（§7.3 第 5 点）；**追加** `交底书修订对话记录.md`（`iteration_dialog_log.py` 或手工）；完成后**必须**输出「合并摘要」留档  
- **指出错误 / 与事实或参数不符**：`Read` → `iteration_context.md` → `correction_handler.md`；纠正结果**另存为**带时间戳的 `.md`/`.docx`；**追加**对话记录；完成后**必须**输出「纠正摘要」留档  

主流程 Step 7→8 的 **`disclosure_self_check.md`** 仍在新稿定稿路径上内部执行。

---

## Agent 自用工作流检查清单

```
□ 已按步骤 Read 对应 prompts；Step 2 若目录含 Office，已执行 docx_to_md / pptx_to_md 并读了产出 `.md`
□ 识别到「在已有交底书上修改」类意图时，已 Read `iteration_context.md` 并选用 merger 或 correction_handler（而非从头跑扫描）；交付为**新** `{案件名}_{时间戳}.md`/`.docx`，未无故覆盖旧稿
□ 执行 merger / correction_handler 后，已在对话中输出该文件要求的留档摘要（合并摘要 / 纠正摘要）；案件目录已追加 **`交底书修订对话记录.md`**（或等价日志）
□ 查新完成且写入 1.1 与区别论述（符合 `prior_art_search.md`）
□ 除用户明确跳过外，完成摘要预览
□ 脱敏、mermaid（定稿均已渲染为 PNG）、章节引用符合 template_reference；**已交付 .md 与 .docx**，且**文件名符合 §7.3 第 5 点**（**凡交付均含**时间戳后缀）；**正文无**技能/示例仓库类文末脚注
□ 自检在后台完成，正文无自检清单章节
```
