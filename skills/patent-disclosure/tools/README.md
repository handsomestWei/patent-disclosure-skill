# 交底包 tools

本目录是 **patent-disclosure** 的脚本根：浏览器、docx、mermaid、公式、CAD、线稿、出图后端，以及 `crawl/` 轻量查新、`fence/` 保护型 1+N。

整仓安装时从仓库根调用：`python skills/patent-disclosure/tools/…`。单独拷走本包时，本目录即为 `tools/`。

## 国知局公布公告检索（交底 Step 5 轻量查新）

| 脚本 | 作用 |
|------|------|
| **`crawl/cnipa_epub_search.py`** | **（Step 5 优先）** 一步拉取+解析，不落盘；**一词一页**（公布模式默认每页 10 条）；**`--type invention\|utility_model\|design\|all`**；`--class` 默认 1×1；首页最多 4 个词 |
| **`crawl/cnipa_epub_crawler.py`** | 检索入口：默认同会话 `fetch` 提交（每词 0.2–0.6 秒），失败自动回退整页导航；词间**自适应节流**（按响应延迟增减，节奏跨进程持久化）；拉取并默认保存结果页 HTML。文件头记录站点防护特征与实测结论 |
| **`crawl/cnipa_epub_nav.py`** | 兜底路径：整页导航提交的原子操作（gate / 填框 / 提交 / 取 HTML），由上面的入口调用，一般不直接运行 |
| **`crawl/cnipa_epub_parse.py`** | 仅解析已保存 HTML |
| **`crawl/cnipa_epub_wait.yaml`** | 公布站等待与收口上限（中文注释）；脚本优先读 YAML，缺文件回退 `cnipa_epub_wait.DEFAULTS` |
| **`patent_type.py`** | 类型别名、国知局 checkbox、Google Patents 查询提示 |

依赖：`pip install playwright`（或根目录 `requirements.txt`）。浏览器见 **`tools/browser.py`**。查新说明见 **`prompts/prior_art_search.md`**。

著录检索（发明人/申请人/分类号等高级查询）是另一个技能包，**不是**本目录脚本。本包查新只用上面的 `crawl/`，不要 import、不要调用检索爬虫。整仓时入口在仓库根 `SKILL.md`。

抓取失败时降级 **WebSearch**（Google 学术**无**专利类型过滤；Google Patents 支持 PATENT/DESIGN，实用新型靠关键词+国知局）。

---

## CAD / STEP（可选，默认关闭）

| 脚本 | 作用 |
|------|------|
| **`cad_scan.py`** | 扫描 `.step`/`.stp` 与原生 CAD 后缀；输出 JSON（`ask_enable_step_parse` / `hint_export_step`）。**无重依赖**。 |
| **`cad_formats.py`** | 后缀表与提示文案。 |
| **`cad_venv.py`** | 探测 `tools/cad-env`；已能 `import cadquery` 则 `skip_install=true`。 |
| **`bootstrap_cad_venv.py`** | 仅在未就绪时建 venv + `--isolated` pip（国内源 → pypi.org）。 |
| **`step_to_views.py`** | STEP → SVG（有 Cairo 再 PNG）。须 **`--enable-step-parse`**；请用 cad-env 的 Python。 |
| **`svg_screenshot.py`** | 短时 HTTP + 无头浏览器把 SVG 截成 PNG（端口先探测，用完关闭）。 |
| **`run_step_to_views.py`** | 探测 cad-env → 必要时 bootstrap → 出图 → 补 PNG。 |
| **`gen_demo_snap_step.py`** | 生成教学用 `tests/fixtures/cad/demo_snap_plate.step`（无 CadQuery）。 |
| **`requirements-step.txt`** | ASCII only；CadQuery + cairosvg；**只装进 cad-env**。 |

流程纪律见 **`skills/patent-disclosure/prompts/project_scan.md`**「CAD / STEP」：有 STEP 成文不中断，交底落盘后再反问；仅有原生 CAD 则交付回复末尾提示导出 STEP。投影图是普通材料（`kind: cad`），**不得当线稿、不得入文**；打分后可能作图生图参考。

CadQuery 官方轮子支持 **Python 3.10–3.12**（**不是** 3.13）。本机已是 3.11/3.12 就用当前解释器建 `cad-env`，不要强行找 3.10。无系统 Cairo 时 **保留 SVG**，用本技能已有的 Playwright 截 PNG。CAD 出图**不用** matplotlib（matplotlib 仅发明公式 PNG 可选）。

```bash
python tools/cad_scan.py -r knowledge --json
python tools/cad_venv.py
python tools/run_step_to_views.py --enable-step-parse -i a.step -o outputs/case/cad_views
```

---

## 发明公式范式（`references/formulas/`）

| 脚本 / 文档 | 作用 |
|-------------|------|
| **`references/formulas/paradigms.yaml`** | 无原文时的起草菜单 |
| **`references/schemas/formula_plan.schema.yaml`** | 案件 `formula_plan.yaml` 合同（`origin` / `source_kind` / `verified` / `omitted`） |
| **`formula_paradigms.py`** | `list` / `show` / `combos`（支持案件目录覆盖） |
| **`check_formula_plan.py`** | 校验来源标记、`source_kind` / 未核对、agent 选题 id、禁装饰音、数值例；`--eval` 简单式代算；化学守恒 / 量纲粗检 |

```bash
python tools/formula_paradigms.py list
python tools/check_formula_plan.py -i outputs/case/formula_plan.yaml --eval
```

成文纪律见 **`skills/patent-disclosure/prompts/invention/disclosure_builder.md` §7.7**。

## 专利布局 / 保护型 1+N（旁路）

脚本在 **`tools/fence/`**（与 `crawl/` 一样单独成目录）。细则见 `tools/fence/README.md`。

```bash
python tools/fence/check_layout.py --family outputs/案/fence/family.yaml --matrix outputs/案/fence/matrix.yaml
python tools/fence/check_scorecard.py --table
```

## 线稿规划（成文前必做）

| 脚本 / 文档 | 作用 |
|-------------|------|
| **`prompts/image_gen.md`** | Agent 合同：合格已有线稿 / 图生图 / 文生图；CAD 不得当线稿入文 |
| **`image_gen.py`** | 读 figure_plan，打印 `mode` / `fallback` |

```bash
python tools/image_gen.py --case-dir outputs/case
```

## 外观线稿（必做）

| 脚本 / 文档 | 作用 |
|-------------|------|
| **`prompts/design_lineart_assist.md`** | 不问用户；写 brief → 门禁 → 图生图或文生图 |
| **`design_lineart_gate.py`** | 默认开；无源图则允许文生图；`--prepare-jobs` 写出 `lineart_assist/design_lineart_jobs.json` |
| **`references/schemas/design_lineart_brief.schema.yaml`** | 描述合同 |

```bash
python tools/design_lineart_gate.py --case-dir outputs/case --prepare-jobs
```

生成的线稿默认入文。外观另将干净实拍一并写入 md 与 Word。CAD 不得 `use_in_disclosure: true`。

## 实用新型结构线稿（必做）

| 脚本 / 文档 | 作用 |
|-------------|------|
| **`prompts/structure_lineart_assist.md`** | 不问用户；轮廓 → 按件拼装 → 按 Structure 叠件号 |
| **`prompts/structure_lineart_compose.md`** | 独立拼装指令：每件一个子 SVG；总图相对引用；粒度止于件号 |
| **`structure_lineart_gate.py`** | 默认开；无 Structure 拒绝；无源图则允许文生图；并入 `check_source_parts` 的 ERROR |
| **`check_source_parts.py`** | 源材料门禁：未披露件号 / 幻觉 covers / uncertain 进权要 |
| **`structure_lineart_compose.py`** | 读 compose YAML，写出 `parts/{视}_{id}.svg` 与相对引用的总 SVG |
| **`structure_callout_overlay.py`** | 读取锚点后以 SVG 叠标；默认按原图墨线把序号推出实体/内腔、把引线终点吸到墨线；有 `base_svg_path` 时注入拼装图；叠标后扩大画布留白 |
| **`references/schemas/structure_lineart_brief.schema.yaml`** | 描述合同（与外观分文件） |
| **`references/schemas/structure_lineart_compose.schema.yaml`** | 按件槽位 / crop / 单件图合同 |
| **`references/schemas/structure_callout_anchors.schema.yaml`** | 锚点持久化合同（`anchor` + `label` + 置信度；可选 `base_svg_path`） |

```bash
python tools/structure_lineart_gate.py --case-dir outputs/case --prepare-jobs
python tools/check_source_parts.py --case-dir outputs/case --write
python tools/structure_lineart_compose.py --case-dir outputs/case
python tools/structure_callout_overlay.py --case-dir outputs/case --anchors outputs/case/structure_callout_anchors.yaml
```

推荐：轮廓之后按件写出子 SVG 再拼总图，再 `callout_mode: overlay` 注入件号。大模型只定位，Python/SVG 叠标；出图后端不是 `local` 时可先试一次生图件号（以轮廓图为输入只加号，轮廓有变即不过），不过就走 overlay，不反复生图纠号。叠标后须读图按 `parts` 名称核对引出线（改 YAML 重叠标，最多 2 轮）；脚本合法 ≠ 图面对。禁止自创件号；CAD 投影不是线稿。可编辑源是 `parts/*.svg` + 总图引用，入文 PNG 只是预览。

## 出图后端（生图）

流程见 **`prompts/figure_generation.md`**。方法移植自 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill)（MIT），即宿主内置生图工具优先、CLI 兜底、样图门、一图一 job、读图 QA、登记，失败回退本地渲染。

| 脚本 | 前缀 | 作用 |
|------|------|------|
| **`figure_backend.py`** | `FIGURE_BACKEND:` | 探测 / 确认 / 记录本案后端（`builtin` / `cli` / `local`）与样图，写 `figure_backend.json`；`PATENT_SKILL_FIGURE_BACKEND=local` 强制旧行为 |
| **`figure_jobs.py`** | `FIGURE_JOB:` | `prepare`（mermaid md / invention_figures.yaml / 线稿门禁 jobs）→ `record` / `block` / `fallback` / `status`；`status` 有 pending、blocked 时退出码 2 |
| **`image_api.py`** | `IMAGE_API:` | CLI 后端：`job --job figure_jobs/x.json`（有参考图走 edit）、`generate`、`edit`、`generate-batch`；`--dry-run` 只打印请求 |
| **`image_runtime.py`** | `IMAGE_RUNTIME:` | `config` 写 `~/.patent-skill/.env`（0600，key 打码），`doctor [--check-api]` |
| **`bw_normalize.py`** | `BW_NORMALIZE:` | 后处理：真黑白、按内容裁切、DPI、可选 SVG 包装与摘要附图副本；报 `color_ratio` / `gray_ratio` |
| **`image_providers/`** | — | OpenAI 兼容与 AtlasCloud 适配 |
| **`references/figure_prompt_templates.yaml`** | — | 各类附图的结构化 prompt 模板（黑白、无图号、只画清单内的件） |

依赖 `requirements-image.txt`（openai、Pillow），仅 CLI 后端需要，征得同意再装。上述文件在申请包 `tools/` 有同文副本（`patent-application/tests/test_design_view_sync.py` 比对）。

```bash
python tools/figure_backend.py --case-dir outputs/case
python tools/figure_jobs.py prepare --case-dir outputs/case --from-md outputs/case/草稿.md
python tools/image_api.py job --job outputs/case/figure_jobs/mmd_01.json
python tools/figure_jobs.py record --case-dir outputs/case --fig mmd_01 --qa-note "文字逐字核对通过"
python tools/mermaid_render.py -i outputs/case/草稿.md -o "outputs/case/案件名_20260101120000.md" --ai-figures outputs/case/figure_jobs.json
python tools/figure_jobs.py status --case-dir outputs/case
```

## Office / mermaid

用 **`docx_to_md.py`**、**`pptx_to_md.py`**、**`pdf_to_md.py`**、**`mermaid_render.py`** 等。

## mermaid_render.py — mermaid：图示 → PNG + 定稿 Markdown + **默认生成 Word**

将 fenced **mermaid**（`` ```mermaid`` ``）逐块经 **Playwright + 内置 `vendor/mermaid.min.js`** 渲染为 PNG；输出 `.md` 中**保留** mermaid 围栏源码，并追加 ``<!-- ![图示 n](mermaid_figures/…) -->`` 供 **`md_to_docx.py`** 嵌入 Word（Word **仅**嵌 PNG，不写 mermaid 代码块）。**3.2 系统框图**与 **3.4 流程图**均用 mermaid（`flowchart` / `subgraph` 等），交底书正文**不再**要求单独的文字框图或 PlantUML。流程图步骤号（`S1` 等）须写在**可见标签**里；脚本会把 `S1[文案]` 补成 `S1["S1 文案"]` 再出图，否则 PNG 上看不到序号。

**生图失败降级**：某一围栏失败时**不中断**——该处**保留**原 `` ```mermaid`` … `` ``` `` 源码；其余块照常出图。仍写出定稿 `.md`，并**照常尝试**生成 Word（未出图块在 Word 中为 **Consolas 代码块**）。无可用浏览器时同样保留围栏，不阻塞 Markdown。

### 依赖：mermaid（Playwright，无需 Node）

与国知局查新**共用** `tools/browser.py`：系统 **Chrome → Edge → Playwright 自带 Chromium**。仓库已内置 `tools/vendor/mermaid.min.js`。

| 需要 | 说明 |
|------|------|
| `pip install playwright` | 已写入根目录 `requirements.txt` |
| 本机 Chrome 或 Edge | **推荐**；有则不必再下 Chromium |
| `python -m playwright install chromium` | **仅当**本机无 Chrome/Edge 时 |

探测：`python tools/browser.py --probe`。**禁止**为出图执行 `npm install` / `npx -y @mermaid-js/mermaid-cli`。`tools/package.json` 仅为旧 mmdc 可选遗留，主路径不使用。

生成 Word 仍需：`pip install -r requirements.txt`（python-docx 等）。

默认视口 **1400×1050**、`device_scale_factor=2`（历史参数名 `--mmdc-scale` / `--mmdc-width` / `--mmdc-height` 仍可用）。再锐化可 `--mmdc-scale 3`。

### 用法

```bash
# 写出定稿 .md，并在同目录生成同名 .docx（默认）；-o 须为「案件名_YYYYMMDDHHmmss.md」（见 skills/patent-disclosure/prompts/invention/disclosure_builder.md §7.3 第 5 点）
python tools/mermaid_render.py -i draft.md -o "一种XXX方法及系统_20260408143025.md"

# 指定 .docx 路径（.md 主名仍须含时间戳）
python tools/mermaid_render.py -i draft.md -o out/一种XXX方法及系统_20260408143025.md --docx out/一种XXX方法及系统_20260408143025.docx

# 仅 Markdown，不要 Word
python tools/mermaid_render.py -i draft.md -o "一种XXX方法及系统_20260408143025.md" --no-docx

# 更高清晰度（可选）
python tools/mermaid_render.py -i draft.md -o "…定稿.md" --mmdc-scale 3 --mmdc-width 1600 --mmdc-height 1200

# 指定 mermaid 图片子目录（相对输出 .md）
python tools/mermaid_render.py -i draft.md -o out/一种XXX方法及系统_20260408143025.md --assets-dir figures/mermaid
```

**Word 生成失败**（缺依赖、版式报错等）时：脚本仍以退出码 **0** 结束（Markdown 已成功）；stderr 会打印 **`md_to_docx.py` 的手动命令**，请复制执行。

无可用浏览器时仍写出 Markdown（保留 mermaid 围栏）；补齐 Chrome/Edge 或 Chromium 后可重跑本脚本出 PNG。

### 与交底书约定

- 技能要求定稿**同时**交付 **Markdown + Word**，且 **`-o` 主文件名须含 `_{YYYYMMDDHHmmss}`**（`skills/patent-disclosure/prompts/invention/disclosure_builder.md` §7.3 第 5 点，含首次定稿）；**3.2 系统框图**与 **3.4 流程图**均用 fenced mermaid，**不要** ASCII 文字流程图或框图。
- 交付代理人前：运行 `mermaid_render.py` 一步即可（默认再调 `md_to_docx.py`）；若 Word 失败，按 stderr 提示手动执行 `md_to_docx.py`。
- **判读**：`MERMAID:` / `DOCX: ok=1` 且退出码 0 即为成功；stderr 中文或 PowerShell 红字不是失败。`DOCX: ok=0` 才算 Word 失败。
- 默认**不**预渲染公式 PNG。Word 公式走 OMML；stderr 若有 `omml_text_fallback` / `OMML_FAIL:`，须用户确认后再 `pip install matplotlib` 并以 `--math` / `--math-render` 重出 Word。

---

## math_to_omml.py — LaTeX → 可编辑 Office Math

``latex2mathml`` → MathML → Word ``m:oMath`` / ``m:oMathPara``。不依赖本机 TeX。由 **`md_to_docx.py`** 默认调用。失败则留 LaTeX 原文；stderr 会列出 `omml_text_fallback`。

兼容：单行 ``\[ ... \]`` 与多行块公式同样写入 OMML；``\tag{1}`` 改为式末 ``(1)``。
上标写入 ``m:sup``（不再误塞进 ``m:sub``）。单位与缺字符号在转换前归一：``^{\circ}C/F``、``\degree``、``\AA``、``\ohm``、``\micro``、``\permil``、``\sim`` 等；非汉字公式 run 指定 Cambria Math，避免中文 Word 落到宋体后显示方框。

```bash
pip install latex2mathml   # 已写入根目录 requirements.txt
```

---

## math_render.py — LaTeX 公式 → PNG（可选回退）

将 Markdown 中的 **LaTeX 公式**用 **matplotlib mathtext** 渲染为 PNG；**保留 LaTeX 原文**，图片引用写入 HTML 注释，供 **`md_to_docx.py`** 在 **OMML 失败时**嵌入。

**默认不定稿出公式 PNG**，也不把 matplotlib 写入主 `requirements.txt`。仅当用户确认后：`pip install matplotlib`，再 `md_to_docx.py --math-render` 或 `mermaid_render.py --math`。

**Mermaid 框图**：``mermaid_render.py`` **保留** `` ```mermaid`` 源码，并追加 ``<!-- ![图示 n](mermaid_figures/...) -->``。

**mathtext 兼容**：``\ge``→``\geq`` 等；``\tag{1}`` 转式末 ``(1)``。

**Word 主路径**：默认 **OMML 优先**；无 PNG 时失败留原文。``--no-omml`` 可强制旧行为。

### 依赖（可选）

```bash
pip install matplotlib
```

### 用法

```bash
python tools/math_render.py -i draft.md -o draft_with_math.md
python tools/math_render.py -i draft.md -o out.md --assets-dir math_figures
python tools/md_to_docx.py -i a.md -o a.docx --math-render
python tools/mermaid_render.py -i a.md -o a.md --math
```

---

## md_to_docx.py — Markdown → Word

将交底书 Markdown 转为 `.docx`，**`#`–`######` 映射为 Word 内置「标题 1」–「标题 9」**，正文为宋体 10.5pt，代码块为 Consolas，便于交给代理人或所内用 Word 修订。

**图示**：定稿应用 **`mermaid_render.py`** 将 mermaid 转为 PNG；若个别块生图失败被降级保留围栏，本脚本会将**仍存在的** `` ```mermaid`` 块按**代码块**写入 Word。本脚本不启动浏览器。

### 依赖

```bash
pip install -r requirements.txt
```

依赖为 `python-docx` + `latex2mathml`（见仓库根目录 `requirements.txt`）。缺 `latex2mathml` 时留原文；公式 PNG 须 ``--math-render`` 且已装 matplotlib。

### 用法

```bash
python tools/md_to_docx.py --input path/to/交底书.md --output path/to/交底书.docx
python tools/md_to_docx.py -i a.md -o a.docx --no-omml         # 仅 PNG/原文
python tools/md_to_docx.py -i a.md -o a.docx --math-render    # OMML 失败用 PNG（须 matplotlib）
```

图片 `![](相对路径.png)`：默认相对 **Markdown 文件所在目录**；也可指定根目录：

```bash
python tools/md_to_docx.py -i ./outputs/case/disclosure.md -o ./outputs/case/disclosure.docx --base-dir ./outputs/case
```

**插图**：对 PNG/GIF/JPEG 会读取像素尺寸，在默认 **最大宽 5.5" × 最大高 8.2"** 内**等比缩放**并同时指定 `width`/`height`，避免竖长流程图仅按宽度放大后**高度超出版心**、打印或阅读时像被裁切。可按纸张边距调整，例如：

```bash
python tools/md_to_docx.py -i a.md -o a.docx --image-max-width-inches 6 --image-max-height-inches 9
```

整仓从仓库根调用：`python skills/patent-disclosure/tools/…`。单独拷走本包时本目录即为 `tools/`。

### 支持的 Markdown 子集

| 元素 | 行为 |
|------|------|
| `#`–`######` | Word 标题 1–9 |
| 段落 | 宋体正文，支持 `**粗体**`、`` `行内代码` ``；**相邻非空行（中间无空行）各自成段**，「（1）…（2）…」会分行显示 |
| `-` / `*` 列表 | 项目符号列表 |
| `1.` 列表 | 编号列表；被标题 / 段落 / 表格 / 分隔线等隔开的新一组从 1 重计（避免跨章串号） |
| ` ``` ` 围栏 | 等宽代码块 |
| `\| 表格 \|` | 简单表格（Table Grid）；单元格内 ``\\(...\\)``、``$...$``、``<!-- -->`` 及 ``\\|`` 中的 ``|`` **不会**被当作列分隔符 |
| `> ` | 左缩进引用 |
| `---` 等 | 浅色分隔线 |
| `![](path)` | 嵌入图片（路径需存在；默认宽/高上限内等比缩放；公式图与正文混排） |
| `$` / `\\(...\\)` / `$$` / `\\[...\\]` LaTeX | **优先 OMML（可编辑公式）** → 已有公式 PNG 则嵌图 → 否则 **原文**；``--math-render`` 才预渲染 PNG；``--no-omml`` 跳过 OMML |

**未完整支持**：复杂嵌套列表、HTML 块、**未预渲染的** mermaid 围栏（仍为代码块）、脚注、任务列表等。定稿前请运行 **`mermaid_render.py`**；若仅用外部工具导出 PNG，可直接写 `![](...)`。

### 版式说明（md_to_docx）

- 不同语言 Word 中「标题 1」显示名可能为「Heading 1」或「标题 1」，样式仍为大纲级别标题，可用导航窗格与目录域。
- Markdown 里每组 `1.` 列表（被标题、正文、表格、分隔线等隔开）在 Word 中从 1 重计，避免第一章 1–4 之后第二章变成 5–8。
- 若需所内固定模版（页眉、首页不同），可在本脚本生成后套用单位 `.dotx`，或后续扩展 `python-docx` 打开模版再写入。

---

## iteration_dialog_log.py — 修订对话记录（迭代用）

每轮 **`skills/patent-disclosure/prompts/merger.md` / `correction_handler.md`** 交付后，在**案件目录**追加一条 **`交底书修订对话记录.md`**：含**本地时间与 UTC**、用户说明摘要、本轮交付文件名、合并/纠正摘要摘录。规则见 **`skills/patent-disclosure/prompts/iteration_context.md`**。

**依赖**：仅标准库。

```bash
python tools/iteration_dialog_log.py --case-dir outputs/某案件 --kind merge \
  --user "补充了调度装置资料，合并进第三章" \
  --summary "已扩写 3.4，并更新实施例；未改保护点表述。" \
  --artifacts "一种XXX方法及系统_20260408143025.md,一种XXX方法及系统_20260408143025.docx"
```

- `--kind`：`merge` 或 `correct`。  
- `--log-name`：可选，默认 `交底书修订对话记录.md`；英文环境可改用 `disclosure_revision_log.md`。  
- 无法执行脚本时，由 Agent 按同结构手工追加。

---

## docx_to_md.py — Word → Markdown + 抽取图片

将 **.docx**（Word / WPS 等另存为 docx）转为 **Markdown**，并把文档内嵌图片落到磁盘，便于 **`Read` 与 Step 2 扫描**（与直接读二进制 .docx 相比更稳）。**Step 2** 对扫描树内**每一个** `.docx` 都应先转换再读产出 `.md`，见 `skills/patent-disclosure/prompts/project_scan.md`。

### 依赖

与 `md_to_docx` 共用根目录 `requirements.txt`（`python-docx` + **`mammoth`**）。

```bash
pip install -r requirements.txt
```

### 用法

```bash
python tools/docx_to_md.py --input path/to/设计说明.docx --output outputs/case/design.md
```

- 默认图片目录：`outputs/case/design_media/`，Markdown 内为相对路径 `![](design_media/img_0001.png)`。
- 自定义图片目录：

```bash
python tools/docx_to_md.py -i ./raw/spec.docx -o ./knowledge/spec.md --media-dir ./knowledge/spec_assets
```

转换警告（如部分样式、WMF 图）会输出到 **stderr**，仍可能生成可用 `.md`。

### 局限（mammoth）

- 仅 **`.docx`**（OOXML）；老版 **`.doc`** 不支持。
- **Markdown 输出在 mammoth 侧标记为 deprecated**，复杂排版可能弱于「先导出 HTML 再转 MD」；专利扫描一般足够。若版式崩坏，建议所内 **另存为 PDF 或纯文本** 再扫。
- **WMF/EMF** 等 Windows 图元可能需单独处理（见 [mammoth WMF 配方](https://github.com/mwilliamson/python-mammoth)）。

整仓从仓库根调用：`python skills/patent-disclosure/tools/…`。单独拷走本包时本目录即为 `tools/`。

---

## pptx_to_md.py — PowerPoint → Markdown + 抽取图片

将 **.pptx** / **.ppsx** 按**幻灯片页**导出为 Markdown，并抽取幻灯片中的**嵌入位图**（`PICTURE` 形状），便于 **`Read` 与 Step 2 扫描**。**Step 2** 对扫描树内**每一个** `.pptx` 均应先转换再读 `.md`，见 `skills/patent-disclosure/prompts/project_scan.md`。

### 依赖

根目录 `requirements.txt` 中的 **`python-pptx`**。

```bash
pip install -r requirements.txt
```

### 用法

```bash
python tools/pptx_to_md.py --input path/to/评审材料.pptx --output outputs/case/review.md
```

- 默认图片目录：`outputs/case/review_media/`，文件名形如 `slide03_img0001.png`。
- 自定义图片目录：

```bash
python tools/pptx_to_md.py -i ./raw/deck.pptx -o ./knowledge/deck.md --media-dir ./knowledge/deck_media
```

每页输出二级标题 `## 第 N 页`，其后为该页形状中的**文本与表格**（简化为管道表）及图片引用；若存在**演讲者备注**，以「**备注**」小节附于该页末尾。

### 局限（python-pptx）

- 仅 **`.pptx` / `.ppsx`**（OOXML）；**`.ppt`** 不支持，请先另存。
- **图表、SmartArt、嵌入 OLE** 等若未以普通图片形状存在，**不会**自动栅格化为 PNG；可先在 PowerPoint 中另存为图片或导出 PDF 作补充材料。
- 文本按形状遍历顺序输出，与视觉阅读顺序可能略有差异。

整仓从仓库根调用：`python skills/patent-disclosure/tools/…`。单独拷走本包时本目录即为 `tools/`。

---

## pdf_to_md.py — PDF → Markdown + 抽取图片

将 **.pdf** 按页导出为 Markdown，并抽取页面中的**嵌入位图**，便于 **`Read` 与 Step 2 扫描**。**Step 2** 对用户指定扫描根内的 `.pdf` 应先转换再读产出 `.md`（跳过 `node_modules/` 等），见 `skills/patent-disclosure/prompts/project_scan.md`。

### 依赖（可选）

本目录 **`requirements-pdf.txt`**（**pymupdf**）。不要装进根目录 `requirements.txt`。解读 / 审查答复若已装过 pymupdf，可复用。

```bash
pip install -r skills/patent-disclosure/tools/requirements-pdf.txt
```

单独拷走本包时：`pip install -r tools/requirements-pdf.txt`。

### 用法

```bash
python tools/pdf_to_md.py --input path/to/设计说明.pdf --output outputs/case/design.md
```

- 默认图片目录：`outputs/case/design_media/`，文件名形如 `slide03_img0001.png`。
- 自定义图片目录：

```bash
python tools/pdf_to_md.py -i ./raw/spec.pdf -o ./knowledge/spec.md --media-dir ./knowledge/spec_assets
```

每页输出二级标题 `## 第 N 页`，其后为该页文本层，再跟当页图片的相对路径 `![](…)`，不把图堆到文末。

退出码：`0` 成功（文字过少会在 stderr 警告扫描件）；`2` 文件不存在；`3` 无法打开；`4` 既无文字也无图（不写 `.md`）。

### 局限（pymupdf）

- 只抽文本层与嵌入位图；扫描件几乎没字时请先 OCR，或接受只有图、几乎没正文。
- 部分 PDF 的矢量图层会抽出纯色碎片图，一般可忽略。
- **不要**把本脚本当成「PDF 出图 / 生成附图」。

整仓从仓库根调用：`python skills/patent-disclosure/tools/…`。单独拷走本包时本目录即为 `tools/`。

通俗解读、著录检索、审查答复的脚本在各自技能包，不在本目录。

---

## 扩展其它脚本时

- Word / PPT 转换依赖写在根目录 `requirements.txt`；PDF 转换为可选 `tools/requirements-pdf.txt`（pymupdf）。
- 在 `SKILL.md`「工具与数据来源」表中增加一行调用说明。
- 勿将密钥写入仓库；配置使用环境变量或用户主目录。
