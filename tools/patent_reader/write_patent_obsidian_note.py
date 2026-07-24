#!/usr/bin/env python3
"""
将已通过 lint 的专利解读笔记写入 Obsidian 库或 outputs/patent_reader/，
并：初始化库资源、术语 stub、增强 frontmatter、生成 Canvas、附图闸门、更新索引。

用法：
  python tools/patent_reader/write_patent_obsidian_note.py --content-file note.md \\
      --manifest source_manifest.json --lint-json lint.json \\
      [--context-anchor context_anchor.json] [--bundle synthesis_bundle.json] \\
      [--public-clues public_clues.json] [--claim-deltas claim_deltas.json] \\
      [--workdir tmp/patent_reader/RUN] [--strict-figures] [--include-review]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from common import (
        normalize_claim_tree,
        optional_path,
        resolve_domain,
        runtime_config,
        slugify_pub,
    )
    from obsidian import (
        bootstrap_vault,
        build_canvas,
        claim_deltas_from_tree,
        enrich_note_frontmatter,
        ensure_canvas_nav,
        ensure_domain_index,
        harvest_claim_summaries_from_note,
        load_claim_deltas,
        merge_claim_summaries,
        render_claim_tree_markdown,
        scan_vault_related,
        try_obsidian_cli_property,
        upsert_claim_tree_section,
        upsert_index_entry,
    )
except ImportError:  # python -m 包内导入
    from tools.patent_reader.common import (
        normalize_claim_tree,
        optional_path,
        resolve_domain,
        runtime_config,
        slugify_pub,
    )
    from tools.patent_reader.obsidian import (
        bootstrap_vault,
        build_canvas,
        claim_deltas_from_tree,
        enrich_note_frontmatter,
        ensure_canvas_nav,
        ensure_domain_index,
        harvest_claim_summaries_from_note,
        load_claim_deltas,
        merge_claim_summaries,
        render_claim_tree_markdown,
        scan_vault_related,
        try_obsidian_cli_property,
        upsert_claim_tree_section,
        upsert_index_entry,
    )

NAV_SECTION_RE = re.compile(r"^##\s*Obsidian\s*导航\s*$", re.M | re.I)
SECTION5_RE = re.compile(
    r"(^##\s*五、专利内术语表[\s\S]*?)(?=^##\s*六、|\Z)",
    re.M,
)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
GLOSSARY_LINK_RE = re.compile(
    r"\[\[(?:Research/)?术语/([^\]|#]+)(?:\|([^\]]+))?\]\]"
)

# 用户可见标题：去掉给 Agent 的说明性括号（幂等）
_USER_HEADING_CLEANUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(##\s*二、连贯叙事)（故事线）\s*$", re.M), r"\1"),
    (re.compile(r"^(###\s*结构图)（可选\s*mermaid）\s*$", re.M | re.I), r"\1"),
    (re.compile(r"^(##\s*七、和现有技术的差别)（若能从原文读出）\s*$", re.M), r"\1"),
    (re.compile(r"^(##\s*九、技术应用场景)（专利内依据）\s*$", re.M), r"\1"),
    (re.compile(r"^(###\s*A\.\s*IPC\s*行业坐标)（离线词表）\s*$", re.M), r"\1"),
    (re.compile(r"^(###\s*B\.\s*公开检索线索)（推测）\s*$", re.M), r"\1"),
    (re.compile(r"^(##\s*相关专利)（自动关联）\s*$", re.M), r"\1"),
    (re.compile(r"^(###\s*附图)（扫描件整页预览）\s*$", re.M), r"\1"),
    (re.compile(r"^(###\s*附图嵌入)（自动）\s*$", re.M), "### 附图"),
    (
        re.compile(
            r"^(>\s*\[!grounding\]\s*应用场景)（专利内依据\s*[·•]\s*高置信）\s*$",
            re.M,
        ),
        r"\1",
    ),
    (
        re.compile(
            r"^(>\s*\[!warning\]-?\s*公开检索线索)（推测\s*[·•]\s*默认折叠）\s*$",
            re.M,
        ),
        r"\1",
    ),
    (re.compile(r"(\[\[(?:[^\]]+_图谱\.canvas)\|[^\]]+\]\])（入库后生成）"), r"\1"),
    (re.compile(r"(\[\[(?:[^\]]+_图谱)\|[^\]]+\]\])（入库后生成）"), r"\1"),
    (re.compile(r"^\|\s*特征\s*\|\s*说明书位置\s*\|\s*附图（若有）\s*\|", re.M), "| 特征 | 说明书位置 | 附图 |"),
    (re.compile(r"\*\*效果（专利自述）\*\*"), "**效果**"),
]


def sanitize_user_facing_titles(content: str) -> str:
    """去掉章节/callout 标题上给 Agent 看的说明性括号，避免交付笔记读起来像说明书。"""
    for pat, repl in _USER_HEADING_CLEANUPS:
        content = pat.sub(repl, content)
    return sanitize_internal_tool_leakage(content)


# 交付笔记/索引中不得出现的内部实现痕迹（脚本名、流水线字段、裁图文件名等）
_INTERNAL_LEAK_CLEANUPS: list[tuple[re.Pattern[str], str]] = [
    # 附录来源：模型常把写作提示里的字段路径抄进正文
    (
        re.compile(
            r"`?context_anchor\.ipc_application`?\s*（离线词表）\s*"
            r"[＋+]\s*(Google Patents[^\n]*)",
        ),
        r"离线 IPC 行业词表；\1",
    ),
    (
        re.compile(r"`?context_anchor\.ipc_application`?\s*（离线词表）"),
        "离线 IPC 行业词表",
    ),
    (
        re.compile(r"`?context_anchor\.[a-zA-Z0-9_.]+`?"),
        "离线行业词表",
    ),
    # 附图说明：只保留页码，不暴露 page_xxx_xref_yy.png
    (
        re.compile(
            r"(\*(?:第\s*\d+\s*页|预览\s*\d+))\s*[·•]\s*`[^`]*\.(?:png|jpe?g|webp|gif)`\*",
            re.I,
        ),
        r"\1*",
    ),
    (
        re.compile(
            r"(\*(?:第\s*\d+\s*页|预览\s*\d+))\s*[·•]\s*[`']?page_\d+_xref_\d+\.(?:png|jpe?g)[`']?\*",
            re.I,
        ),
        r"\1*",
    ),
    # 索引/导航中的脚本名 → 用户可读说法
    (
        re.compile(
            r"由\s*`write_patent_obsidian_note\.py`\s*/\s*`setup_obsidian_vault\.py`\s*维护。"
        ),
        "入库后自动维护。",
    ),
    (
        re.compile(r"由\s*`write_patent_obsidian_note\.py`\s*维护。?"),
        "入库后自动维护。",
    ),
    (
        re.compile(r"（交付后运行\s*`link_patent_notes\.py`\s*生成）"),
        "（交付后可生成专利关联）",
    ),
    (
        re.compile(
            r"若仍为灰色，执行\s*`setup_obsidian_vault\.py`\s*后\s*"
            r"\*\*Ctrl/Cmd\+R\*\*\s*重载库。"
        ),
        "若仍为灰色，请重载库（Ctrl/Cmd+R）。",
    ),
    (
        re.compile(r"（脚本追加 wikilink 条目。）"),
        "（入库时自动追加条目。）",
    ),
    # 残留裸脚本名（兜底，不误伤扩展名说明以外的句子）
    (
        re.compile(
            r"`(?:write_patent_obsidian_note|setup_obsidian_vault|link_patent_notes|"
            r"build_patent_canvas|build_context_anchor|extract_patent_text|"
            r"extract_patent_figures|check_obsidian_env)\.py`"
        ),
        "入库工具",
    ),
]


def sanitize_internal_tool_leakage(content: str) -> str:
    """去掉交付正文中的脚本名、流水线字段名、内部文件名等实现痕迹。"""
    for pat, repl in _INTERNAL_LEAK_CLEANUPS:
        content = pat.sub(repl, content)
    return content


def _strip_cell(cell: str) -> str:
    s = cell.strip()
    m = WIKILINK_RE.fullmatch(s)
    if m:
        return (m.group(2) or m.group(1).rsplit("/", 1)[-1]).strip()
    # 单元格内嵌 wikilink（非整格）时取显示名
    m2 = WIKILINK_RE.search(s)
    if m2 and s.startswith("[[" ):
        return (m2.group(2) or m2.group(1).rsplit("/", 1)[-1]).strip()
    return s


def _split_md_table_row(line: str) -> list[str]:
    """按 | 拆表行，但忽略 wikilink [[...|...]] 内的竖线。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    cols: list[str] = []
    buf: list[str] = []
    i = 0
    in_link = False
    while i < len(s):
        if s.startswith("[[", i):
            in_link = True
            buf.append("[[")
            i += 2
            continue
        if in_link and s.startswith("]]", i):
            in_link = False
            buf.append("]]")
            i += 2
            continue
        ch = s[i]
        if ch == "|" and not in_link:
            cols.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cols.append("".join(buf).strip())
    return cols


def harvest_glossary_from_note(content: str) -> list[dict]:
    """从第五节术语表与已有术语 wikilink 收获候选（补 extract 为空的情况）。"""
    m = SECTION5_RE.search(content)
    if not m:
        return []
    sec = m.group(1)
    by_term: dict[str, dict] = {}

    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|\s*[-:\s|]+$", line):
            continue
        cols = _split_md_table_row(line)
        if len(cols) < 2:
            continue
        term = _strip_cell(cols[0])
        if not term or term == "术语" or term.startswith("_") or "[[" in term:
            continue
        defn = _strip_cell(cols[1]) if len(cols) > 1 else ""
        by_term[term] = {"term": term, "definition": defn}

    for gm in GLOSSARY_LINK_RE.finditer(sec):
        path_term = gm.group(1).strip().rstrip("\\")
        display = (gm.group(2) or path_term).strip()
        term = display or path_term
        if not term or term.startswith("_") or term == "术语索引":
            continue
        by_term.setdefault(term, {"term": term, "definition": ""})

    return list(by_term.values())


def merge_glossary_candidates(
    bundle_glossary: list, note_glossary: list[dict]
) -> list[dict]:
    """合并 bundle 与笔记收获的术语；同名时保留非空 definition。"""
    by_term: dict[str, dict] = {}
    for item in list(bundle_glossary or []) + list(note_glossary or []):
        if isinstance(item, dict):
            term = str(item.get("term") or "").strip()
            defn = str(item.get("definition") or "").strip()
        else:
            term = str(item).strip()
            defn = ""
        if not term:
            continue
        prev = by_term.get(term)
        if not prev:
            by_term[term] = {"term": term, "definition": defn}
        elif defn and not prev.get("definition"):
            prev["definition"] = defn
    return list(by_term.values())


def _note_link_name(dest: Path, vault: Path) -> str:
    rel = dest.relative_to(vault)
    return str(rel.with_suffix("")).replace("\\", "/")


def resolve_source_pdf(
    manifest: dict, workdir: Path | None
) -> Path | None:
    """定位官方 PDF：manifest.source_path → workdir/source/*.{pdf,PDF}。"""
    candidates: list[Path] = []
    sp = str(manifest.get("source_path") or "").strip()
    if sp:
        candidates.append(Path(sp))
    if workdir is not None:
        src_dir = workdir / "source"
        if src_dir.is_dir():
            candidates.extend(sorted(src_dir.glob("*.pdf")))
            candidates.extend(sorted(src_dir.glob("*.PDF")))
        candidates.extend(sorted(workdir.glob("*.pdf")))
    seen: set[str] = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except OSError:
            continue
        key = str(rp).lower()
        if key in seen:
            continue
        seen.add(key)
        if rp.is_file() and rp.suffix.lower() == ".pdf":
            return rp
    return None


def copy_source_pdf_to_note_dir(
    pdf: Path, note_dir: Path, pub: str
) -> Path:
    """复制到 note_dir/source/{pub}.pdf（幂等覆盖）。"""
    dest_dir = note_dir / "source"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slugify_pub(pub)}.pdf"
    shutil.copy2(pdf, dest)
    return dest


def ensure_source_pdf_nav(content: str, *, pub: str) -> str:
    """导航中补「官方 PDF」wikilink（同目录 source/）。"""
    link = f"[[source/{slugify_pub(pub)}.pdf|官方 PDF]]"
    if link in content or f"source/{slugify_pub(pub)}.pdf" in content:
        return content
    m = re.search(
        r"(##\s*Obsidian 导航\s*\n)([\s\S]*?)(?=\n##\s|\n> \[!|\Z)", content
    )
    if not m:
        return content
    block = m.group(2)
    lines = block.rstrip().splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if any(
            k in line
            for k in ("权项锚点", "说明书段落", "图谱", "canvas")
        ):
            insert_at = i + 1
    if insert_at == 0:
        insert_at = len(lines)
    lines.insert(insert_at, f"- {link}")
    new_block = "\n".join(lines) + "\n"
    return content[: m.start(2)] + new_block + content[m.end(2) :]


def _ensure_nav_section(content: str, nav_lines: list[str]) -> str:
    """合并/更新 Obsidian 导航节（已有模板导航时也会补全真实链接）。"""
    if not nav_lines:
        return content
    existing = NAV_SECTION_RE.search(content)
    if existing:
        start = existing.start()
        rest = content[existing.end() :]
        end_m = re.search(r"^##\s+", rest, re.M)
        end = existing.end() + end_m.start() if end_m else len(content)
        old_section = content[start:end]
        lines_out = ["## Obsidian 导航", ""]
        seen: set[str] = set()
        for ln in nav_lines:
            item = ln.strip()
            if not item or item in seen:
                continue
            lines_out.append(f"- {item}")
            seen.add(item)
        for m in re.finditer(r"^-\s+(.+)$", old_section, re.M):
            item = m.group(1).strip()
            if item and item not in seen:
                lines_out.append(f"- {item}")
                seen.add(item)
        block = "\n".join(lines_out) + "\n\n"
        return content[:start] + block + content[end:]

    block = "## Obsidian 导航\n\n" + "\n".join(f"- {ln}" for ln in nav_lines) + "\n\n"
    m = re.search(r"^##\s*一、", content, re.M)
    if m:
        return content[: m.start()] + block + content[m.start() :]
    m2 = re.search(r"^#\s+", content, re.M)
    if m2:
        end = content.find("\n", m2.end())
        insert = end + 1 if end != -1 else m2.end()
        return content[:insert] + "\n" + block + content[insert:]
    return block + content


def _load_figures_manifest(workdir: Path) -> dict:
    manifest = workdir / "figures" / "manifest.json"
    if not manifest.is_file():
        return {"figures": []}
    return json.loads(manifest.read_text(encoding="utf-8"))


def _figure_allowed(fig: dict, include_review: bool) -> bool:
    decision = fig.get("decision")
    if decision == "insert":
        return True
    if include_review:
        status = (fig.get("quality_signals") or {}).get("status")
        if decision == "placeholder" and status == "review":
            return True
        if decision == "review":
            return True
    return False


def _copy_figures_gated(
    workdir: Path,
    images_dir: Path,
    *,
    include_review: bool = False,
) -> tuple[list[dict], list[str]]:
    """复制 insert（及可选 review）附图；返回 (figs, copied_rel_paths)。"""
    data = _load_figures_manifest(workdir)
    images_dir.mkdir(parents=True, exist_ok=True)
    insert_figs: list[dict] = []
    copied: list[str] = []
    for fig in data.get("figures") or []:
        if not _figure_allowed(fig, include_review):
            continue
        src = workdir / "figures" / fig.get("filename", "")
        if not src.is_file():
            continue
        dest = images_dir / src.name
        shutil.copy2(src, dest)
        fig = dict(fig)
        fig["decision"] = "insert"
        insert_figs.append(fig)
        copied.append(f"images/{src.name}")
    return insert_figs, copied


def _note_references_image(note: str, relative: str) -> bool:
    name = Path(relative).name
    if name in note or relative in note:
        return True
    return bool(re.search(rf"!\[\[(?:[^\]]*/)?{re.escape(name)}(?:\|[^\]]*)?\]\]", note))


def _is_scan_page_fig(fig: dict) -> bool:
    lvl = str(fig.get("extraction_level") or "")
    fn = str(fig.get("filename") or "")
    return lvl == "page" or fn.startswith("page_") or "xref" in fn


def _copy_scan_pages(
    workdir: Path,
    images_dir: Path,
    *,
    limit: int = 8,
) -> tuple[list[dict], list[str]]:
    """扫描件模式：复制 figures 下整页 PNG（忽略 insert 闸门）。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    data = _load_figures_manifest(workdir)
    figs_src = list(data.get("figures") or [])
    if not figs_src:
        for src in sorted((workdir / "figures").glob("page_*.png"))[:limit]:
            figs_src.append(
                {
                    "filename": src.name,
                    "extraction_level": "page",
                    "decision": "placeholder",
                    "page": None,
                }
            )
    insert_figs: list[dict] = []
    copied: list[str] = []
    for fig in figs_src:
        if len(insert_figs) >= limit:
            break
        if not _is_scan_page_fig(fig) and fig.get("decision") != "insert":
            # 非整页且非 insert 的跳过；整页/xref 一律可作扫描预览
            if not str(fig.get("filename") or "").endswith(".png"):
                continue
        src = workdir / "figures" / fig.get("filename", "")
        if not src.is_file():
            continue
        dest = images_dir / src.name
        shutil.copy2(src, dest)
        fig = dict(fig)
        fig["decision"] = "insert"
        fig["scan_page"] = True
        insert_figs.append(fig)
        copied.append(f"images/{src.name}")
    return insert_figs, copied


def harvest_narrative_from_note(content: str) -> dict[str, str]:
    """从一/二/七节收获 Canvas 叙事卡文案。"""
    out: dict[str, str] = {}

    def _sec(title_pat: str) -> str:
        m = re.search(
            rf"^##\s*{title_pat}\s*\n([\s\S]*?)(?=^##\s|\Z)",
            content,
            re.M,
        )
        return (m.group(1).strip() if m else "")

    one = _sec(r"一、一句话")
    if one:
        # 去掉空行，压成短段
        one = re.sub(r"\n+", " ", one).strip()
        if len(one) > 160:
            one = one[:160] + "…"
        out["one_liner"] = one

    two = _sec(r"二、连贯叙事.*")
    if two:
        for key, label in (
            ("problem", "问题"),
            ("approach", "思路"),
            ("how", "怎么做"),
            ("effect", "效果"),
        ):
            m = re.search(
                rf"\*\*{label}[^*]*\*\*[：:]?\s*(.+?)(?=\n\s*\*\*|\n\n|\Z)",
                two,
                re.S,
            )
            if m:
                text = re.sub(r"\s+", " ", m.group(1)).strip()
                if len(text) > 140:
                    text = text[:140] + "…"
                out[key] = text

    seven = _sec(r"七、和现有技术的差别.*")
    if seven:
        # 取首条非空列表或首段
        bullet = re.search(r"^[-*]\s+\*\*[^*]+\*\*[：:：]?\s*(.+)$", seven, re.M)
        if bullet:
            text = bullet.group(1).strip()
        else:
            text = re.sub(r"\s+", " ", seven.split("\n\n")[0]).strip()
        if len(text) > 140:
            text = text[:140] + "…"
        if text:
            out["diff"] = text
    return out


def _strip_stale_figure_blocks(content: str) -> str:
    """去掉过时的 insert=0 占位 callout / 旧自动附图节 / 散落的 ### 图N 块。"""
    content = re.sub(
        r"(?ms)^> \[!figure\][^\n]*\n(?:>.*\n)*?>[^\n]*insert\s*=\s*0[^\n]*\n(?:>.*\n)*",
        "",
        content,
    )
    content = re.sub(
        r"(?ms)^###\s*附图(?:嵌入)?(?:（扫描件整页预览）|（自动）)?\s*\n.*?(?=^##\s|\Z)",
        "",
        content,
    )
    # 第六节内散落的图标题+嵌入（避免重复注入）
    m6 = re.search(
        r"(^##\s*六、[\s\S]*?)(?=^##\s*七、|\Z)", content, re.M
    )
    if m6:
        sec = m6.group(1)
        sec2 = re.sub(
            r"(?ms)^###\s*图\s*\d+\s*\n+(?:!\[\[[^\]]+\]\]\s*\n(?:\*[^\n]+\*\s*\n)*)+",
            "",
            sec,
        )
        sec2 = re.sub(
            r"(?ms)^!\[\[images/[^\]]+\]\]\s*\n(?:\*[^\n]+\*\s*\n)*",
            "",
            sec2,
        )
        content = content[: m6.start(1)] + sec2 + content[m6.end(1) :]
    return content


def _inject_figure_embeds(
    content: str,
    insert_figs: list[dict],
    *,
    scan_mode: bool = False,
) -> str:
    """在第六节嵌入附图；扫描件模式用整页预览说明。"""
    if not insert_figs:
        return content
    content = _strip_stale_figure_blocks(content)
    missing = [
        f
        for f in insert_figs
        if not _note_references_image(
            content, f.get("relative_path") or f.get("filename", "")
        )
    ]
    # 扫描模式：即使已有部分引用，也重建预览节（去重后）
    if scan_mode:
        missing = insert_figs[:8]
        content = _strip_stale_figure_blocks(content)
    elif not missing:
        return content

    if scan_mode or any(f.get("scan_page") or _is_scan_page_fig(f) for f in missing):
        block_lines = [
            "",
            "### 附图",
            "",
            "> [!tip] 扫描 PDF",
            "> 官方文本多为扫描件，下列为**整页渲染预览**（非矢量裁切图）。"
            "请对照说明书图号阅读；精修裁图需人工确认。",
            "",
        ]
    else:
        block_lines = ["", "### 附图", ""]

    for i, f in enumerate(missing[:8], 1):
        fname = f.get("filename") or ""
        embed = f.get("suggested_embed") or f"![[images/{fname}]]"
        # 统一相对笔记目录的 images/
        if "images/" not in embed and fname:
            embed = f"![[images/{fname}]]"
        page = f.get("page") or f.get("page_number")
        label = str(f.get("label") or "")
        num_m = re.search(r"图\s*(\d+)", label) or re.search(
            r"图(\d+)", fname
        )
        fig_no = num_m.group(1) if num_m else None
        # 用户可见说明只用页码/图号，不暴露内部文件名
        if fig_no and page:
            cap = f"图{fig_no}（第 {page} 页）"
        elif fig_no:
            cap = f"图{fig_no}"
        elif page:
            cap = f"第 {page} 页"
        else:
            cap = f"预览 {i}"
        if fig_no:
            block_lines.append(f"### 图{fig_no}")
            block_lines.append("")
        block_lines.append(embed)
        block_lines.append(f"*{cap}*")
        block_lines.append("")
    block = "\n".join(block_lines)
    m = re.search(r"^##\s*六、.*$", content, re.M)
    if m:
        end = content.find("\n## ", m.end())
        if end == -1:
            return content[: m.end()] + "\n" + block + content[m.end() :]
        return content[:end] + "\n" + block + content[end:]
    return content.rstrip() + "\n" + block


def _wikilink_glossary_in_section5(content: str, glossary_resolved: list[dict]) -> str:
    """仅在第五节术语表内为已解析术语加 wikilink。"""
    m = SECTION5_RE.search(content)
    if not m:
        return content
    sec = m.group(1)
    new_sec = sec
    for g in glossary_resolved:
        term = g.get("term") or ""
        path = g.get("path") or ""
        if not term or not path:
            continue
        link = f"[[{path}|{term}]]"
        if link in new_sec:
            continue
        new_sec = re.sub(
            rf"(\|\s*){re.escape(term)}(\s*\|)",
            rf"\1{link}\2",
            new_sec,
            count=1,
        )
    return content[: m.start(1)] + new_sec + content[m.end(1) :]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--content-file", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--lint-json", default=None, type=optional_path)
    ap.add_argument("--context-anchor", default=None, type=optional_path)
    ap.add_argument("--bundle", default=None, type=optional_path)
    ap.add_argument("--public-clues", default=None, type=optional_path)
    ap.add_argument(
        "--claim-deltas",
        default=None,
        type=optional_path,
        help="Agent 填写的本项新增 JSON（缺省读 workdir/claim_deltas.json）",
    )
    ap.add_argument("--workdir", default=None, type=optional_path)
    ap.add_argument(
        "--strict-figures",
        action="store_true",
        help="要求笔记在入库前已嵌入 insert 图；禁止依赖自动 inject",
    )
    ap.add_argument(
        "--include-review",
        action="store_true",
        help="将 quality=review 的附图一并按 insert 复制并嵌入",
    )
    ap.add_argument(
        "--scan-pages",
        action="store_true",
        help="扫描件模式：复制整页 PNG 并在第六节嵌入预览（无精修图时默认启用）",
    )
    ap.add_argument("--no-glossary-stubs", action="store_true")
    ap.add_argument(
        "--fetch-clues-fallback",
        action="store_true",
        help="线索缺 summary 时用脚本 HTTP 降级抓取（默认关闭；摘要应由 Agent 主路径填写）",
    )
    ap.add_argument(
        "--copy-source-pdf",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="将官方 PDF 复制到笔记目录 source/（默认开启；--no-copy-source-pdf 关闭）",
    )
    ap.add_argument("--output", default="", help="状态 JSON 路径")
    args = ap.parse_args(argv)

    if args.lint_json and args.lint_json.is_file():
        lint = json.loads(args.lint_json.read_text(encoding="utf-8"))
        if not lint.get("passed"):
            print("拒绝写入：lint 未通过", file=sys.stderr)
            return 1

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    content = args.content_file.read_text(encoding="utf-8")
    pub = manifest.get("pub_number") or "patent"
    cfg = runtime_config()

    anchor: dict = {}
    if args.context_anchor and args.context_anchor.is_file():
        anchor = json.loads(args.context_anchor.read_text(encoding="utf-8"))

    public_clues: list = []
    if args.public_clues and args.public_clues.is_file():
        try:
            from clue_vault import as_clues, filter_clues
        except ImportError:
            from tools.patent_reader.clue_vault import as_clues, filter_clues

        raw = json.loads(args.public_clues.read_text(encoding="utf-8"))
        public_clues, _ = filter_clues(as_clues(raw))

    title_m = re.search(r"^#\s+(.+)$", content, re.M)
    title = title_m.group(1).strip() if title_m else f"专利解读 {pub}"
    domain = anchor.get("domain") or resolve_domain(
        title + "\n" + content[:2000],
        (manifest.get("ipc_codes") or [""])[0] if manifest.get("ipc_codes") else "",
    )

    ts = datetime.now().strftime("%Y%m%d")
    filename = f"{slugify_pub(pub)}_解读_{ts}.md"
    pub_slug = slugify_pub(pub)

    vault = Path(cfg["obsidian_vault"]).resolve() if cfg["obsidian_vault"] else None
    papers = cfg["papers_dir"]
    glossary_dir = cfg["glossary_dir"]

    if vault:
        base = vault / papers / domain / pub_slug
        bootstrap_actions = bootstrap_vault(vault, papers)
    else:
        base = Path(cfg["output_dir"]) / f"{pub_slug}_{ts}"
        bootstrap_actions = []

    base.mkdir(parents=True, exist_ok=True)
    images_dir = base / "images"
    images_dir.mkdir(exist_ok=True)

    insert_figs: list[dict] = []
    copied: list[str] = []
    if args.workdir and args.workdir.is_dir():
        # strict：在 inject 前检查，未嵌入则拒绝（不依赖自动补嵌「刷绿」）
        if args.strict_figures:
            preview, _ = _copy_figures_gated(
                args.workdir.resolve(),
                images_dir,
                include_review=args.include_review,
            )
            pre_missing = [
                f.get("filename")
                for f in preview
                if not _note_references_image(
                    content, f.get("relative_path") or f.get("filename", "")
                )
            ]
            if pre_missing:
                print(
                    f"拒绝写入：--strict-figures 要求笔记已嵌入附图: {pre_missing}",
                    file=sys.stderr,
                )
                return 1
        insert_figs, copied = _copy_figures_gated(
            args.workdir.resolve(),
            images_dir,
            include_review=args.include_review or args.scan_pages,
        )
        # 无可用 insert 时自动扫描件整页；或显式 --scan-pages
        scan_mode = bool(args.scan_pages)
        if not insert_figs or scan_mode:
            scan_figs, scan_copied = _copy_scan_pages(
                args.workdir.resolve(), images_dir, limit=8
            )
            if scan_figs:
                insert_figs = scan_figs
                copied = scan_copied
                scan_mode = True
        else:
            scan_mode = any(
                f.get("scan_page") or _is_scan_page_fig(f) for f in insert_figs
            )
    else:
        scan_mode = False

    content = sanitize_user_facing_titles(content)
    content = enrich_note_frontmatter(
        content,
        pub=pub,
        domain=domain,
        manifest=manifest,
        anchor=anchor,
        public_clues=public_clues,
    )

    if insert_figs:
        content = _inject_figure_embeds(
            content, insert_figs, scan_mode=scan_mode
        )
        content = sanitize_user_facing_titles(content)

    nav: list[str] = []
    if vault:
        nav = [
            f"[[{papers}/_专利解读索引|专利解读索引]]",
            f"[[{papers}/{domain}/_领域索引|{domain}领域索引]]",
            f"[[{glossary_dir}/_术语索引|术语索引]]",
        ]
    else:
        nav = [
            "[[_专利解读索引|专利解读索引]]（本地 outputs）",
        ]
    content = _ensure_nav_section(content, nav)

    dest = base / filename
    note_rel = str(dest.relative_to(vault)).replace("\\", "/") if vault else filename

    canvas_rel = (
        f"{papers}/{domain}/{pub_slug}/{pub_slug}_图谱.canvas"
        if vault
        else f"{pub_slug}_图谱.canvas"
    )
    canvas_path = (vault / canvas_rel) if vault else (base / f"{pub_slug}_图谱.canvas")
    glossary_resolved: list[dict] = []

    glossary: list = []
    if args.bundle and args.bundle.is_file():
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        glossary = bundle.get("glossary_candidates") or []
    # Agent 手写第五节/wikilink 时 extract 常为空：入库须从笔记正文补收获
    glossary = merge_glossary_candidates(glossary, harvest_glossary_from_note(content))

    related = {"related_patents": [], "disclosures": []}
    if vault:
        related = scan_vault_related(
            vault,
            papers,
            pub,
            manifest.get("assignees") or [],
            domain=domain,
        )

    claim_tree: dict | None = None
    if args.workdir:
        ct_path = args.workdir.resolve() / "claim_tree.json"
        if ct_path.is_file():
            raw_tree = json.loads(ct_path.read_text(encoding="utf-8"))
            review_meta = (
                raw_tree.get("review") if isinstance(raw_tree, dict) else None
            )
            claim_tree = normalize_claim_tree(raw_tree)
            if isinstance(review_meta, dict):
                claim_tree["review"] = review_meta

    # 第三节：树形一览表；「本项新增」优先 Agent claim_deltas，启发式仅降级
    if claim_tree and (claim_tree.get("nodes") or []):
        agent_deltas: dict[int, str] = {}
        delta_path = args.claim_deltas
        if delta_path is None and args.workdir:
            cand = args.workdir.resolve() / "claim_deltas.json"
            if cand.is_file():
                delta_path = cand
        if delta_path and Path(delta_path).is_file():
            agent_deltas = load_claim_deltas(Path(delta_path))
        # note_plan.json 也可内嵌 claim_deltas
        if args.workdir:
            plan_path = args.workdir.resolve() / "note_plan.json"
            if plan_path.is_file():
                try:
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    agent_deltas = merge_claim_summaries(
                        agent_deltas, load_claim_deltas(plan)
                    )
                except (OSError, json.JSONDecodeError):
                    pass
        summaries = merge_claim_summaries(
            harvest_claim_summaries_from_note(content),
            claim_deltas_from_tree(claim_tree),
            agent_deltas,
        )
        content = upsert_claim_tree_section(
            content,
            render_claim_tree_markdown(
                claim_tree, pub=pub, summaries=summaries
            ),
        )
        side_tree = base / "claim_tree.json"
        side_tree.write_text(
            json.dumps(claim_tree, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 旁路保存 Agent deltas，供 Canvas/再入库
        if agent_deltas and args.workdir:
            side_deltas = {
                "source": "agent",
                "deltas": [
                    {"claim": n, "delta": summaries[n]}
                    for n in sorted(agent_deltas)
                    if n in summaries
                ],
            }
            (args.workdir.resolve() / "claim_deltas.json").write_text(
                json.dumps(side_deltas, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if args.workdir:
            try:
                from obsidian import claim_tree_to_mermaid
            except ImportError:
                from tools.patent_reader.obsidian import claim_tree_to_mermaid

            mmd_path = args.workdir.resolve() / "claim_mermaid.mmd"
            mmd_path.write_text(
                claim_tree_to_mermaid(claim_tree, pub, summaries=summaries) + "\n",
                encoding="utf-8",
            )

    figure_rels: list[str] = []
    if vault and images_dir.is_dir():
        note_dir_rel = str(Path(note_rel).parent).replace("\\", "/")
        for img in sorted(images_dir.glob("*.png"))[:4]:
            figure_rels.append(f"{note_dir_rel}/images/{img.name}")

    # 公开线索：筛选→自动抓取→clues/→附录 B→权/特征旁注
    clue_cards: list[dict] = []
    rich_clues: list[dict] = []
    if public_clues:
        try:
            from clue_vault import (
                clue_cards_for_canvas,
                harvest_feature_entries,
                inject_clue_annotations,
                materialize_clues,
                upsert_appendix_b,
            )
        except ImportError:
            from tools.patent_reader.clue_vault import (
                clue_cards_for_canvas,
                harvest_feature_entries,
                inject_clue_annotations,
                materialize_clues,
                upsert_appendix_b,
            )

        note_dir_rel = str(Path(note_rel).parent).replace("\\", "/") if vault else ""
        rich_clues, appendix_md = materialize_clues(
            public_clues,
            note_dir=base,
            pub=pub,
            note_rel=note_rel if vault else filename,
            claim_summaries=harvest_claim_summaries_from_note(content),
            feature_entries=harvest_feature_entries(content),
            fetch_fallback=bool(args.fetch_clues_fallback),
        )
        content = upsert_appendix_b(content, appendix_md)
        content = inject_clue_annotations(content, rich_clues)
        content = sanitize_user_facing_titles(content)
        clue_cards = clue_cards_for_canvas(rich_clues, note_dir_rel=note_dir_rel)

    canvas_meta = {
        "domain": domain,
        "ipc": (anchor or {}).get("ipc_codes")
        or manifest.get("ipc_codes")
        or "",
        "assignees": manifest.get("assignees")
        or (anchor or {}).get("assignees")
        or [],
        "evidence_scope": manifest.get("evidence_scope") or "",
    }
    narrative = harvest_narrative_from_note(content)

    canvas = build_canvas(
        vault=vault,
        papers_dir=papers,
        note_rel_path=note_rel if vault else filename,
        pub=pub,
        title=title,
        related=related,
        glossary_terms=glossary,
        glossary_dir=glossary_dir,
        create_glossary_stubs=not args.no_glossary_stubs,
        glossary_root=(None if vault else (base / "术语")),
        meta=canvas_meta,
        claim_tree=claim_tree,
        claim_summaries=harvest_claim_summaries_from_note(content),
        figure_rels=figure_rels,
        narrative=narrative,
        clue_cards=clue_cards,
    )
    glossary_resolved = canvas.pop("glossary_resolved", [])
    content = _wikilink_glossary_in_section5(content, glossary_resolved)
    canvas_path.parent.mkdir(parents=True, exist_ok=True)
    canvas_path.write_text(
        json.dumps(canvas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    content = ensure_canvas_nav(
        content, canvas_rel if vault else canvas_path.name
    )

    desc_para_path = ""
    desc_para_cited: list[str] = []
    try:
        from desc_paragraphs import (
            load_description_paragraphs,
            materialize_description_paragraphs,
        )
    except ImportError:
        from tools.patent_reader.desc_paragraphs import (
            load_description_paragraphs,
            materialize_description_paragraphs,
        )

    workdir = args.workdir
    paragraphs = load_description_paragraphs(workdir)
    content, para_dest, desc_para_cited = materialize_description_paragraphs(
        content=content,
        pub=pub,
        note_dir=base,
        paragraphs=paragraphs,
        cited_only=True,
    )
    if para_dest is not None:
        desc_para_path = str(para_dest)

    try:
        from note_cites import enhance_note_citations
    except ImportError:
        from tools.patent_reader.note_cites import enhance_note_citations

    content, claim_anchors_path, claim_anchor_nums = enhance_note_citations(
        content,
        pub=pub,
        note_dir=base,
        claim_tree=claim_tree if isinstance(claim_tree, dict) else None,
        claim_summaries=harvest_claim_summaries_from_note(content),
        insert_figs=insert_figs,
    )

    source_pdf_copied = ""
    if args.copy_source_pdf:
        src_pdf = resolve_source_pdf(manifest, workdir)
        if src_pdf is not None:
            try:
                dest_pdf = copy_source_pdf_to_note_dir(src_pdf, base, pub)
                source_pdf_copied = str(dest_pdf)
                content = ensure_source_pdf_nav(content, pub=pub)
            except OSError as exc:
                print(f"WARN copy-source-pdf failed: {exc}", file=sys.stderr)
        else:
            print(
                "WARN copy-source-pdf: 未找到官方 PDF（manifest.source_path / workdir/source）",
                file=sys.stderr,
            )

    if vault:
        gloss_index = vault / glossary_dir / "_术语索引.md"
        for g in glossary_resolved:
            if g.get("path") and g.get("term"):
                line = f"[[{g['path']}|{g['term']}]] — 来自 `{pub}`"
                upsert_index_entry(
                    gloss_index,
                    "术语索引",
                    line,
                    "专利解读术语概念页。",
                    dedupe_key=g["term"],
                )

    try:
        from note_cites import escape_wikilink_pipes_in_tables
    except ImportError:
        from tools.patent_reader.note_cites import escape_wikilink_pipes_in_tables

    # 表格内 wikilink 别名的 | 必须转义，否则会露路径、拆列
    content = escape_wikilink_pipes_in_tables(content)
    dest.write_text(content, encoding="utf-8")

    moc_paths: list[str] = []
    cli_ok: list[str] = []
    if vault:
        link = _note_link_name(dest, vault)
        entry = f"[[{link}|{pub} {title[:28]}]] — `{ts}` · `{domain}`"
        global_moc = vault / papers / "_专利解读索引.md"
        domain_moc = ensure_domain_index(vault, papers, domain)
        upsert_index_entry(
            global_moc,
            "专利解读索引",
            entry,
            "本页自动汇总专利通俗解读笔记；入库后自动维护。",
        )
        upsert_index_entry(
            domain_moc,
            f"{domain} · 领域索引",
            entry,
            f"领域：**{domain}**。上级：[[{papers}/_专利解读索引|专利解读索引]]。",
        )
        moc_paths = [str(global_moc), str(domain_moc)]

        for prop, val in (
            ("domain", domain),
            ("pub_number", pub),
            ("evidence_scope", manifest.get("evidence_scope", "")),
        ):
            if val and try_obsidian_cli_property(note_rel, prop, str(val), vault):
                cli_ok.append(prop)

    status = {
        "written": str(dest),
        "canvas": str(canvas_path) if canvas_path.is_file() else "",
        "description_paragraphs": desc_para_path,
        "description_paragraphs_cited": desc_para_cited,
        "claim_anchors": str(claim_anchors_path) if claim_anchors_path else "",
        "claim_anchors_count": len(claim_anchor_nums),
        "source_pdf": source_pdf_copied,
        "copy_source_pdf": bool(args.copy_source_pdf),
        "domain": domain,
        "obsidian": bool(vault),
        "bootstrap": bootstrap_actions,
        "moc_updated": moc_paths,
        "obsidian_cli_properties": cli_ok,
        "figures_inserted": [f.get("filename") for f in insert_figs],
        "figures_copied": copied,
        "include_review": args.include_review,
        "scan_pages": bool(scan_mode) if args.workdir else args.scan_pages,
        "narrative_keys": list(narrative.keys()) if narrative else [],
        "glossary_resolved": glossary_resolved,
        "clues_count": len(rich_clues),
        "clues_dir": str(base / "clues") if rich_clues else "",
    }
    print(f"OK written: {dest}")
    if canvas_path.is_file():
        print(f"CANVAS: {canvas_path}")
    if desc_para_path:
        print(f"DESC_PARAS: {desc_para_path} cited={len(desc_para_cited)}")
    if claim_anchors_path:
        print(
            f"CLAIM_ANCHORS: {claim_anchors_path} count={len(claim_anchor_nums)}"
        )
    if source_pdf_copied:
        print(f"SOURCE_PDF: {source_pdf_copied}")
    if insert_figs:
        print(f"FIGURES_INSERT: {len(insert_figs)}")
    for p in moc_paths:
        print(f"MOC: {p}")
    if args.output:
        Path(args.output).write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
