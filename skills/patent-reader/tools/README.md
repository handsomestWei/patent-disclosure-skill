# 专利通俗解读工具（`skills/patent-reader/tools/`）

阅读模式专用脚本。过 WAF 用本包 `tools/browser.py`；外观视图用本包 `tools/crawl/`（一词一页，不是著录检索引擎）。

## 目录结构

```
skills/patent-reader/tools/
├── shared/     # 共享配置与路径
├── extract/    # PDF / 全文 / 附图取证
├── analyze/    # 权要树、线索包、校验与 lint
├── vault/      # Obsidian 入库、Canvas、关联与库环境
└── google_patents/  # Google Patents 详情页 / 检索（与 patent-search 同名目录逐字一致）
```

| 子目录 | 文件 | 作用 |
|--------|------|------|
| `shared/` | `common.py` | 共享兼容入口（再导出下列模块）；外部一律从这里导入 |
| | `paths.py` / `obsidian_env.py` / `claims.py` / `rules.py` / `biblio.py` | 包根与 slug / Obsidian 库探测与运行配置 / 独立从属判断与权要树 / 领域与 IPC 规则 / 全文著录抽取 |
| | `text_vocab.py` | 读取 `references/text_vocab.yaml`（著录字段标签、从属句式、独立权开头、机构提示词） |
| `extract/` | `fetch_patent_pdf.py` | **按公开号下载全文 PDF**（源表 `references/patent_pdf_sources.yaml`；状态含自动判别的 `patent_type`） |
| | `fetch_gp_fulltext.py` | **海外公开号取全文**（US / EP / WO / JP / KR…）：一次 Google Patents 详情页请求，直接写出权要树、说明书段落等中间文件并下载 PDF；机翻文献另存原文；限流退出码 4，不重试 |
| | `fetch_design_views.py` | **外观设计视图取证**（国知局会话 + 详情页 `/imgs` 序号探测；无 PDF CDN 时用） |
| | `extract_patent_text.py` | 全文/PDF 取证 |
| | `figure_extract.py` | caption+bbox 裁切 + 质量门 |
| | `extract_patent_figures.py` | PDF 附图 CLI → manifest |
| `analyze/` | `build_context_anchor.py` | 技术落地线索包；海外文献只整理事实（`search_plan`），检索词由 Agent 推断 |
| | `build_claim_mermaid.py` | 权利要求 mermaid |
| | `validate_claim_tree.py` | 权项树校验/规范化 |
| | `claim_features.py` / `validate_claim_features.py` | 独权特征行（对照表左列） |
| | `validate_public_clues.py` | 附录 B 线索校验 + 置信度筛选 |
| | `lint_patent_note.py` | 笔记结构校验 |
| `vault/` | `obsidian.py` | 兼容入口：再导出下列拆分模块的公开符号 |
| | `obsidian_paths.py` | 模板 / CSS 路径 |
| | `obsidian_frontmatter.py` | YAML 解析与入库字段 |
| | `obsidian_claims.py` | 权利要求树、Mermaid、第三节表 |
| | `obsidian_glossary.py` | 术语 stub、反链、相关笔记扫描 |
| | `obsidian_canvas.py` | JSON Canvas 与图谱导航 |
| | `obsidian_bootstrap.py` | 库初始化、索引、关系图配色 |
| | `schema_vault.py` | Structure/Appearance Schema 写入笔记/Canvas |
| | `clue_vault.py` | 线索兼容入口（再导出 `clues/` 下各模块）；外部一律从这里导入 |
| | `clues/model.py` / `summary.py` / `matching.py` / `annotate.py` / `render.py` | 线索数据与筛选 / 摘要清洗与降级抓取 / 权项特征弱匹配 / 笔记旁注注入 / `clues/` 笔记·附录 B·Canvas |
| | `clues/vocab.py` | 读取 `references/clue_vocab.yaml`（置信度、噪音词、停用词、同义词、特征提示等词表） |
| | `desc_paragraphs.py` | 说明书 `[000N]` 解析与悬停 wikilink |
| | `note_cites.py` | 笔记引用增强 |
| | `patent_link.py` | 库内专利关联规则 |
| | `write_patent_obsidian_note.py` | 入库主入口 |
| | `build_patent_canvas.py` | JSON Canvas 图谱 |
| | `link_patent_notes.py` | 交付后库内关联与全局 Canvas |
| | `materialize_public_clues.py` | 对已有解读补跑线索落地 |
| | `check_obsidian_env.py` | 探测/持久化库路径 |
| | `setup_obsidian_vault.py` | 库初始化（开发/排障） |
| `google_patents/` | `query.py` / `client.py` / `results.py` / `detail.py` / `api.py` | 查询串构造、单次请求与限流识别、检索结果与详情页解析；改动须同步 `skills/patent-search/tools/google_patents/` |
| 根 | `requirements.txt` | 依赖：`PyYAML`（读 `references/*.yaml`）、`pymupdf`（PDF） |

库内模板：`assets/obsidian/`（CSS、`*.base.yaml` 源稿、索引页；拷库时写成 `.base`）。

流程见 **`skills/patent-reader/prompts/patent_plain_reader.md`**。

## 快速开始

```bash
pip install -r skills/patent-reader/tools/requirements.txt

# 先探测库路径（强烈推荐已装 Obsidian 并开库）
python skills/patent-reader/tools/vault/check_obsidian_env.py --auto-accept

# 仅公开号：先下载 PDF（Google Patents 页 → CDN；见 patent_pdf_sources.yaml）
python skills/patent-reader/tools/extract/fetch_patent_pdf.py \
  --pub CN119961390A -o outputs/patent_reader/demo

python skills/patent-reader/tools/extract/extract_patent_text.py \
  -i outputs/patent_reader/demo/source/CN119961390A.pdf \
  -o outputs/patent_reader/demo --pub-number CN119961390A

# 海外公开号：一次请求取结构化全文（替代 fetch_patent_pdf + extract_patent_text）
python skills/patent-reader/tools/extract/fetch_gp_fulltext.py \
  --pub US11450918B2 -o outputs/patent_reader/demo_us

# 外观设计（CN…S）：常无 PDF CDN → 用国知局视图取证
pip install -r skills/patent-reader/tools/crawl/requirements-cnipa.txt
python tools/browser.py --probe
# 无 Chrome/Edge 时才：python -m playwright install chromium
python skills/patent-reader/tools/extract/fetch_design_views.py \
  --pub CN309939145S -o outputs/patent_reader/demo_design
# → figures/images/view_001.jpg … + figures/manifest.json + source/*_design_brief.json
```

入库用 `vault/write_patent_obsidian_note.py`（内含 bootstrap）；勿再单独要求用户跑 `setup_obsidian_vault.py`。

## 环境变量

| 变量 | 说明 |
|------|------|
| `PATENT_READER_OBSIDIAN_VAULT` | Obsidian 库根（兼容 `PATENT_DISCLOSURE_OBSIDIAN_VAULT`）；也可用 `check_obsidian_env.py --set` 持久化到 `~/.patent-disclosure-skill/obsidian_vault.txt` |
| `PATENT_READER_PAPERS_DIR` | 库内目录，默认 `Research/Patents` |
| `PATENT_READER_OUTPUT_DIR` | 解读 RUN 目录（默认 `outputs/patent_reader`）；无库时笔记也写这里 |
| `PATENT_READER_GLOSSARY_DIR` | 术语目录，默认 `Research/术语` |

交付后可选社区插件引导：`skills/patent-reader/prompts/obsidian_plugin_guide.md`。  
关系图配色与插件说明：`docs/obsidian-setup-guide.md`（原生 Groups，无需插件）。
