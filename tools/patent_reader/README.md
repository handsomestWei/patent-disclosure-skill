# 专利通俗解读工具（`tools/patent_reader/`）

阅读模式专用脚本，与交底书主流程工具（`mermaid_render.py`、`cnipa_*.py` 等）分离。

## 目录结构

| 文件 | 作用 |
|------|------|
| `common.py` | 领域路由、IPC 提示、路径与环境变量 |
| `obsidian.py` | Frontmatter、Canvas、库 bootstrap、Mermaid |
| `fetch_patent_pdf.py` | **按公开号下载全文 PDF**（固化入口；源表 `references/patent_pdf_sources.yaml`） |
| `extract_patent_text.py` | 全文/PDF 取证 |
| `figure_extract.py` | 专利 caption+bbox 裁切 + 质量门（被 extract 调用） |
| `extract_patent_figures.py` | PDF 附图 CLI → manifest（insert/placeholder） |
| `build_context_anchor.py` | 技术落地线索包 |
| `build_claim_mermaid.py` | 权利要求 mermaid |
| `validate_claim_tree.py` | 权项树校验/规范化；Agent 校对后 `--require-review` |
| `build_patent_canvas.py` | JSON Canvas 图谱 |
| `lint_patent_note.py` | 笔记结构校验 |
| `validate_public_clues.py` | 附录 B 线索校验 + 置信度筛选（默认最多 3 条） |
| `clue_vault.py` | `clues/` 落地、附录/旁注/Canvas；脚本 HTTP 仅作降级 |
| `materialize_public_clues.py` | 对已有解读补跑线索落地；`--fetch-fallback` 才脚本抓取 |
| `check_obsidian_env.py` | 对话开始前探测库路径（**强烈推荐**有库；可降级 outputs） |
| `link_patent_notes.py` | 交付后常问：库内专利关联（规则+模型分）与全局 `_专利关联.canvas` |
| `desc_paragraphs.py` | 说明书 `[000N]` 解析、`*_说明书段落.md` 锚点、引用改写为可悬停 wikilink |
| `write_patent_obsidian_note.py` | 入库 + 自动 bootstrap；第三节「本项新增」优先 `claim_deltas.json`（Agent）；默认拷贝官方 PDF 到 `source/`（`--no-copy-source-pdf` 关闭） |
| `setup_obsidian_vault.py` | 与入库等价的库初始化（开发/排障用；用户流程勿单独强调） |
| `requirements.txt` | 可选依赖（`pymupdf`） |

库内模板：`assets/obsidian/`（CSS、Bases、索引页）。

流程见 **`prompts/patent_plain_reader.md`**。

## 快速开始

```bash
pip install -r tools/patent_reader/requirements.txt

# 先探测库路径（强烈推荐已装 Obsidian 并开库）
python tools/patent_reader/check_obsidian_env.py --auto-accept

# 仅公开号：先下载 PDF（Google Patents 页 → CDN；见 patent_pdf_sources.yaml）
python tools/patent_reader/fetch_patent_pdf.py \
  --pub CN119961390A -o tmp/patent_reader/demo

python tools/patent_reader/extract_patent_text.py \
  -i tmp/patent_reader/demo/source/CN119961390A.pdf \
  -o tmp/patent_reader/demo --pub-number CN119961390A
# 或本地样例文本：
# python tools/patent_reader/extract_patent_text.py \
#   -i tests/fixtures/patent_reader_sample.txt \
#   -o tmp/patent_reader/demo --pub-number CN999999999B
```

入库用 `write_patent_obsidian_note.py`（内含 bootstrap）；勿再单独要求用户跑 `setup_obsidian_vault.py`。

## 环境变量

| 变量 | 说明 |
|------|------|
| `PATENT_READER_OBSIDIAN_VAULT` | Obsidian 库根（兼容 `PATENT_DISCLOSURE_OBSIDIAN_VAULT`）；也可用 `check_obsidian_env.py --set` 持久化到 `~/.patent-disclosure-skill/obsidian_vault.txt` |
| `PATENT_READER_PAPERS_DIR` | 库内目录，默认 `Research/Patents` |
| `PATENT_READER_OUTPUT_DIR` | 未配置库时输出目录 |
| `PATENT_READER_GLOSSARY_DIR` | 术语目录，默认 `Research/术语` |

交付后可选社区插件引导：`prompts/obsidian_plugin_guide.md`。  
关系图配色与插件说明：`docs/obsidian-setup-guide.md`（原生 Groups，无需插件）。
