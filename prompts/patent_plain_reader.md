# 专利通俗解读（阅读模式）

## 适用时机

用户意图为**读懂已有专利**（反向阅读），而非撰写交底书。典型触发：

- 专利通俗解读、读专利、看懂专利、反向专利
- 提供专利号 / 专利 PDF / 粘贴权利要求或说明书
- `/patent-read`、`/读专利`

**与主流程关系**：本模式**不**执行 intake → 交底书 Step 1–8。

## 是否依赖 Obsidian？

**强烈推荐配置 Obsidian 库**（`PATENT_READER_OBSIDIAN_VAULT`），才能完整体验索引、Canvas 知识图谱、术语网、关系图配色与公开线索旁注。  
无库时仍可写入 `outputs/patent_reader/`（降级），解读主链路照常，但图谱与旁注体验会弱一截。  
因此**对话一开始、取证之前**必须先探测环境；用户安装与可选社区插件见 **`docs/obsidian-setup-guide.md`**。

## 第 0 步（门禁）：探测 Obsidian 与库路径

**在向用户确认主题之外的实质步骤之前**，先运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/check_obsidian_env.py --json
```

| 结果 | Agent 行为 |
|------|------------|
| `status=ready` 且有 `resolved.vault` | 可 `--auto-accept` 写入持久化；本会话设置 `PATENT_READER_OBSIDIAN_VAULT` 后继续 |
| `needs_user_input=true`（未装 / 多库 / 无库） | **暂停取证**，**强烈建议**用户给出库根路径以获得完整体验（常见：`C:\Users\<用户>\Documents\Obsidian Vault`）；仅当用户明确只要 Markdown / 不要库时，才降级 `outputs/` |
| 用户提供路径后 | 执行 `--set "路径"`（Windows 可选再加 `--setx`），并在后续 Shell 中带上该环境变量 |

```bash
# 用户给出路径后
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/check_obsidian_env.py --set "库路径" --setx

# Windows 当前会话（Agent 后续命令需带上）
# PowerShell: $env:PATENT_READER_OBSIDIAN_VAULT = "库路径"
```

持久化文件：`~/.patent-disclosure-skill/obsidian_vault.txt`（脚本自动读，不单靠环境变量）。

用户明确说「只要 Markdown / 不要 Obsidian」→ 跳过入库增强，写入 `outputs/` 即可。

## Obsidian 增强（L0–L2）

写笔记前 **`Read`**：

- `prompts/obsidian_ofm_companion.md` — Callout / frontmatter / Mermaid 规范
- `references/patent_obsidian_format.md` + `assets/patent_note_template.md`

**标题纪律**：交付笔记的 `##` / `###` / callout 标题只用简洁名称（如「二、连贯叙事」「七、和现有技术的差别」），**禁止**加「（故事线）」「（若能从原文读出）」「（专利内依据）」等给 Agent 的说明。模板里「写作提示 · 勿写入交付稿」仅供撰写时参考，不得原样留在正文。

**实现痕迹禁令（硬性）**：交付笔记与库内索引**禁止**出现脚本/工具文件名（如 `*.py`）、流水线字段路径（如 `context_anchor.ipc_application`）、内部裁图文件名（如 `page_001_xref_01.png`）。附录「来源」只写「离线 IPC 行业词表」等自然语言；附图说明只写「第 N 页」。

有库时，`write_patent_obsidian_note.py` 入库会**自动** `bootstrap_vault`（CSS / Bases / 关系图 Groups）。**勿**再引导用户手动复制 CSS 或单独为「配库」跑初始化；交付对话只引导可选社区插件（见 `obsidian_plugin_guide.md`）。
## 工作流（严格按序）

生成运行 ID：`read-<公开号或slug>-<YYYYMMDDHHmm>`（**RUN**）。

### 第 1 步：取证与结构化

**仅有公开号、无本地全文/PDF 时**（**禁止**每次现写下载脚本）：先跑固化入口，再 extract：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/fetch_patent_pdf.py \
  --pub <公开号> -o tmp/patent_reader/${RUN}
# → tmp/patent_reader/${RUN}/source/<公开号>.pdf
# 源优先级与备选见 references/patent_pdf_sources.yaml
# 排障可加 --save-html；已有直链可 --url …
```

失败时：用 `cnipa_epub_search.py` **核验**公开号/摘要（通常无全文 PDF）→ 请用户自备 PDF，或稍后重试 Google CDN。**勿**臆造 PDF URL。

用户已提供 PDF/全文路径时：**跳过** `fetch_patent_pdf`，直接 extract。

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/extract_patent_text.py \
  -i <全文或 ${RUN}/source/<公开号>.pdf> -o tmp/patent_reader/${RUN} --pub-number <若有>
```

**PDF 附图（有 PDF 时执行；caption+bbox + 质量门）**：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/extract_patent_figures.py \
  -i <patent.pdf> -o tmp/patent_reader/${RUN}/figures
# 人工确认后少丢可用图：追加 --include-review
```

- 读 `FIGURES_MANIFEST`：`decision=insert` 可嵌入；`placeholder` 仅用 `[!figure]` 占位。
- `quality=review` 默认 placeholder；加 `--include-review`（抽取或入库）可按 insert 处理。
- 写笔记第六节：`insert` → `![[images/…]]`；其余 → `[!figure]`。

### 第 1.5 步：技术落地线索 + 可视化草稿

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_context_anchor.py -w tmp/patent_reader/${RUN}

python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_claim_mermaid.py \
  --claim-tree tmp/patent_reader/${RUN}/claim_tree.json \
  --pub-number <公开号> \
  -o tmp/patent_reader/${RUN}/claim_mermaid.mmd
```

- 第三节**树形结构**（◆/├─/└─）由入库脚本按**已校对**的 `claim_tree.json` 渲染；**「本项新增」列优先用你写的 `claim_deltas.json`**（见 1.6），勿再「mermaid + 表」双份主展示；`claim_mermaid.mmd` 仅作可选附件。

### 第 1.55 步：校对 `claim_tree.json`（Agent 主路径 · 父号/独立权）

抽取脚本只会用正则猜独立权与父号，**遇「如权利要求1或2所述」「权1至3」等极易错**。你必须在写 `claim_deltas` / 第三节前完成校对：

1. 打开 `claim_tree.json`，对照权要原文（`raw_sections.jsonl` / PDF / 全文）。
2. 逐项核对并改写节点字段：
   - `is_independent`：是否独立权（真/假）
   - `parent`：从属权的**直接**父号（单值）；独立权必须为 `null`
   - 若节点已有 `parent_candidates`（多引用列表）：从中择一写入 `parent`，并在 `review.notes` 说明选型理由
3. 多引用规则（硬性）：
   - 「权 A 或 B」→ 选**依赖链上更合理的直接限定对象**（通常选独立权，或原文主述的那一项）；**不要**留多个 parent
   - 「权 A 至 C」→ 一般挂到区间内被进一步限定的那一项，拿不准时挂**最小编号且已存在的独立权/父权**
4. 回写同一文件，并增加：

```json
{
  "roots": [1],
  "nodes": [
    {
      "number": 1,
      "is_independent": true,
      "parent": null,
      "text_preview": "…"
    },
    {
      "number": 5,
      "is_independent": false,
      "parent": 1,
      "parent_candidates": [1, 2],
      "text_preview": "如权利要求1或2所述的…"
    }
  ],
  "review": {
    "by": "agent",
    "status": "reviewed",
    "notes": "权5「1或2」挂到独立权1；权12 父号由4改为6",
    "corrections": [
      {"claim": 5, "to_parent": 1, "reason": "或引多项，挂独立权1"}
    ]
  }
}
```

5. **再跑校验**（有 issues 必须修到通过；`multi_parent_candidates` 为警告，校对后可保留 candidates）：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/validate_claim_tree.py \
  -i tmp/patent_reader/${RUN}/claim_tree.json \
  --write \
  --require-review
```

- `--write`：规范化 roots / 悬空父号后再写回。
- 未写 `review.by=agent|human` 时 `--require-review` 会失败——用于防止跳过校对。

### 第 1.6 步：`claim_deltas.json`（Agent 主路径 · 本项新增）

在**已校对**的 `claim_tree.json` 上，为每一项权利要求写一句大白话「相对父权/独立权多了什么」（独立权写骨架要点）。**禁止**照抄「如权利要求…所述」「其特征在于」套话。

写入 `tmp/patent_reader/${RUN}/claim_deltas.json`：

```json
{
  "source": "agent",
  "deltas": [
    {"claim": 1, "delta": "基膜+至少一面涂覆层，涂层含陶瓷与纤维素"},
    {"claim": 2, "delta": "限定纤维素分子量 5万～250万"},
    {"claim": 3, "delta": "非衍生化纤维素经碱尿素溶解后涂布"}
  ]
}
```

- 每句建议 12～40 字；从属权只写**增量**，不要重复父权已有内容。
- 也可写在 `note_plan.json` 的 `claim_deltas` 字段（同结构）；或写入 `claim_tree.json` 各 node 的 `delta` 字段。
- 入库时**优先**用本文件；缺省权号才用脚本启发式从 `text_preview` 截句（效果较差）。

### 第 2 步：公开检索 → 充实 `public_clues.json`（Agent 主路径）

对 `context_anchor.json` → `web_search_queries` 执行 **WebSearch**（或国知局脚本）得到候选后：

1. **先**跑校验+筛选（置信度高→低，**默认最多 3 条**）：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/validate_public_clues.py \
  -i tmp/patent_reader/${RUN}/public_clues.json \
  -o tmp/patent_reader/${RUN}/public_clues.lint.json \
  --write-filtered
```

2. **再由你（Agent）自主规划**打开每条 URL 并写回同文件（**主路径，勿依赖入库脚本爬虫**）：
   - 按站点选型：静态页可用 WebFetch / `mcp_web_fetch`；强反爬或 SPA 用浏览器类工具；打不开则标失败，勿编造正文。
   - 每条补全字段（可复现、可入库）：

```json
[
  {
    "title": "……",
    "url": "https://…",
    "confidence": "中",
    "reason": "与权利要求/实施例的对应关系…",
    "page_title": "页面标题（若可得）",
    "summary": "200～800 字可读摘要，只写页面上能核验的内容",
    "status": "agent_fetched",
    "related_claims": [1, 6],
    "related_features": ["涂覆层含陶瓷和纤维素"],
    "anchor_fits": [
      {
        "kind": "feature",
        "key": "涂覆层含陶瓷和纤维素",
        "fit": "页面写在纸基上涂布纤维素溶液（未出现本案数值区间）"
      },
      {
        "kind": "claim",
        "key": "1",
        "fit": "公开制备流程与权1「涂覆隔膜」同主题，但基材表述为纸基"
      },
      {
        "kind": "term",
        "key": "纤维素",
        "fit": "文中举例棉浆溶解后用于隔膜涂层"
      }
    ],
    "fetch_note": "选用的读取方式；失败原因（可选）"
  }
]
```

- `status`：`agent_fetched`（已读）/ `fetch_failed`（打不开）/ `draft`（仅有链接）。
- `related_claims` / `related_features`：弱匹配建议，**标注为推测**，不得写成说明书证据。
- **`anchor_fits`（硬性 · 大模型主路径）**：你（Agent）**读完该线索页面/摘要全文后**，对照本案权要与特征表，为**真正有对应的**锚点各写一句贴合点（`fit`≤40～80字）。
  - `kind`：`feature` | `claim` | `term`；`key` 必须能对上笔记里的特征名 / 权号 / 术语。
  - **只写页面上能核验的对应**；摘要未点名的数值/尺寸特征不要硬编 `fit`（可省略该条，或入库后由脚本归入「另涉」）。
  - 入库旁注**优先使用** `anchor_fits`；缺省时脚本才用启发式从 `summary` 抽句（效果较差）。
  - 特征表若在写笔记时才定稿：第 4 步入库前应用最终特征名**回填/修订** `anchor_fits` 再写 `public_clues.json`。
- **`summary` 写法（硬性）**：写成 3～8 条要点或两三句连贯短文；**禁止**粘贴导航/页脚/面包屑/整页纯文本；化学式写在同一行（如 `Al2O3/勃姆石涂覆`，勿拆成多行单字）。不要用行首 `>`（会在 Obsidian 变成引用竖线）。
- 无可靠结果时写 `[]`，附录 B「未发现…」。
- **禁止**把推测线索写进一至八主结论。

入库脚本只做**结构化落地与 L1–L4 融合**（`clues/`、导航入口、各节折叠旁注、权/特征点对点、附录 B、Canvas）。**贴合句以 Agent `anchor_fits` 为准**；脚本 HTTP 抓取仅为**降级**：仅当某条缺少 `summary` 且显式传入 `--fetch-clues-fallback` 时才尝试。

### 第 3 步：`note_plan.json`

含 `context_anchor_ref`、`public_clues_ref`、`grounding`；可选内嵌 `claim_deltas`（若未单独写 `claim_deltas.json`）。

### 第 4 步：写解读笔记

遵循 **L0 Callout 模板**（`[!patent-meta]`、`[!grounding]`、`[!warning]-`）。

**说明书段落依据（硬性）**：引用原文段落时写 **`说明书 0002`** 或区间 **`说明书 0002–0004`**（四位编号，用 en-dash `–`）。**禁止**再写裸 `[0002]`（Obsidian 会误染成假链接）。  
入库会生成同目录 `{公开号}_说明书段落.md`（仅含本篇引用到的段；文首含页面预览**使用说明**），并把上述写法改成**单条**可悬停预览 wikilink，例如 `[[…#^p0002|说明书 0002]]`、`[[…#^r0002-0004|说明书 0002–0004]]`。  
正文可写「权2–3」「图1–3」：入库改为 `[[…_权项锚点#^claim-N|权N]]`（旁路笔记）、`[[#图N|图N]]`（附图区标题）。悬停预览需开启「页面预览」并**按住 Ctrl**。

第三节可先留简表或占位；**入库会按 `claim_tree` + `claim_deltas` 重写第三节树形表**。第四节独立权精读仍须你写 callout 与特征表。

若有 `figures/manifest.json`：
- `decision=insert` → 第六节 `![[images/…]]`（入库脚本也会自动补嵌）
- `decision=placeholder` → `[!figure]` 占位，**不要**当正式插图

术语：第五节优先 `[[Research/术语/术语名|术语]]`。入库脚本会合并 `glossary_candidates` **与笔记第五节表/已有 wikilink** 再建 stub、反链与 Canvas（避免 extract 抽不到术语时术语网空白）。

### 第 5 步：lint

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/lint_patent_note.py \
  --note <笔记.md> \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  --claim-tree tmp/patent_reader/${RUN}/claim_tree.json \
  --plan tmp/patent_reader/${RUN}/note_plan.json \
  --context-anchor tmp/patent_reader/${RUN}/context_anchor.json \
  --figures-manifest tmp/patent_reader/${RUN}/figures/manifest.json \
  --output tmp/patent_reader/${RUN}/lint.json
```

- `section3_missing_mermaid_optional`、`insert_figure_not_referenced:*` 为 **warnings**（不阻断）；issues 须修到 passed。
- 有 ≥2 条独立权时第三节应补 mermaid。

### 第 6 步：写入 Obsidian

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/write_patent_obsidian_note.py \
  --content-file <笔记.md> \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  --context-anchor tmp/patent_reader/${RUN}/context_anchor.json \
  --bundle tmp/patent_reader/${RUN}/synthesis_bundle.json \
  --public-clues tmp/patent_reader/${RUN}/public_clues.json \
  --workdir tmp/patent_reader/${RUN} \
  --lint-json tmp/patent_reader/${RUN}/lint.json \
  --output tmp/patent_reader/${RUN}/write_status.json
# workdir 内若有 claim_deltas.json，第三节「本项新增」优先采用（也可 --claim-deltas 显式指定）
# 可选：--include-review（入库时把 review 图当 insert）
# 可选：--strict-figures（要求笔记已嵌入，禁止只靠自动补嵌）
# 官方 PDF 默认拷到笔记目录 source/；不需要时加 --no-copy-source-pdf
```

自动：`bootstrap_vault`（CSS / Bases / 关系图）、frontmatter 标签、`*.canvas` 图谱（叙事/著录/权项/术语/相关专利/**公开线索卡**）、第三节树形表（**本项新增优先 `claim_deltas`**）、`clues/` 落地（用第 2 步 Agent 已写的 summary/`anchor_fits`）、**说明书段落锚点笔记 + 引用 wikilink 改写**、**官方 PDF → `source/`（默认）**、扫描件整页预览、术语反链。线索脚本抓取默认关闭，仅 `--fetch-clues-fallback`。无 vault 时仍写 `outputs/`。入库可加 `--scan-pages`。

可选单独生成 Canvas：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_patent_canvas.py \
  --note-rel Research/Patents/<领域>/<公开号>/<文件>.md \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  -o Research/Patents/<领域>/<公开号>/<公开号>_图谱.canvas
```

### 第 7 步：交付

1. 笔记路径、Canvas 路径、索引页路径  
2. 一句话结论、证据范围、应用场景要点  
3. **`Read`** `prompts/obsidian_plugin_guide.md` → 向用户出示**插件安装引导**（含社区插件 URL）

### 第 8 步（交付后常问 · 推荐）：库内专利关联

交付第 7 步后，**只要库内已有 ≥2 篇解读笔记，就必须用一句话反问**（勿静默跳过）：

> 库里已有其它专利解读，要不要做一次「专利关联」？会按同申请人 / IPC / 共术语等规则连边，并生成全局 `Research/Patents/_专利关联.canvas`（不构成法律意见）。

| 用户态度 | Agent 行为 |
|----------|------------|
| 明确同意 / 「要关联」 / 「好」 | 执行下方命令；可先 `--dry-run` 预览边再写入 |
| 拒绝 / 「不用」 | **跳过**，结束本轮 |
| 「先看看有哪些边」 | 仅 `--dry-run`，再问是否写入 |
| 库内不足 2 篇 | 可省略反问，或说明「再解读一篇后可做关联」 |

```bash
# 预览
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> --dry-run \
  -o tmp/patent_reader/${RUN}/patent_links.preview.json

# 写入（双向回写 related_pubs + 相关专利节 + 单篇图谱 + 全局 _专利关联.canvas）
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> \
  -o tmp/patent_reader/${RUN}/patent_links.json
```

**可选增强（模型边）**：若 dry-run 后仍有「疑似相关但规则分不够」的对，Agent 可阅读两篇笔记后写 `model_links.json`：

```json
[
  {
    "pub_a": "CNxxx",
    "pub_b": "CNyyy",
    "relation": "improvement",
    "score": 0.75,
    "rationale": "独立权均含…；B 增加…"
  }
]
```

再执行：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> \
  --model-scores tmp/patent_reader/${RUN}/model_links.json \
  -o tmp/patent_reader/${RUN}/patent_links.json
```

**约束**：无 vault 时跳过本步；关联仅为辅助导航，须在相关专利节保留免责提示；**禁止**把关联写成侵权/无效结论。

## 与国知局查新的一致性

公开号、摘要须先检索核验；**禁止虚构**链接。
