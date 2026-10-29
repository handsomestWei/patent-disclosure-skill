# 专利通俗解读工具（`skills/patent-reader/tools/`）

阅读模式专用脚本。过 WAF 用本包 `tools/browser.py`；外观视图用本包 `tools/crawl/`（一词一页，不是著录检索引擎）。

## 目录结构

```
skills/patent-reader/tools/
├── shared/     # 共享配置与路径
├── extract/    # PDF / 全文 / 附图取证
├── analyze/    # 权要树、线索包、校验与 lint
└── vault/      # Obsidian 入库、Canvas、关联与库环境
```

| 子目录 | 文件 | 作用 |
|--------|------|------|
| `shared/` | `common.py` | 领域路由、IPC 提示、路径与环境变量 |
| `extract/` | `fetch_patent_pdf.py` | **按公开号下载全文 PDF**（源表 `references/patent_pdf_sources.yaml`；状态含自动判别的 `patent_type`） |
| | `fetch_design_views.py` | **外观设计视图取证**（国知局会话 + 详情页 `/imgs` 序号探测；无 PDF CDN 时用） |
| | `extract_patent_text.py` | 全文/PDF 取证 |
| | `figure_extract.py` | caption+bbox 裁切 + 质量门 |
| | `extract_patent_figures.py` | PDF 附图 CLI → manifest |
| `analyze/` | `build_context_anchor.py` | 技术落地线索包 |
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
| | `clue_vault.py` | `clues/` 落地、附录/旁注/Canvas |
| | `desc_paragraphs.py` | 说明书 `[000N]` 解析与悬停 wikilink |
| | `note_cites.py` | 笔记引用增强 |
| | `patent_link.py` | 库内专利关联规则 |
| | `write_patent_obsidian_note.py` | 入库主入口 |
| | `build_patent_canvas.py` | JSON Canvas 图谱 |
| | `link_patent_notes.py` | 交付后库内关联与全局 Canvas |
| | `materialize_public_clues.py` | 对已有解读补跑线索落地 |
| | `check_obsidian_env.py` | 探测/持久化库路径 |
| | `setup_obsidian_vault.py` | 库初始化（开发/排障） |
| 根 | `requirements.txt` | 可选依赖（`pymupdf`） |

库内模板：`assets/obsidian/`（CSS、`*.base.yaml` 源稿、索引页；拷库时写成 `.base`）。

流程见 **`skills/patent-reader/prompts/patent_plain_reader.md`**。

## 快速开始

```bash
pip install -r skills/patent-reader/tools/requirements.txt

# 先探测库路径（强烈推荐已装 Obsidian 并开库）
python skills/patent-reader/tools/vault/check_obsidian_env.py --auto-accept

# 仅公开号：先下载 PDF（二选一：computer-use MCP 桌面控制优先；或技能脚本走 Google Patents 页 → CDN，见 patent_pdf_sources.yaml）
#   · MCP 逐篇操作序列与踩坑（输入法/清空/间隔/点击频次/出错查验/求助）见 references/gui_download_cnipa.md（全部走 windows-computer-use MCP）
python skills/patent-reader/tools/extract/fetch_patent_pdf.py \
  --pub CN119961390A -o outputs/patent_reader/demo

python skills/patent-reader/tools/extract/extract_patent_text.py \
  -i outputs/patent_reader/demo/source/CN119961390A.pdf \
  -o outputs/patent_reader/demo --pub-number CN119961390A

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
