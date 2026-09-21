# 项目文档扫描（Step 2）

## 目标

按优先级扫描并提取**可专利化**内容。**根据当前项目结构调整扫描路径**。

## 优先级表

| 优先级 | 文档类型 | 关注内容 |
|--------|----------|----------|
| 1 | 专利相关文档 | 专利点分析、已有交底书、专利申报建议、创新点汇总 |
| 2 | 详细设计/方案文档 | 详细设计、方案讨论、流程图、完整流程、技术对比分析 |
| 3 | 核心实现代码 | 算法与策略实现、业务逻辑与流程编排、数据处理与转换、规则引擎与决策逻辑、接口与集成设计、状态机与调度机制、性能优化与缓存策略、安全与权限控制等（依项目领域灵活识别） |
| 4 | 系统设计文档 | 系统设计、架构说明、模块划分、数据流与控制流 |

## 扫描目标目录模版

执行时按项目实际目录填写：

```
[项目根目录]/
├── [专利或文档目录]/     ← 专利点分析、交底书、申报建议
├── [设计文档目录]/       ← 详细设计、方案讨论、流程图、技术对比
├── [代码目录]/           ← 算法实现、业务逻辑、规则引擎、接口与集成、调度机制等
└── [根目录]/             ← 系统设计、架构说明、模块与数据流
```

## 文档敏感信息检查

**读取文档前**，**必须**先检查敏感信息：
  ```bash
  python skills/patent-disclosure/tools/data_mask.py examine_code_file "<项目根目录>"
  ```
  **将检测结果告知用户**（含「检测到 N 处敏感信息」或「未发现敏感信息」），并等待用户回复确认后，方可读取原文件。禁止在未获得用户确认的情况下直接阅读。


## 执行提示

- 大仓库先用搜索 / 语义检索定位关键文件，再精读。
- 记录**引用路径或文件名**，便于在交底书中写「参见某设计」时脱敏表述。
- 凡出现 **`.docx` / `.pptx` / `.pdf`**，**必须**按下一节 **「Office 文档与 PDF」** 先转 Markdown 再读，不可跳过或只扫纯文本而漏掉 Office/PDF。
- 凡扫描树内可能有 CAD / 三维文件，**必须**按 **「CAD / STEP（可选，默认关闭）」** 执行分类；**不得**在用户未确认时安装 STEP 依赖或运行 `step_to_views.py`。

## CAD / STEP（可选，默认关闭）

**开关**：STEP 多视角解析 **默认关闭**。Step 2 **只分类、不中断**挖点/成文。交底 md+docx **落盘之后**再反问；仅当用户回复 **是** 后才装依赖并转换。回复 **否** 则跳过解析。用户在成文前**主动要求**开启的除外。

**分类扫描（轻量，无重依赖）**：在扫描根（含 `knowledge/`、用户 @ 的目录等）执行：

```bash
python skills/patent-disclosure/tools/cad_scan.py -r "<扫描根>" --json
```

（多根可重复 `-r`。初次 Step 2 与**多轮补材料后**均须再跑。）

依据 JSON 的 `action`：

| `action` | 行为 |
|----------|------|
| `ask_enable_step_parse` | **不中断**后续挖点/成文。记下 `step_files`，成文只用已有图片/文档。**交底落盘后**在 **`## 交付后请确认` 第 1 条**用 `messages.ask_enable_step_parse` 反问（请回 **是** / **否**）。未得 **是** 前禁止装依赖与 `step_to_views.py`。 |
| `hint_export_step` | **不中断**扫描（继续 Office/文档/图片流程）；在 **`## 交付后请确认` 第 1 条**提示：可将原生 CAD 导出为 `.step`/`.stp` 后再开启解析（文案可用 JSON `messages.hint_export_step`）。 |
| `none` | 无 CAD 相关文件，忽略。 |

**用户在交付后回复「是」后**（或成文前主动要求开启后）：

先探测隔离环境（**不要每次安装**）。JSON 的 `ok` 为 true 则跳过 bootstrap：

```bash
python skills/patent-disclosure/tools/cad_venv.py
```

若 `ok` 不为 true：先向用户说明「正在配置本地 CAD 环境（隔离 `cad-env`，Python 3.10–3.12，耗时较久）」，再执行：

```bash
python skills/patent-disclosure/tools/bootstrap_cad_venv.py
```

然后出图（CadQuery 在 `tools/cad-env`；PNG：**Cairo 或** Playwright 截 SVG，两条路都不用 matplotlib）：

```bash
python skills/patent-disclosure/tools/run_step_to_views.py --enable-step-parse \
  -i "<path/to/model.step>" -o "outputs/{案件标识}/cad_views"
```

- **禁止**把 CadQuery 装进主环境 / 3.13。本机已是 3.11 或 3.12 时用当前解释器建 venv，**不要**强行再装 3.10。
- 产出：`views/*.svg`（必有）；`views/*.png`（有 Cairo 或浏览器时）；`assembly_tree.yaml`、`structure_schema.seed.yaml`、`figure_plan.seed.yaml`。无 PNG 时 figure_plan 用 SVG。
- `figure_plan.seed.yaml` 里 CAD 条为 `kind: cad`、`use_in_disclosure: false`、`role: reference`：**不是线稿，不得入文**。
- 随后按 `fill_structure_schema.md` 审改 seed：识图重评 `relevance` / `quality` / `score`，CAD 条保持不入文。再跑 `image_gen.py`：有合格线稿才跳过生成，否则以高分 CAD/实拍为参考图生图，或文生图。另存新时间戳交底稿。
- **禁止**无 `--enable-step-parse`（且无环境变量 `PATENT_SKILL_STEP_PARSE=1`）时强行转换。
- 用户回复 **否**：记录决定，保留已交付稿；可在 **`## 交付后请确认` 第 1 条**保留「日后可再开 STEP 解析」一句。

**后缀**：`.step`/`.stp` 为可解析目标；原生 CAD（`.sldprt`/`.sldasm`/`.ipt`/`.iam`/`.prt`/`.asm`/`.catpart`/…）见 `tools/cad_formats.py`，**本技能不直接解析**。

## 外观线稿（必做）

仅**外观设计**。细则：`prompts/image_gen.md` + `prompts/design_lineart_assist.md`。

- **默认开**；**不问用户**。填 Appearance + figure_plan 后跑 `image_gen.py`，再写 brief / 出门禁 / 生成或选用线稿。
- 线稿只有两条路：材料已有合格 `kind: lineart`，或大模型生成（图生图 → 失败则先描述再文生图）。
- 干净实拍 **和** 线稿都写入交底 Markdown 与 Word。实拍不得标成线稿。CAD 不入文。
- 仅用户明确不要线稿或 `PATENT_SKILL_SKIP_LINEART=1` 才跳过。

## 实用新型结构线稿（必做）

仅**实用新型**。细则：`prompts/image_gen.md` + `prompts/structure_lineart_assist.md` + `prompts/structure_lineart_compose.md`。

- **默认开**；**不问用户**。填 Structure + figure_plan 后跑 `image_gen.py`。
- CAD 投影 **不是**线稿、**不得**入文；分数够才可能作图生图参考。
- 轮廓按 `parts` **拼装**为子 SVG + 总图相对引用，序号层推荐 **overlay 注入**（禁止自创件号）。勿与 `design_lineart_*` 混用。
- 仅用户明确不要线稿或 `PATENT_SKILL_SKIP_LINEART=1` 才跳过。

## Office 文档与 PDF（.docx / .pptx / .pdf）：必先转换再读

**格式**：脚本仅支持 OOXML（**`.docx` / `.pptx`**）和 PDF（**`.pdf`**）。旧版 **`.doc` / `.ppt`** 须先在 Office / WPS 中**另存为**新格式后再走下列流程。

Agent **不得**因「只能舒适读取文本」而**遗漏**项目内的 Word / PPT / PDF：**必须先转为 Markdown 再纳入扫描**，不能只扫 `.md` 与源码。

1. **发现**：在扫描目录内 **`Glob` 或列举** `*.docx`、`*.pptx`、`*.pdf`（含子目录，如 `docs/sample_*.docx`）。
2. **转换（本仓库脚本）**：对每个文件执行（路径相对本技能仓库根）：

   ```bash
   python skills/patent-disclosure/tools/docx_to_md.py -i "<路径>/<名>.docx" -o "<同目录或 docs>/<名>.md"
   python skills/patent-disclosure/tools/pptx_to_md.py -i "<路径>/<名>.pptx" -o "<同目录或 docs>/<名>.md"
   python skills/patent-disclosure/tools/pdf_to_md.py -i "<路径>/<名>.pdf" -o "<同目录或 docs>/<名>.md"
   ```

   需已 `pip install -r requirements.txt`。输出旁会生成 **`{md 主名}_media/`**，内为嵌入图，**以生成的 `.md` 正文与图片引用为扫描依据**。
3. **再读**：**`Read`** 上述新生成的 `.md`（及必要时扫一眼 `_media` 文件名用于脱敏引用），与原有 `.md`、代码**同等对待**，摘要进专利点材料表。
4. **解析重点**：表格、编号列表、**PPT 每页标题与正文**、**Word 修订区以外的正文**、**备注**（`pptx_to_md` 会写入「备注」小节）、**PDF 每页正文**——均属可专利化叙述来源。

## 图片与裸图目录（默认不识图）

- **`sample_assets/`**、`node_modules/`、`dist/`、`build/`、`.next/`、`src/assets/`、前端切图等目录下的独立 `.png` / `.jpg` / `.webp`：**不作为** Step 2 必须逐个打开的对象。
- **例外（才 Read 识图）**：用户**点名**某图片路径或说「这张图是场景示意，补充到交底书」；或某图已嵌在已转换 Office 的 `_media` 且正文当技术示意图引用。
- Word/PPT 转换后，嵌入图已在 **`![](相对路径)`** 中体现，**以 Markdown 文本扫描为主**即可；不要为了找图去扫整个前端工程。

点名之后：理解图上对象与图例 → 判别（技术示意图 / 拓扑 / 流程照片 / 结构 / 界面截屏 / 图标切图 / 营销场景）→ 匹配章节。图标、切图、营销场景不入文并说明原因。技术示意图拷到案件 `assets/`，在 3.1 或第六章编号嵌入，不要改画。这与外观 `photo_scene`（棚拍/包装默认不入文）不是一类，不要套那条挡技术环境图。

## 按专利类型加扫（实用 / 外观）

当前类型为**实用新型**或**外观设计**时，在通用优先级之外**额外**关注：

| 类型 | 加扫重点 |
|------|----------|
| 实用新型 | 装配图、爆炸图、结构说明、`structure_*.yaml/json`、零件表；再按 `prompts/fill_structure_schema.md` 识图填表并写出 **`figure_plan.yaml`** |
| 外观设计 | 按要点落面收正投影/立体图（非默认六视；官方全称）、效果图、色彩说明、`appearance_*.yaml/json`；再按 `prompts/fill_appearance_schema.md` 与 `references/design_view_cnipa.md` 填表并写出 **`figure_plan.yaml`** |

独立结构/外观附图（用户点名或 schema `source_images`）**需要** Read 识图，不适用下方「sample_assets 跳过」惯例。

## 示例案件 `knowledge/`（练习时勿漏）

### 发明 · `skills/patent-disclosure/examples/example_batch_job_scheduler/knowledge/`

| 路径 | 动作 |
|------|------|
| `docs/architecture.md` | 直接 Read |
| `docs/sample_architecture_review.docx` | **先** `tools/docx_to_md.py` → 再 Read 生成的 `.md` |
| `docs/sample_scheduler_deck.pptx` | **先** `tools/pptx_to_md.py` → 再 Read 生成的 `.md` |
| `docs/sample_assets/*.png` | **跳过**单独精读（内容已由 Office 内嵌图 + 转换 MD 覆盖） |

### 实用新型 · `skills/patent-disclosure/examples/example_utility_model_ev_powertrain/knowledge/`

| 路径 | 动作 |
|------|------|
| `docs/structure_brief.md` | Read（主材料；部件表与建议剖视/爆炸/局部） |
| `assets/*.jpg` | 展台实拍，**须**识图打分；`kind` 为 `photo_clean` / `photo_scene`，**不入文**；本案例无合格线稿，成文前按 brief **文生图** |

教学用 STEP 不在本示例：见 `skills/patent-disclosure/tests/fixtures/cad/demo_snap_plate.step`（`cad_scan` / `gen_demo_snap_step.py`）。

### 外观 · `skills/patent-disclosure/examples/example_design_desk_lamp/knowledge/`

| 路径 | 动作 |
|------|------|
| `docs/design_brief.md` | Read |
| `assets/*.{jpg,png}` | **须**识图填 AppearanceSchema + **`figure_plan.yaml`**（教学用；勿依赖预填 yaml；场景图默认低优先级） |