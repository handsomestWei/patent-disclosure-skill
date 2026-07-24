"""专利解读 Obsidian 库增强：模板引导、frontmatter、Canvas、库初始化。"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from common import ROOT, runtime_config, slugify_pub, slugify_term

ASSETS_OBSIDIAN = ROOT / "assets" / "obsidian"


def evidence_scope_label(scope: str) -> str:
    """标签用短英文（patent/evidence/full）。"""
    return {
        "full_text": "full",
        "abstract_only": "abstract",
        "partial": "partial",
    }.get(scope or "", "full")


def evidence_scope_zh(scope: str) -> str:
    """仪表盘/Dataview 显示用中文。"""
    return {
        "full_text": "全文",
        "abstract_only": "仅摘要",
        "partial": "部分",
    }.get(scope or "", scope or "—")


def speculative_zh(flag: bool) -> str:
    return "是" if flag else "否"


def build_tags(domain: str, evidence_scope: str, confidence_speculative: bool) -> list[str]:
    domain_slug = re.sub(r"\s+", "", domain or "未分类")
    tags = [
        f"patents/{domain_slug}",
        f"patent/evidence/{evidence_scope_label(evidence_scope)}",
    ]
    if confidence_speculative:
        tags.append("patent/speculative")
    return tags


def _descendants_of(nodes: list[dict], root: int) -> set[int]:
    """返回 root 及其所有从属权利要求编号。"""
    by_parent: dict[int | None, list[int]] = {}
    for n in nodes:
        by_parent.setdefault(n.get("parent"), []).append(n["number"])
    desc: set[int] = {root}
    stack = [root]
    while stack:
        cur = stack.pop()
        for child in by_parent.get(cur, []):
            if child not in desc:
                desc.add(child)
                stack.append(child)
    return desc


def claim_delta_text(
    text_preview: str,
    *,
    is_independent: bool = False,
    limit: int = 72,
) -> str:
    """从权项原文预览抽出「本项新增」短句（启发式降级；优先用 Agent claim_deltas）。"""
    t = re.sub(r"\s+", " ", (text_preview or "").strip())
    t = re.sub(
        r"^如权利要求[\d、或与以及至到\s]+所述的[^，。；]{0,80}[，,；;]?\s*",
        "",
        t,
    )
    t = re.sub(r"^其特征在于[：:]\s*", "", t)
    if is_independent:
        t = re.sub(r"^一种", "", t)
    # 截到首个长分句，避免整段配方灌进表
    for sep in ("；", ";", "。"):
        if sep in t and t.index(sep) >= 12:
            t = t.split(sep, 1)[0]
            break
    t = t.strip(" ，,;；")
    if len(t) > limit:
        t = t[: limit - 1] + "…"
    return t or "（见原文）"


def load_claim_deltas(raw) -> dict[int, str]:
    """解析 Agent「本项新增」JSON。

    支持：
    - {"deltas":[{"claim":1,"delta":"…"}, …]}
    - {"1":"…","2":"…"} / {"deltas":{"1":"…"}}
    - [{"claim":1,"delta":"…"}] / [{"number":1,"summary":"…"}]
    """
    out: dict[int, str] = {}
    if raw is None:
        return out
    if isinstance(raw, Path):
        if not raw.is_file():
            return out
        try:
            raw = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return out
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("deltas"), list):
            items = raw["deltas"]
        elif isinstance(raw.get("deltas"), dict):
            items = [
                {"claim": k, "delta": v} for k, v in raw["deltas"].items()
            ]
        elif isinstance(raw.get("claim_deltas"), (list, dict)):
            return load_claim_deltas(raw.get("claim_deltas"))
        else:
            # 纯映射：键为权号
            items = [{"claim": k, "delta": v} for k, v in raw.items() if str(k).isdigit() or isinstance(k, int)]
    else:
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        num = item.get("claim", item.get("number", item.get("id")))
        text = item.get("delta", item.get("summary", item.get("text", item.get("本项新增"))))
        try:
            n = int(num)
        except (TypeError, ValueError):
            continue
        s = re.sub(r"\s+", " ", str(text or "").strip())
        if n > 0 and s:
            out[n] = s
    return out


def claim_deltas_from_tree(claim_tree: dict | None) -> dict[int, str]:
    """若 claim_tree.nodes[].delta / agent_delta 已由 Agent 写入，则回收。"""
    out: dict[int, str] = {}
    if not claim_tree:
        return out
    for n in claim_tree.get("nodes") or []:
        num = n.get("number")
        text = n.get("delta") or n.get("agent_delta") or n.get("summary")
        if num is None or not text:
            continue
        try:
            out[int(num)] = re.sub(r"\s+", " ", str(text).strip())
        except (TypeError, ValueError):
            continue
    return out


def merge_claim_summaries(*parts: dict[int, str] | None) -> dict[int, str]:
    """后写覆盖先写。推荐顺序：heuristic←note←tree←agent。"""
    out: dict[int, str] = {}
    for part in parts:
        for k, v in (part or {}).items():
            try:
                n = int(k)
            except (TypeError, ValueError):
                continue
            s = re.sub(r"\s+", " ", str(v or "").strip())
            if n > 0 and s:
                out[n] = s
    return out


def _mermaid_escape(s: str) -> str:
    return (
        (s or "")
        .replace("\\", "/")
        .replace('"', "'")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
    )


def claim_tree_to_mermaid(
    claim_tree: dict,
    pub: str = "",
    *,
    summaries: dict[int, str] | None = None,
) -> str:
    """由 claim_tree.json 生成 mermaid（短标签；独立权=子图）。"""
    nodes = claim_tree.get("nodes") or []
    if not nodes:
        return "flowchart TB\n  empty[无权利要求树数据]"
    summaries = summaries or {}
    roots = claim_tree.get("roots") or [
        n["number"] for n in nodes if n.get("is_independent")
    ]
    by_num = {n["number"]: n for n in nodes if n.get("number") is not None}
    lines = [
        "flowchart TB",
        "  classDef ind fill:#4F46E5,stroke:#312E81,color:#fff",
        "  classDef dep fill:#F8FAFC,stroke:#64748B,color:#0F172A",
    ]
    if pub:
        lines.append(f'  meta["{_mermaid_escape(pub)}"]:::ind')
    for root in roots:
        family = sorted(_descendants_of(nodes, root))
        sg_id = f"sg{root}"
        root_n = by_num.get(root) or {}
        root_raw = summaries.get(root) or claim_delta_text(
            str(root_n.get("text_preview") or ""),
            is_independent=True,
            limit=28,
        )
        if len(root_raw) > 28:
            root_raw = root_raw[:27] + "…"
        root_gist = _mermaid_escape(root_raw)
        lines.append(f'  subgraph {sg_id}["独立权 {root} · {root_gist}"]')
        for num in family:
            n = by_num.get(num) or {}
            raw = summaries.get(num) or claim_delta_text(
                str(n.get("text_preview") or ""),
                is_independent=bool(n.get("is_independent")),
                limit=22,
            )
            if len(raw) > 22:
                raw = raw[:21] + "…"
            gist = _mermaid_escape(raw)
            if n.get("is_independent"):
                lines.append(f'    c{num}["权{num} 独立\\n{gist}"]:::ind')
            else:
                parent = n.get("parent")
                lines.append(f'    c{num}["权{num} ←{parent}\\n{gist}"]:::dep')
        for num in family:
            n = by_num.get(num) or {}
            parent = n.get("parent")
            if parent in family:
                lines.append(f"    c{parent} --> c{num}")
        lines.append("  end")
        if pub:
            lines.append(f"  meta --> c{root}")
    # 多独立权时弱连（产品↔方法）
    if len(roots) >= 2:
        lines.append(f"  c{roots[0]} -.相关.- c{roots[1]}")
    return "\n".join(lines)


def _claim_tree_branch_prefix(
    num: int,
    by_num: dict[int, dict],
    children: dict[int | None, list[int]],
) -> str:
    """为权项生成树形前缀：◆ / ├─ / └─ / │ 等（单一视图表达从属）。"""
    n = by_num.get(num) or {}
    if n.get("is_independent") or n.get("parent") is None:
        return "◆"
    parent = n.get("parent")
    # 根 → parent 路径（用于画左侧竖线）
    path_to_parent: list[int] = []
    cur = parent
    guard = 0
    while cur is not None and guard < 32:
        path_to_parent.append(int(cur))
        cur = (by_num.get(cur) or {}).get("parent")
        guard += 1
    path_to_parent.reverse()
    prefix = ""
    for anc in path_to_parent[:-1]:
        ap = (by_num.get(anc) or {}).get("parent")
        # 独立权之间不互画竖线（多根树并排）
        if ap is None:
            prefix += "　"
            continue
        sibs = children.get(ap, [])
        prefix += "　" if sibs and sibs[-1] == anc else "│ "
    sibs = children.get(parent, [])
    prefix += "└─" if sibs and sibs[-1] == num else "├─"
    return prefix


def render_claim_tree_markdown(
    claim_tree: dict,
    *,
    pub: str = "",
    summaries: dict[int, str] | None = None,
    include_mermaid: bool = False,
) -> str:
    """第三节「权利要求树」：单一树形一览表（结构+新增合在一起）。

    mermaid 默认不嵌入正文（避免与表重复）；需要时可 include_mermaid=True
    或单独使用 claim_mermaid.mmd。
    """
    rows = _claim_tree_rows(claim_tree, summaries=summaries, delta_limit=56)
    if not rows:
        return (
            "## 三、权利要求树\n\n"
            "> 暂无结构化权项树；请对照说明书权利要求书阅读。\n"
        )
    ind_count = sum(1 for b, _, _ in rows if b == "◆")
    dep_count = len(rows) - ind_count
    lines = [
        "## 三、权利要求树",
        "",
        f"> 共 **{len(rows)}** 项 · 独立 **{ind_count}** / 从属 **{dep_count}**。"
        "下表一列看清从属与新增；独立权展开见**第四节**。",
        "",
        "| 结构 | 权 | 本项新增 |",
        "| --- | ---: | --- |",
    ]
    for branch, num, delta in rows:
        lines.append(f"| `{branch}` | {num} | {delta.replace('|', '\\|')} |")

    if include_mermaid:
        mmd = claim_tree_to_mermaid(claim_tree, pub, summaries=summaries)
        lines.extend(
            [
                "",
                "> [!note]- 图形示意（可选）",
                "> 与上表同一棵树，仅供偏好流程图的读者。",
                ">",
                "> ```mermaid",
            ]
        )
        for ml in mmd.splitlines():
            lines.append(f"> {ml}")
        lines.append("> ```")

    return "\n".join(lines).rstrip() + "\n"


def harvest_claim_summaries_from_note(content: str) -> dict[int, str]:
    """从旧版缩进树/表中回收人工写过的短摘要。"""
    m = re.search(
        r"^##\s*三、\s*权利要求树\s*\n([\s\S]*?)(?=^##\s*四、|\Z)",
        content,
        re.M,
    )
    if not m:
        return {}
    sec = m.group(1)
    out: dict[int, str] = {}
    for mm in re.finditer(
        r"\*\*权\s*(\d+)[^*]*\*\*[：:]\s*(.+?)(?=\n|$)",
        sec,
    ):
        out[int(mm.group(1))] = mm.group(2).strip()
    # 旧四列表：权|类型|从属|本项新增
    for mm in re.finditer(
        r"^\|\s*(\d+)\s*\|\s*[^|]+\|\s*[^|]+\|\s*([^|]+)\|",
        sec,
        re.M,
    ):
        num = int(mm.group(1))
        cell = mm.group(2).strip()
        if cell and cell not in ("本项新增", "---"):
            out.setdefault(num, cell)
    # 新三列表：结构|权|本项新增
    for mm in re.finditer(
        r"^\|\s*`?[^|]*`?\s*\|\s*(\d+)\s*\|\s*([^|]+)\|",
        sec,
        re.M,
    ):
        num = int(mm.group(1))
        cell = mm.group(2).strip()
        if cell and cell not in ("本项新增", "---", "权"):
            out.setdefault(num, cell)
    return out


def upsert_claim_tree_section(content: str, section_md: str) -> str:
    """用新版第三节替换笔记中的「三、权利要求树」。"""
    section_md = section_md.rstrip() + "\n\n"
    pat = re.compile(
        r"^##\s*三、\s*权利要求树\s*\n[\s\S]*?(?=^##\s*四、|\Z)",
        re.M,
    )
    if pat.search(content):
        return pat.sub(section_md, content, count=1)
    # 插在第二节后
    m = re.search(r"^##\s*二、.*$", content, re.M)
    if m:
        rest = content[m.end() :]
        m2 = re.search(r"^##\s+", rest, re.M)
        if m2:
            ins = m.end() + m2.start()
            return content[:ins] + section_md + content[ins:]
    return content.rstrip() + "\n\n" + section_md


def parse_frontmatter(content: str) -> tuple[dict, str, str]:
    if not content.startswith("---"):
        return {}, "", content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, "", content
    yaml_block = content[3:end].strip()
    body = content[end + 4 :].lstrip("\n")
    data: dict = {}
    key: str | None = None
    for line in yaml_block.splitlines():
        if line.startswith("  - ") and key == "tags":
            data.setdefault("tags", []).append(line[4:].strip())
        elif line.startswith("  - ") and key == "assignees":
            data.setdefault("assignees", []).append(line[4:].strip())
        elif line.startswith("  - ") and key == "cssclasses":
            data.setdefault("cssclasses", []).append(line[4:].strip())
        elif line.startswith("  - ") and key == "aliases":
            data.setdefault("aliases", []).append(line[4:].strip())
        elif line.startswith("  - ") and key == "related_pubs":
            data.setdefault("related_pubs", []).append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val in ("", "[]"):
                data[key] = (
                    []
                    if key in ("tags", "assignees", "cssclasses", "aliases", "related_pubs")
                    else ""
                )
            elif val == "true":
                data[key] = True
            elif val == "false":
                data[key] = False
            else:
                data[key] = val.strip('"')
    return data, yaml_block, body


def render_frontmatter(data: dict) -> str:
    lines = ["---"]
    order = [
        "tags",
        "aliases",
        "cssclasses",
        "pub_number",
        "domain",
        "ipc",
        "assignees",
        "related_pubs",
        "read_date",
        "perspective",
        "evidence_scope",
        "confidence_speculative",
    ]
    written: set[str] = set()
    for key in order + sorted(k for k in data if k not in order):
        if key in written or key not in data:
            continue
        written.add(key)
        val = data[key]
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _clue_is_speculative(clue: dict) -> bool:
    conf = str(clue.get("confidence") or "").strip().lower()
    if conf in ("高", "high"):
        return False
    if conf in ("中", "低", "medium", "low", "med", "mid", ""):
        return True
    # 未标注置信度但有 URL 的附录线索默认视为推测
    return bool(clue.get("url") or clue.get("link"))


def enrich_note_frontmatter(
    content: str,
    *,
    pub: str,
    domain: str,
    manifest: dict,
    anchor: dict,
    public_clues: list | None = None,
) -> str:
    fm, _, body = parse_frontmatter(content)
    ipc_codes = manifest.get("ipc_codes") or anchor.get("ipc_codes") or []
    ipc = ipc_codes[0] if ipc_codes else ""
    scope = manifest.get("evidence_scope") or fm.get("evidence_scope") or "full_text"
    assignees = manifest.get("assignees") or anchor.get("assignees") or fm.get("assignees") or []
    clues = public_clues or []
    speculative = bool(fm.get("confidence_speculative"))
    if clues:
        speculative = speculative or any(_clue_is_speculative(c) for c in clues)
    # 未传线索文件时，根据正文附录 B / speculative callout 推断
    if not clues and (
        "[!speculative]" in body
        or re.search(r"置信度[：:]\s*(中|低)", body)
        or "公开检索线索" in body and "http" in body
    ):
        speculative = True

    tags = list(dict.fromkeys(build_tags(domain, scope, speculative) + list(fm.get("tags") or [])))
    cssclasses = list(dict.fromkeys(["patent-reader"] + list(fm.get("cssclasses") or [])))
    aliases = list(dict.fromkeys([pub] + list(fm.get("aliases") or [])))

    # ipc 可能已是分号串（Agent 手写）
    if not ipc and isinstance(fm.get("ipc"), str):
        ipc = fm.get("ipc") or ""
    elif isinstance(ipc_codes, list) and len(ipc_codes) > 1 and not str(fm.get("ipc") or "").strip():
        ipc = "; ".join(str(x) for x in ipc_codes[:4])

    fm.update(
        {
            "tags": tags,
            "aliases": aliases,
            "cssclasses": cssclasses,
            "pub_number": pub,
            "domain": domain,
            "ipc": ipc or fm.get("ipc") or "",
            "assignees": assignees[:5] if isinstance(assignees, list) else assignees,
            "evidence_scope": scope,
            "evidence_label": evidence_scope_zh(str(scope)),
            "confidence_speculative": speculative,
            "speculative_label": speculative_zh(bool(speculative)),
        }
    )
    if not fm.get("read_date"):
        fm["read_date"] = datetime.now().strftime("%Y-%m-%d")
    return render_frontmatter(fm) + body


def scan_vault_related(
    vault: Path,
    papers_dir: str,
    pub: str,
    assignees: list[str],
    *,
    domain: str = "",
) -> dict:
    """扫描库内相关笔记：同领域解读、同申请人、交底书。"""
    papers = vault / papers_dir
    related_patents: list[dict] = []
    disclosures: list[dict] = []
    if not papers.is_dir():
        return {"related_patents": [], "disclosures": [], "glossary_notes": []}

    assignee_set = {a.strip() for a in assignees if a and len(a.strip()) >= 2}
    pub_slug = slugify_pub(pub)
    seen: set[str] = set()

    for md in papers.rglob("*.md"):
        if md.name.startswith("_") or is_spurious_patent_note(md):
            continue
        rel = str(md.relative_to(vault)).replace("\\", "/")
        text = md.read_text(encoding="utf-8", errors="replace")[:4000]
        base = md.stem
        if pub_slug in base or (pub and pub in base):
            continue

        if "_解读_" in md.name and rel not in seen:
            same_domain = bool(domain) and f"/{domain}/" in f"/{rel}/"
            same_assignee = bool(assignee_set) and any(a in text for a in assignee_set)
            if same_domain or same_assignee:
                label = "同申请人" if same_assignee else "同领域"
                if same_domain and same_assignee:
                    label = "同申请人·同领域"
                related_patents.append(
                    {"path": rel, "title": base, "label": label}
                )
                seen.add(rel)

        if pub in text and ("交底书" in text or "disclosure" in base.lower()):
            disclosures.append({"path": rel, "title": base})

    return {
        "related_patents": related_patents[:8],
        "disclosures": disclosures[:5],
        "glossary_notes": [],
    }


def _parse_aliases_from_fm(yaml_block: str) -> tuple[str, list[str]]:
    """仅从 aliases / title 取值，避免把 tags 误收为 alias。"""
    title = ""
    aliases: list[str] = []
    in_aliases = False
    for line in yaml_block.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("title:"):
            title = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            in_aliases = False
            continue
        if stripped.startswith("tags:") or stripped.startswith("cssclasses:"):
            in_aliases = False
            continue
        if stripped.startswith("aliases:"):
            in_aliases = True
            rest = stripped.split(":", 1)[1].strip()
            if rest and rest not in ("", "[]"):
                aliases.append(rest.strip('"').strip("'"))
            continue
        if in_aliases:
            if stripped.startswith("  - ") or (stripped.startswith("- ") and not stripped.startswith("- ipc")):
                aliases.append(stripped.lstrip("- ").strip().strip('"').strip("'"))
                continue
            if stripped and not stripped.startswith(" "):
                in_aliases = False
    return title, [a for a in aliases if a]


def scan_glossary_index(vault: Path, glossary_dir: str) -> dict[str, str]:
    """扫描术语目录：term/alias -> 相对库根路径（无 .md）。"""
    root = vault / glossary_dir
    index: dict[str, str] = {}
    if not root.is_dir():
        return index
    for md in root.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        rel = str(md.relative_to(vault).with_suffix("")).replace("\\", "/")
        stem = md.stem
        index[stem] = rel
        index[stem.lower()] = rel
        try:
            text = md.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            continue
        fm_m = re.match(r"^---\n([\s\S]*?)\n---", text)
        if not fm_m:
            continue
        title, aliases = _parse_aliases_from_fm(fm_m.group(1))
        if title:
            index[title] = rel
            index[title.lower()] = rel
        for alias in aliases:
            index[alias] = rel
            index[alias.lower()] = rel
    return index


def _glossary_file_matches_term(path: Path, term: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")[:1200]
    fm_m = re.match(r"^---\n([\s\S]*?)\n---", text)
    if not fm_m:
        return path.stem == term or path.stem == slugify_term(term)
    title, aliases = _parse_aliases_from_fm(fm_m.group(1))
    keys = {title, path.stem, *(aliases or [])}
    keys |= {k.lower() for k in keys if k}
    return term in keys or term.lower() in keys


def normalize_wiki_path(path: str) -> str:
    """库内 wikilink 路径：统一 /，去掉 .md（Obsidian 惯例）。"""
    s = (path or "").replace("\\", "/").strip()
    if s.endswith(".md"):
        s = s[:-3]
    # 去掉误产生的「文件名 1」后缀对应路径中的空格副本（仅清理链到空壳的情况由调用方处理）
    return s


def _wikilink_target(line: str) -> str:
    m = re.search(r"\[\[([^\]|#]+)", line)
    return normalize_wiki_path(m.group(1)) if m else ""


def is_spurious_patent_note(path: Path) -> bool:
    """空壳/重复解读笔记：如「CN…_解读_20260721 1.md」（点坏链自动生成）。"""
    name = path.name
    if re.search(r"\s+\d+\.md$", name) and "_解读_" in name:
        return True
    if "_解读_" in name and path.is_file() and path.stat().st_size == 0:
        return True
    return False


def append_glossary_backlinks(
    path: Path,
    *,
    source_pub: str,
    note_rel: str = "",
    disclosures: list[dict] | None = None,
) -> None:
    """在术语页追加/合并反链：来源专利解读、交底书。路径一律正斜杠并去重。"""
    if not path.is_file():
        return
    body = path.read_text(encoding="utf-8")
    marker = "## 反链"
    note_rel = normalize_wiki_path(note_rel)
    # 防御：调用方若传入 Path 的 Windows 字符串
    if note_rel.startswith("./"):
        note_rel = note_rel[2:]

    # 先规范化已有反链节（去掉反斜杠重复项）
    body, section_changed = _normalize_glossary_backlink_section(body)

    lines: list[str] = []
    if source_pub:
        if note_rel:
            lines.append(f"- 解读：[[{note_rel}|{source_pub}]]")
        elif f"`{source_pub}`" not in body and f"|{source_pub}]]" not in body:
            lines.append(f"- 专利：`{source_pub}`")
    for d in disclosures or []:
        p = normalize_wiki_path(str(d.get("path") or ""))
        title = d.get("title") or p
        if p:
            lines.append(f"- 交底书：[[{p}|{title}]]")

    existing_targets: set[str] = set()
    if marker in body:
        sec = body.split(marker, 1)[1]
        for ln in sec.splitlines():
            tgt = _wikilink_target(ln)
            if tgt:
                existing_targets.add(tgt)
            # 无链接的「专利：`CNxxx`」行
            if source_pub and f"`{source_pub}`" in ln:
                existing_targets.add(f"pub:{source_pub}")

    new_lines: list[str] = []
    for ln in lines:
        tgt = _wikilink_target(ln)
        if tgt and tgt in existing_targets:
            continue
        if source_pub and ln.strip() == f"- 专利：`{source_pub}`" and (
            f"pub:{source_pub}" in existing_targets or f"|{source_pub}]]" in body
        ):
            continue
        if ln in body:
            continue
        new_lines.append(ln)
        if tgt:
            existing_targets.add(tgt)

    need_seen_in = False
    if source_pub and body.startswith("---"):
        fm_end = body.find("\n---", 3)
        fm_head = body[: fm_end + 4] if fm_end != -1 else body[:800]
        if "seen_in:" not in fm_head:
            need_seen_in = True
        elif source_pub not in fm_head:
            need_seen_in = True

    if not new_lines and not need_seen_in and not section_changed:
        return

    if new_lines:
        if marker not in body:
            body = body.rstrip() + f"\n\n{marker}\n\n" + "\n".join(new_lines) + "\n"
        else:
            for ln in new_lines:
                body = body.rstrip() + f"\n{ln}\n"

    if need_seen_in and source_pub:
        if "seen_in:" in body[:800]:
            body = re.sub(
                r"(seen_in:\s*\n(?:\s+- .+\n)*)",
                rf"\1  - {source_pub}\n",
                body,
                count=1,
            )
        else:
            end = body.find("\n---", 3)
            if end != -1:
                body = body[:end] + f"\nseen_in:\n  - {source_pub}\n" + body[end:]
    path.write_text(body, encoding="utf-8")


def _normalize_glossary_backlink_section(body: str) -> tuple[str, bool]:
    """反链节：路径改正斜杠，按目标去重。"""
    marker = "## 反链"
    if marker not in body:
        return body, False
    pre, rest = body.split(marker, 1)
    # 反链节到下一 ## 或文末
    m = re.match(r"(\s*\n)([\s\S]*?)(?=\n##\s|\Z)", rest)
    if not m:
        return body, False
    head_ws, sec = m.group(1), m.group(2)
    tail = rest[m.end() :]
    kept: list[str] = []
    seen: set[str] = set()
    for ln in sec.splitlines():
        raw = ln.rstrip()
        if not raw.strip():
            continue
        if "[[" in raw:

            def _fix_link(mo: re.Match[str]) -> str:
                target = mo.group(1).replace("\\", "/")
                rest_g = mo.group(2) or ""
                return f"[[{target}{rest_g}]]"

            raw = re.sub(r"\[\[([^\]|#]+)((?:\|[^\]]*)?)\]\]", _fix_link, raw)
        key = _wikilink_target(raw) or raw.strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(raw)
    new_sec = ("\n".join(kept) + "\n") if kept else ""
    new_body = pre + marker + head_ws + new_sec + tail
    return new_body, new_body != body


def repair_glossary_backlinks(vault: Path, glossary_dir: str) -> int:
    """批量修复术语页反链（反斜杠重复）。返回修改文件数。"""
    root = vault / glossary_dir
    if not root.is_dir():
        return 0
    n = 0
    for path in root.glob("*.md"):
        if path.name.startswith("_"):
            continue
        try:
            old = path.read_text(encoding="utf-8")
        except OSError:
            continue
        new, changed = _normalize_glossary_backlink_section(old)
        if changed and new != old:
            path.write_text(new, encoding="utf-8")
            n += 1
    return n


def purge_spurious_patent_notes(vault: Path, papers_dir: str) -> list[str]:
    """删除点坏链产生的空壳「…解读… 1.md」。"""
    root = vault / papers_dir
    removed: list[str] = []
    if not root.is_dir():
        return removed
    for md in root.rglob("*.md"):
        if not is_spurious_patent_note(md):
            continue
        # 仅删空文件或明确的「 数字」后缀副本
        try:
            if md.stat().st_size == 0 or re.search(r"\s+\d+\.md$", md.name):
                rel = str(md.relative_to(vault)).replace("\\", "/")
                md.unlink()
                removed.append(rel)
        except OSError:
            continue
    return removed


def ensure_glossary_stub(
    vault: Path,
    glossary_dir: str,
    term: str,
    *,
    definition: str = "",
    source_pub: str = "",
    papers_dir: str = "Research/Patents",
    note_rel: str = "",
    disclosures: list[dict] | None = None,
) -> tuple[str, bool]:
    """确保术语页存在；撞名时换唯一 slug；返回 (相对路径无.md, 是否新建)。"""
    root = vault / glossary_dir
    root.mkdir(parents=True, exist_ok=True)
    slug = slugify_term(term)
    path = root / f"{slug}.md"
    if path.is_file() and not _glossary_file_matches_term(path, term):
        # slug 撞名但术语不同 → 换唯一文件名
        i = 2
        while True:
            cand = root / f"{slug}_{i}.md"
            if not cand.is_file() or _glossary_file_matches_term(cand, term):
                path = cand
                break
            i += 1
    rel = str(path.relative_to(vault).with_suffix("")).replace("\\", "/")
    created = False
    if path.is_file():
        # 合并 alias；若正文仍是占位且有第五节含义则回填
        text = path.read_text(encoding="utf-8")
        if term not in text[:600]:
            text = re.sub(
                r"(aliases:\s*\n(?:\s+- .+\n)*)",
                rf"\1  - {term}\n",
                text,
                count=1,
            )
            path.write_text(text, encoding="utf-8")
        if definition.strip():
            _fill_glossary_definition(path, term, definition.strip())
    else:
        defn = definition.strip() or "（待补充：来自专利说明书定义或一般理解）"
        body = (
            "---\n"
            "tags:\n"
            "  - glossary\n"
            "aliases:\n"
            f"  - {term}\n"
            f"title: {term}\n"
            f"source_pub: {source_pub}\n"
            "seen_in:\n"
            f"  - {source_pub}\n"
            "---\n\n"
            f"# {term}\n\n"
            f"{defn}\n\n"
            f"来源专利：`{source_pub}` · [[{papers_dir}/_专利解读索引|专利解读索引]]\n\n"
            "## 反链\n\n"
        )
        path.write_text(body, encoding="utf-8")
        created = True
    append_glossary_backlinks(
        path,
        source_pub=source_pub,
        note_rel=note_rel,
        disclosures=disclosures,
    )
    return rel, created


def _fill_glossary_definition(path: Path, term: str, definition: str) -> bool:
    """用第五节「本文含义」回填空壳/占位术语页正文。"""
    if not definition or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    m = re.search(
        rf"(^#\s*{re.escape(term)}\s*\n\n)(.+?)(\n\n来源专利[：:]|\n\n##\s*反链|\Z)",
        text,
        re.M | re.S,
    )
    if not m:
        return False
    old = m.group(2).strip()
    if old == definition:
        return False
    if not (
        old.startswith("（待补充")
        or old.startswith("(待补充")
        or len(old) < 8
    ):
        # 已有实质定义则不覆盖，仅当很短时允许补强
        if len(old) >= 8 and "待补充" not in old:
            return False
    new_text = text[: m.start(2)] + definition + text[m.end(2) :]
    path.write_text(new_text, encoding="utf-8")
    return True


def resolve_glossary_nodes(
    vault: Path,
    glossary_dir: str,
    terms: list[str] | list[dict],
    *,
    create_stubs: bool = True,
    source_pub: str = "",
    papers_dir: str = "Research/Patents",
    definitions: dict[str, str] | None = None,
    note_rel: str = "",
    disclosures: list[dict] | None = None,
) -> list[dict]:
    """将术语列表解析为 Canvas 可用节点信息。"""
    definitions = definitions or {}
    index = scan_glossary_index(vault, glossary_dir)
    nodes: list[dict] = []
    # 全部术语建 stub/反链；Canvas 仅展示前 8 个节点
    for i, item in enumerate(terms):
        if isinstance(item, dict):
            term = str(item.get("term") or "").strip()
            defn = str(item.get("definition") or definitions.get(term, "")).strip()
        else:
            term = str(item).strip()
            defn = definitions.get(term, "")
        if not term:
            continue
        rel = index.get(term) or index.get(term.lower())
        created = False
        if not rel and create_stubs:
            rel, created = ensure_glossary_stub(
                vault,
                glossary_dir,
                term,
                definition=defn,
                source_pub=source_pub,
                papers_dir=papers_dir,
                note_rel=note_rel,
                disclosures=disclosures,
            )
            index[term] = rel
        elif rel:
            # 已有页：补反链；有定义则尝试回填空壳
            stub_path = vault / f"{rel}.md"
            if defn:
                _fill_glossary_definition(stub_path, term, defn)
            append_glossary_backlinks(
                stub_path,
                source_pub=source_pub,
                note_rel=note_rel,
                disclosures=disclosures,
            )
        if i < 8:
            nodes.append(
                {
                    "term": term,
                    "path": rel or "",
                    "created": created,
                    "has_file": bool(rel),
                    "definition": defn,
                }
            )
    return nodes


def _claim_tree_rows(
    claim_tree: dict,
    *,
    summaries: dict[int, str] | None = None,
    delta_limit: int = 40,
) -> list[tuple[str, int, str]]:
    """统一权项树行：(结构前缀, 权号, 本项新增)。与笔记第三节同构。"""
    nodes = claim_tree.get("nodes") or []
    if not nodes:
        return []
    summaries = dict(summaries or {})
    by_num = {n["number"]: n for n in nodes if n.get("number") is not None}
    for n in nodes:
        num = n.get("number")
        if num is None:
            continue
        if num in summaries and str(summaries[num]).strip():
            summaries[num] = re.sub(r"\s+", " ", str(summaries[num]).strip())
            if len(summaries[num]) > delta_limit:
                summaries[num] = summaries[num][: delta_limit - 1] + "…"
            continue
        summaries[num] = claim_delta_text(
            str(n.get("text_preview") or ""),
            is_independent=bool(n.get("is_independent")),
            limit=delta_limit,
        )

    children: dict[int | None, list[int]] = {}
    for n in nodes:
        parent = None if n.get("is_independent") else n.get("parent")
        children.setdefault(parent, []).append(n["number"])
    for k in children:
        children[k] = sorted(children[k])

    def _walk(num: int, acc: list[int]) -> None:
        if num in acc:
            return
        acc.append(num)
        for ch in children.get(num, []):
            _walk(ch, acc)

    order: list[int] = []
    roots = list(
        dict.fromkeys(
            [n["number"] for n in nodes if n.get("is_independent")]
            or (claim_tree.get("roots") or [])
        )
    )
    for r in roots:
        _walk(int(r), order)
    for num in sorted(by_num.keys()):
        if num not in order:
            order.append(num)

    rows: list[tuple[str, int, str]] = []
    for num in order:
        n = by_num[num]
        if n.get("is_independent") or n.get("parent") is None:
            branch = "◆"
        else:
            branch = _claim_tree_branch_prefix(num, by_num, children)
        rows.append((branch, num, summaries.get(num) or "—"))
    return rows


def _claim_tree_card_text(
    claim_tree: dict | None,
    pub: str,
    *,
    summaries: dict[int, str] | None = None,
) -> str:
    """Canvas 权项卡：与笔记第三节同一套树形表（更短一句）。"""
    if not claim_tree:
        return ""
    rows = _claim_tree_rows(claim_tree, summaries=summaries, delta_limit=32)
    if not rows:
        return ""
    ind = sum(1 for b, _, _ in rows if b == "◆")
    lines = [
        f"## 权项树 · `{pub}`",
        "",
        f"独立 {ind} / 共 {len(rows)} · 与笔记第三节同构",
        "",
        "| 结构 | 权 | 本项新增 |",
        "| --- | ---: | --- |",
    ]
    for branch, num, delta in rows[:14]:
        lines.append(f"| `{branch}` | {num} | {delta.replace('|', '\\|')} |")
    if len(rows) > 14:
        lines.append(f"| … |  | 另 {len(rows) - 14} 项 |")
    return "\n".join(lines)


# Canvas 配色（hex；旧客户端不认时可回退预设 1–6）
_CANVAS_COLORS = {
    "center": "#4F46E5",
    "hub": "#0284C7",
    "claims": "#475569",
    "related": "#CA8A04",
    "term": "#EA580C",
    "disclosure": "#0F766E",
    "group_narr": "#6366F1",
    "group_term": "#F97316",
    "group_rel": "#EAB308",
    "narr_problem": "#DC2626",
    "narr_approach": "#D97706",
    "narr_how": "#2563EB",
    "narr_effect": "#059669",
    "narr_diff": "#7C3AED",
    "narr_one": "#4F46E5",
    "clue": "#B45309",
    "group_clue": "#D97706",
}


def _clip_canvas_text(text: str, limit: int = 140) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _narrative_cards(narrative: dict | None) -> list[tuple[str, str, str, str]]:
    """返回 (id, 标题, 正文, 颜色) 列表。"""
    if not narrative:
        return []
    order = [
        ("problem", "问题", "narr_problem"),
        ("approach", "思路", "narr_approach"),
        ("how", "怎么做", "narr_how"),
        ("effect", "效果", "narr_effect"),
        ("diff", "差别", "narr_diff"),
        ("one_liner", "一句话", "narr_one"),
    ]
    cards: list[tuple[str, str, str, str]] = []
    for key, label, color_key in order:
        text = str(narrative.get(key) or "").strip()
        if not text:
            continue
        if key == "one_liner" and any(
            k in narrative for k in ("problem", "approach", "effect")
        ):
            continue
        cards.append(
            (
                f"narr-{key}",
                label,
                _clip_canvas_text(text, 160),
                _CANVAS_COLORS[color_key],
            )
        )
    return cards[:5]


def build_canvas(
    *,
    vault: Path | None,
    papers_dir: str,
    note_rel_path: str,
    pub: str,
    title: str,
    related: dict,
    glossary_terms: list[str] | list[dict] | None = None,
    glossary_dir: str = "Research/术语",
    create_glossary_stubs: bool = True,
    glossary_root: Path | None = None,
    meta: dict | None = None,
    claim_tree: dict | None = None,
    claim_summaries: dict[int, str] | None = None,
    figure_rels: list[str] | None = None,
    narrative: dict | None = None,
    clue_cards: list[dict] | None = None,
) -> dict:
    """生成 JSON Canvas：叙事故事地图 + 精简中心 + 术语含义卡 + 分组。

    glossary_root 用于无 vault 时写入本地术语页。
    默认不挂扫描附图（易刷屏）；figure_rels 仅保留非 page_ 精修图最多 1 张。
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    center_id = "center"
    meta = meta or {}
    narrative = narrative or {}
    note_rel = str(note_rel_path).replace("\\", "/")
    note_link = note_rel[:-3] if note_rel.endswith(".md") else note_rel

    domain = str(meta.get("domain") or "").strip()
    ipc = meta.get("ipc") or meta.get("ipc_codes") or ""
    if isinstance(ipc, list):
        ipc = "; ".join(str(x) for x in ipc[:4])
    assignees = meta.get("assignees") or []
    if isinstance(assignees, list):
        asg = "、".join(str(a) for a in assignees[:3])
    else:
        asg = str(assignees)
    scope = str(meta.get("evidence_scope") or "").strip()
    scope_zh = {
        "full_text": "全文",
        "abstract_only": "仅摘要",
        "partial": "部分",
    }.get(scope, scope or "—")

    one = _clip_canvas_text(
        str(narrative.get("one_liner") or narrative.get("problem") or ""), 120
    )
    center_lines = [
        f"# `{pub}`",
        "",
        f"**{title}**" if title else "",
        "",
        one or "（打开下方链接阅读全文解读）",
        "",
        f"[[{note_link}|打开解读笔记]]",
    ]
    nodes.append(
        {
            "id": center_id,
            "type": "text",
            "text": "\n".join(ln for ln in center_lines if ln is not None),
            "x": -40,
            "y": -40,
            "width": 420,
            "height": 240,
            "color": _CANVAS_COLORS["center"],
        }
    )

    # 叙事卡 + 分组（中心上方）
    narr_cards = _narrative_cards(narrative)
    if narr_cards:
        n = len(narr_cards)
        card_w, gap = 250, 16
        total_w = n * card_w + (n - 1) * gap
        start_x = -total_w // 2
        narr_y = -420
        nodes.append(
            {
                "id": "grp-narr",
                "type": "group",
                "x": start_x - 24,
                "y": narr_y - 48,
                "width": total_w + 48,
                "height": 290,
                "label": "叙事",
                "color": _CANVAS_COLORS["group_narr"],
            }
        )
        for i, (nid, label, text, color) in enumerate(narr_cards):
            nodes.append(
                {
                    "id": nid,
                    "type": "text",
                    "text": f"## {label}\n\n{text}",
                    "x": start_x + i * (card_w + gap),
                    "y": narr_y,
                    "width": card_w,
                    "height": 220,
                    "color": color,
                }
            )
            edges.append(
                {
                    "id": f"e-{nid}",
                    "fromNode": nid,
                    "fromSide": "bottom",
                    "toNode": center_id,
                    "toSide": "top",
                    "label": label,
                    "color": color,
                }
            )

    hub_lines = [
        "## 著录",
        "",
        f"**公开号** `{pub}`",
        f"**领域** {domain or '—'}",
        f"**IPC** {ipc or '—'}",
        f"**申请人** {asg or '—'}",
        f"**证据** {scope_zh}",
        "",
        f"[[{papers_dir}/_专利解读索引|索引]]",
    ]
    if domain:
        hub_lines.append(f"[[{papers_dir}/{domain}/_领域索引|{domain}]]")
    hub_lines.append(f"[[{glossary_dir}/_术语索引|术语索引]]")

    nodes.append(
        {
            "id": "hub",
            "type": "text",
            "text": "\n".join(hub_lines),
            "x": -560,
            "y": -80,
            "width": 300,
            "height": 280,
            "color": _CANVAS_COLORS["hub"],
        }
    )
    edges.append(
        {
            "id": "e-hub-center",
            "fromNode": "hub",
            "fromSide": "right",
            "toNode": center_id,
            "toSide": "left",
            "label": "著录",
            "color": _CANVAS_COLORS["hub"],
        }
    )

    claim_text = _claim_tree_card_text(
        claim_tree, pub, summaries=claim_summaries
    )
    if claim_text:
        row_n = max(claim_text.count("\n|"), 3)
        nodes.append(
            {
                "id": "claims",
                "type": "text",
                "text": claim_text,
                "x": -580,
                "y": 220,
                "width": 360,
                "height": min(120 + row_n * 28, 420),
                "color": _CANVAS_COLORS["claims"],
            }
        )
        edges.append(
            {
                "id": "e-claims-center",
                "fromNode": "claims",
                "fromSide": "right",
                "toNode": center_id,
                "toSide": "left",
                "label": "权项",
                "color": _CANVAS_COLORS["claims"],
            }
        )

    rel_items = list(related.get("related_patents") or [])[:4]
    if rel_items:
        nodes.append(
            {
                "id": "grp-rel",
                "type": "group",
                "x": 480,
                "y": -200,
                "width": 340,
                "height": 40 + len(rel_items) * 150,
                "label": "关联专利",
                "color": _CANVAS_COLORS["group_rel"],
            }
        )
    y = -160
    for i, item in enumerate(rel_items):
        nid = f"rp{i}"
        path = str(item.get("path") or "").replace("\\", "/")
        link = path[:-3] if path.endswith(".md") else path
        other = str(item.get("title") or item.get("pub") or Path(path).stem)
        if "_解读_" in other:
            other = other.split("_解读_")[0]
        elif other.endswith("_解读"):
            other = other[: -len("_解读")]
        label = item.get("label") or "相关专利"
        nodes.append(
            {
                "id": nid,
                "type": "text",
                "text": f"## {other}\n\n*{label}*\n\n[[{link}|打开笔记]]",
                "x": 500,
                "y": y,
                "width": 300,
                "height": 130,
                "color": _CANVAS_COLORS["related"],
            }
        )
        edges.append(
            {
                "id": f"e-center-{nid}",
                "fromNode": center_id,
                "fromSide": "right",
                "toNode": nid,
                "toSide": "left",
                "label": label,
                "color": _CANVAS_COLORS["related"],
            }
        )
        y += 150

    y_dc = 200 if claim_text else 220
    for i, item in enumerate(related.get("disclosures") or []):
        nid = f"dc{i}"
        path = str(item.get("path") or "").replace("\\", "/")
        link = path[:-3] if path.endswith(".md") else path
        nodes.append(
            {
                "id": nid,
                "type": "text",
                "text": f"## 交底书\n\n[[{link}|打开]]",
                "x": -560,
                "y": y_dc + 320 + i * 160,
                "width": 300,
                "height": 120,
                "color": _CANVAS_COLORS["disclosure"],
            }
        )
        edges.append(
            {
                "id": f"e-dc-{nid}",
                "fromNode": nid,
                "fromSide": "right",
                "toNode": center_id,
                "toSide": "left",
                "label": "交底书",
                "color": _CANVAS_COLORS["disclosure"],
            }
        )

    # 公开线索卡（推测层；链到 clues/ 笔记）
    clue_list = list(clue_cards or [])[:6]
    if clue_list:
        clue_y0 = 420
        nodes.append(
            {
                "id": "grp-clues",
                "type": "group",
                "x": 480,
                "y": clue_y0 - 40,
                "width": 340,
                "height": 36 + len(clue_list) * 150,
                "label": "公开线索（推测）",
                "color": _CANVAS_COLORS["group_clue"],
            }
        )
        for i, card in enumerate(clue_list):
            nid = f"clue{i}"
            title = str(card.get("title") or "线索")[:40]
            conf = card.get("confidence") or "中"
            link = str(card.get("link") or "").replace("\\", "/")
            reason = str(card.get("reason") or "")[:64]
            claims = card.get("related_claims") or []
            fids = card.get("related_feature_ids") or []
            bits: list[str] = []
            if claims:
                bits.append("权" + "、".join(str(n) for n in claims[:4]))
            if fids:
                bits.append("·".join(str(x) for x in fids[:4]))
            claim_bit = "可能相关：" + " ".join(bits) if bits else "弱匹配未命中"
            text = (
                f"## {title}\n\n"
                f"*置信 {conf} · 推测*\n\n"
                f"{claim_bit}\n\n"
                f"{reason}\n\n"
                f"[[{link}|打开线索]]"
            )
            nodes.append(
                {
                    "id": nid,
                    "type": "text",
                    "text": text,
                    "x": 500,
                    "y": clue_y0 + i * 150,
                    "width": 300,
                    "height": 140,
                    "color": _CANVAS_COLORS["clue"],
                }
            )
            edges.append(
                {
                    "id": f"e-center-{nid}",
                    "fromNode": center_id,
                    "fromSide": "bottom",
                    "toNode": nid,
                    "toSide": "left",
                    "label": "线索",
                    "color": _CANVAS_COLORS["clue"],
                }
            )
            if claims and claim_text:
                edges.append(
                    {
                        "id": f"e-claims-{nid}",
                        "fromNode": "claims",
                        "fromSide": "right",
                        "toNode": nid,
                        "toSide": "bottom",
                        "label": "权" + "、".join(str(n) for n in claims[:3]),
                        "color": _CANVAS_COLORS["clue"],
                    }
                )

    glossary_nodes: list[dict] = []
    disclosures = related.get("disclosures") or []
    # 从 glossary_terms 预取 definition，resolve 后仍保留
    defn_map: dict[str, str] = {}
    for item in list(glossary_terms or []):
        if isinstance(item, dict):
            t = str(item.get("term") or "").strip()
            d = str(item.get("definition") or "").strip()
            if t and d:
                defn_map[t] = d

    if vault and glossary_terms:
        glossary_nodes = resolve_glossary_nodes(
            vault,
            glossary_dir,
            list(glossary_terms),
            create_stubs=create_glossary_stubs,
            source_pub=pub,
            papers_dir=papers_dir,
            note_rel=note_link,
            disclosures=disclosures,
            definitions=defn_map,
        )
    elif glossary_terms and glossary_root is not None:
        glossary_root.mkdir(parents=True, exist_ok=True)
        fake_vault = glossary_root.parent
        rel_dir = glossary_root.name
        glossary_nodes = resolve_glossary_nodes(
            fake_vault,
            rel_dir,
            list(glossary_terms),
            create_stubs=create_glossary_stubs,
            source_pub=pub,
            papers_dir=papers_dir,
            note_rel="",
            disclosures=disclosures,
            definitions=defn_map,
        )
        for g in glossary_nodes:
            if g.get("path"):
                g["path"] = f"{rel_dir}/{Path(g['path']).name}"
    elif glossary_terms:
        for item in list(glossary_terms)[:8]:
            if isinstance(item, dict):
                glossary_nodes.append(
                    {
                        "term": item.get("term"),
                        "path": "",
                        "has_file": False,
                        "definition": item.get("definition") or "",
                    }
                )
            else:
                glossary_nodes.append(
                    {"term": str(item), "path": "", "has_file": False, "definition": ""}
                )

    for g in glossary_nodes:
        if not g.get("definition") and g.get("term") in defn_map:
            g["definition"] = defn_map[g["term"]]

    show_terms = glossary_nodes[:6]
    if show_terms:
        cols = min(3, len(show_terms))
        rows = (len(show_terms) + cols - 1) // cols
        card_w, card_h, gap_x, gap_y = 240, 150, 16, 16
        grid_w = cols * card_w + (cols - 1) * gap_x
        grid_h = rows * card_h + (rows - 1) * gap_y
        gx = -grid_w // 2
        gy = 320
        nodes.append(
            {
                "id": "grp-term",
                "type": "group",
                "x": gx - 20,
                "y": gy - 40,
                "width": grid_w + 40,
                "height": grid_h + 56,
                "label": "术语（本文含义）",
                "color": _CANVAS_COLORS["group_term"],
            }
        )
        for i, g in enumerate(show_terms):
            nid = f"g{i}"
            term = g.get("term") or ""
            defn = _clip_canvas_text(str(g.get("definition") or "（见术语页）"), 90)
            col, row = i % cols, i // cols
            path = str(g.get("path") or "")
            if path and not path.endswith(".md"):
                link_target = path
            elif path:
                link_target = path[:-3]
            else:
                link_target = ""
            body = f"## {term}\n\n{defn}"
            if link_target:
                body += f"\n\n[[{link_target}|术语页]]"
            nodes.append(
                {
                    "id": nid,
                    "type": "text",
                    "text": body,
                    "x": gx + col * (card_w + gap_x),
                    "y": gy + row * (card_h + gap_y),
                    "width": card_w,
                    "height": card_h,
                    "color": _CANVAS_COLORS["term"],
                }
            )
            edges.append(
                {
                    "id": f"e-g-{nid}",
                    "fromNode": center_id,
                    "fromSide": "bottom",
                    "toNode": nid,
                    "toSide": "top",
                    "label": "术语",
                    "color": _CANVAS_COLORS["term"],
                }
            )

    # 仅非扫描页精修图，最多 1 张（可选）
    figs = [
        f
        for f in (figure_rels or [])
        if f and "page_" not in Path(f).name.lower() and "xref" not in Path(f).name.lower()
    ][:1]
    if figs:
        frel = figs[0].replace("\\", "/")
        nodes.append(
            {
                "id": "fig0",
                "type": "file",
                "file": frel,
                "x": 500,
                "y": y + 20,
                "width": 220,
                "height": 160,
                "color": "6",
            }
        )
        edges.append(
            {
                "id": "e-fig-0",
                "fromNode": center_id,
                "fromSide": "right",
                "toNode": "fig0",
                "toSide": "left",
                "label": "附图",
            }
        )

    return {"nodes": nodes, "edges": edges, "glossary_resolved": glossary_nodes}


def upsert_index_entry(
    index_path: Path,
    title: str,
    entry_line: str,
    intro: str,
    extra_body: str = "",
    *,
    dedupe_key: str = "",
) -> None:
    """创建或更新索引页，追加笔记列表条目。

    dedupe_key: 若提供，则删除列表中已含该 key 的旧行后再追加（用于术语按 term 去重）。
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if index_path.is_file():
        body = index_path.read_text(encoding="utf-8")
    else:
        body = (
            f"---\ntags:\n  - patents/index\n---\n\n"
            f"# {title}\n\n{intro}\n\n{extra_body}\n"
        )

    marker = "## 笔记列表"
    # 术语索引用「术语列表」
    if "术语" in title and marker not in body and "## 术语列表" in body:
        marker = "## 术语列表"

    if dedupe_key:
        lines = body.splitlines(keepends=True)
        new_lines: list[str] = []
        for ln in lines:
            if ln.lstrip().startswith("- ") and dedupe_key in ln:
                continue
            new_lines.append(ln)
        body = "".join(new_lines)
    elif entry_line in body:
        index_path.write_text(body, encoding="utf-8")
        return

    if marker not in body:
        body = body.rstrip() + f"\n\n{marker}\n\n"
    body = body.rstrip() + f"\n- {entry_line}\n"
    index_path.write_text(body, encoding="utf-8")


def ensure_domain_index(vault: Path, papers_dir: str, domain: str) -> Path:
    """确保领域索引页存在。"""
    domain_dir = vault / papers_dir / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    index_path = domain_dir / "_领域索引.md"
    if not index_path.is_file():
        body = (
            "---\n"
            "tags:\n"
            "  - patents/index\n"
            f"cssclasses:\n"
            "  - patent-index\n"
            "---\n\n"
            f"# {domain} · 领域索引\n\n"
            f"领域：**{domain}**。上级：[[{papers_dir}/_专利解读索引|专利解读索引]]。\n\n"
            f"## 本领域仪表盘（Dataview）\n\n"
            f"```dataview\n"
            f'TABLE pub_number AS "公开号", read_date AS "解读日期", '
            f'default(evidence_label, choice(evidence_scope = "full_text", "全文", '
            f'choice(evidence_scope = "abstract_only", "仅摘要", '
            f'choice(evidence_scope = "partial", "部分", evidence_scope)))) AS "证据范围", '
            f'default(speculative_label, choice(confidence_speculative, "是", "否")) AS "含推测"\n'
            f'FROM "{papers_dir}/{domain}"\n'
            f'WHERE contains(file.name, "_解读_")\n'
            f"SORT read_date DESC\n"
            f"```\n\n"
            "## 笔记列表\n\n"
        )
        index_path.write_text(body, encoding="utf-8")
    else:
        # 已有领域索引：升级证据列中文显示
        try:
            body = index_path.read_text(encoding="utf-8")
        except OSError:
            return index_path
        if "evidence_label" not in body and (
            'evidence_scope AS "证据' in body
            or 'AS "证据"' in body
            or 'AS "证据范围"' in body
        ):
            body2 = re.sub(
                r"```dataview\nTABLE[\s\S]*?```",
                (
                    "```dataview\n"
                    'TABLE pub_number AS "公开号", read_date AS "解读日期", '
                    'default(evidence_label, choice(evidence_scope = "full_text", "全文", '
                    'choice(evidence_scope = "abstract_only", "仅摘要", '
                    'choice(evidence_scope = "partial", "部分", evidence_scope)))) AS "证据范围", '
                    'default(speculative_label, choice(confidence_speculative, "是", "否")) AS "含推测"\n'
                    f'FROM "{papers_dir}/{domain}"\n'
                    'WHERE contains(file.name, "_解读_")\n'
                    "SORT read_date DESC\n"
                    "```"
                ),
                body,
                count=1,
            )
            if body2 != body:
                index_path.write_text(body2, encoding="utf-8")
    return index_path


def _repair_index_glossary_dataview(index_path: Path, glossary_dir: str) -> bool:
    """修补索引页「术语网」Dataview：围栏必须为 ```，查询用 FROM … AND #glossary。"""
    try:
        body = index_path.read_text(encoding="utf-8")
    except OSError:
        return False
    fence = "`" * 3
    new_section = (
        "### 术语网（反链入口）\n\n"
        f"> 下列列表依赖 Dataview；若仍为空，请打开 `{glossary_dir}/` 核对术语页，"
        "或点开 `glossary.base`。\n\n"
        f"{fence}dataview\n"
        "LIST\n"
        f'FROM "{glossary_dir}" AND #glossary\n'
        'WHERE file.name != "_术语索引"\n'
        "SORT file.name ASC\n"
        f"{fence}\n\n"
    )
    pat = re.compile(r"###\s*术语网[\s\S]*?(?=##\s*笔记列表|##\s*关联图谱)")
    m = pat.search(body)
    if not m:
        return False
    good = f'{fence}dataview\nLIST\nFROM "{glossary_dir}" AND #glossary\n'
    sec = m.group(0)
    if good in sec and sec.count(fence) >= 2:
        return False
    new_body = pat.sub(new_section, body)
    if new_body == body:
        return False
    index_path.write_text(new_body, encoding="utf-8")
    return True


def _upgrade_index_evidence_dataview(index_path: Path, papers_dir: str) -> bool:
    """将主索引 Dataview 证据/推测列升级为中文（evidence_label / speculative_label）。"""
    try:
        body = index_path.read_text(encoding="utf-8")
    except OSError:
        return False
    if "evidence_label" in body and "speculative_label" in body:
        return False
    if "evidence_scope AS" not in body and 'AS "含推测"' not in body:
        return False
    fence = "`" * 3
    new_table = (
        f"{fence}dataview\n"
        'TABLE pub_number AS "公开号", domain AS "领域", read_date AS "解读日期", '
        'default(evidence_label, choice(evidence_scope = "full_text", "全文", '
        'choice(evidence_scope = "abstract_only", "仅摘要", '
        'choice(evidence_scope = "partial", "部分", evidence_scope)))) AS "证据范围", '
        'ipc AS "IPC", '
        'default(speculative_label, choice(confidence_speculative, "是", "否")) AS "含推测"\n'
        f'FROM "{papers_dir}"\n'
        'WHERE contains(file.name, "_解读_")\n'
        "SORT read_date DESC\n"
        f"{fence}"
    )
    body2, n = re.subn(
        rf"{fence}dataview\nTABLE[\s\S]*?{fence}",
        new_table,
        body,
        count=1,
    )
    if n == 0 or body2 == body:
        return False
    # 确保有关联图谱节
    if "_专利关联.canvas" not in body2:
        link = f"- [[{papers_dir}/_专利关联.canvas|专利关联总览]]（交付后可生成专利关联）\n"
        if "## 关联图谱" in body2:
            body2 = re.sub(
                r"(##\s*关联图谱\s*\n)",
                rf"\1\n{link}",
                body2,
                count=1,
            )
        elif "## 笔记列表" in body2:
            body2 = body2.replace(
                "## 笔记列表",
                f"## 关联图谱\n\n{link}\n## 笔记列表",
                1,
            )
    index_path.write_text(body2, encoding="utf-8")
    return True


def _rgb_pack(hex_color: str) -> int:
    """#RRGGBB → Obsidian graph.json 的 rgb 整数。"""
    h = hex_color.lstrip("#")
    return int(h, 16)


def build_patent_graph_color_groups(
    papers_dir: str = "Research/Patents",
    glossary_dir: str = "Research/术语",
) -> list[dict]:
    """专利解读关系图配色（先匹配先生效）。"""
    papers_q = papers_dir.replace("\\", "/").rstrip("/")
    gloss_q = glossary_dir.replace("\\", "/").rstrip("/")

    def g(query: str, hex_color: str) -> dict:
        return {"query": query, "color": {"a": 1, "rgb": _rgb_pack(hex_color)}}

    return [
        g("file:_图谱", "#14B8A6"),  # Canvas 单篇图谱 · 青绿
        g("file:_专利关联", "#0D9488"),  # 全局关联 · 深青
        g(f'path:"{gloss_q}"', "#F97316"),  # 术语目录 · 橙
        g("tag:#glossary", "#FB923C"),  # 术语标签 · 浅橙
        g("tag:#patents/index", "#64748B"),  # 索引 · 石板灰
        g("tag:#patent/speculative", "#F59E0B"),  # 含推测 · 琥珀
        g("file:_解读_", "#4F46E5"),  # 解读笔记 · 靛
        g("tag:#patents", "#6366F1"),  # 专利标签 · 靛紫
        g("file:.base", "#0F766E"),  # Bases · 深青
        g(f'path:"{papers_q}"', "#818CF8"),  # 专利目录兜底
    ]


def _is_managed_graph_query(query: str) -> bool:
    q = str(query or "")
    return (
        q.startswith("file:_图谱")
        or q.startswith("file:_专利关联")
        or q.startswith("file:_解读_")
        or q.startswith("file:.base")
        or q.startswith("tag:#patent")
        or q.startswith("tag:#glossary")
        or q.startswith("tag:#patents")
        or q.startswith('path:"Research/')
        or q.startswith("path:Research/")
    )


# 关系图保留 Canvas/PDF，过滤附图、旁路 JSON、悬停旁路笔记
# （search 与 Obsidian 搜索语法一致；负向 file: 排除节点）
GRAPH_EXCLUDE_TERMS = (
    "-file:.png",
    "-file:.jpg",
    "-file:.jpeg",
    "-file:.gif",
    "-file:.webp",
    "-file:.svg",
    "-file:.bmp",
    "-file:.tif",
    "-file:.tiff",
    "-file:.json",
    "-file:.jsonl",
    "-file:_权项锚点",
    "-file:_说明书段落",
)

# 兼容旧名
GRAPH_IMAGE_EXCLUDE_TERMS = GRAPH_EXCLUDE_TERMS


def _merge_graph_search_excludes(existing: str) -> str:
    """在保留用户自定义 filter 的前提下，确保排除噪声节点。"""
    parts = [p for p in (existing or "").split() if p]
    for term in GRAPH_EXCLUDE_TERMS:
        if term not in parts:
            parts.append(term)
    return " ".join(parts)


def _merge_graph_search_hide_images(existing: str) -> str:
    """兼容旧调用名。"""
    return _merge_graph_search_excludes(existing)


def ensure_graph_color_groups(
    vault: Path,
    papers_dir: str = "Research/Patents",
    glossary_dir: str = "Research/术语",
) -> str | None:
    """写入/合并 .obsidian/graph.json 颜色分组；返回动作描述或 None。"""
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    graph_path = obsidian_dir / "graph.json"
    desired = build_patent_graph_color_groups(papers_dir, glossary_dir)
    desired_queries = {g["query"] for g in desired}

    if graph_path.is_file():
        try:
            data = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    else:
        data = {
            "collapse-filter": False,
            "search": "",
            "showTags": False,
            "showAttachments": True,
            "hideUnresolved": False,
            "showOrphans": True,
            "collapse-display": False,
            "showArrow": False,
            "textFadeMultiplier": 0,
            "nodeSizeMultiplier": 1.1,
            "lineSizeMultiplier": 1,
            "collapse-forces": False,
            "centerStrength": 0.5,
            "repelStrength": 10,
            "linkStrength": 1,
            "linkDistance": 250,
            "scale": 1,
            "close": False,
        }

    existing = data.get("colorGroups") or []
    kept = [
        g
        for g in existing
        if isinstance(g, dict)
        and g.get("query")
        and g["query"] not in desired_queries
        and not _is_managed_graph_query(g["query"])
    ]
    data["colorGroups"] = desired + kept
    data["collapse-color-groups"] = False  # 展开 Groups，便于看到配色图例
    data["showAttachments"] = True  # 保留 Canvas/PDF；图片与 JSON 用 search 排除
    data["search"] = _merge_graph_search_excludes(str(data.get("search") or ""))
    data["collapse-filter"] = False  # 展开过滤器，便于看到已排除项
    graph_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return f"graph_colors:{graph_path}"


def ensure_colored_tags_seed(vault: Path) -> str | None:
    """若已装 Colored Tags，写入更鲜明的调色板与已知专利标签序号（不覆盖用户 tagColors）。"""
    data_path = vault / ".obsidian" / "plugins" / "colored-tags" / "data.json"
    if not data_path.is_file():
        return None
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    changed = False
    palette = data.setdefault("palette", {})
    # bright 比 adaptive-soft 更适合「一眼能分清」
    if palette.get("selected") in (None, "adaptive-soft", ""):
        palette["selected"] = "bright"
        changed = True
    known = data.setdefault("knownTags", {})
    seeds = {
        "patents": 1,
        "glossary": 3,
        "patent": 2,
        "patents/index": 5,
        "glossary/index": 3,
        "patent/evidence": 4,
        "patent/evidence/full": 4,
        "patent/evidence/abstract": 6,
        "patent/speculative": 2,
    }
    for tag, idx in seeds.items():
        if tag not in known:
            known[tag] = idx
            changed = True
    if not changed:
        return None
    data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return f"colored_tags:{data_path}"


def bootstrap_vault(vault: Path, papers_dir: str = "Research/Patents") -> list[str]:
    """将 assets/obsidian 引导文件写入库（幂等）。"""
    actions: list[str] = []
    papers = vault / papers_dir
    papers.mkdir(parents=True, exist_ok=True)

    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)

    snippets_dir = obsidian_dir / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)
    css_src = ASSETS_OBSIDIAN / "patent-reader.css"
    css_dst = snippets_dir / "patent-reader.css"
    if css_src.is_file():
        shutil.copy2(css_src, css_dst)
        actions.append(f"snippet:{css_dst}")

    base_src = ASSETS_OBSIDIAN / "patents.base"
    base_dst = papers / "patents.base"
    if base_src.is_file():
        need_copy = not base_dst.is_file() or base_src.stat().st_mtime > base_dst.stat().st_mtime
        if need_copy:
            body = base_src.read_text(encoding="utf-8")
            body = body.replace("{{PAPERS_DIR}}", papers_dir)
            body = body.replace("Research/Patents", papers_dir)
            base_dst.write_text(body, encoding="utf-8")
            actions.append(f"base:{base_dst}")

    gloss_base_src = ASSETS_OBSIDIAN / "glossary.base"
    cfg = runtime_config()
    glossary_rel = cfg.get("glossary_dir") or "Research/术语"
    if gloss_base_src.is_file():
        gloss_root = vault / glossary_rel
        gloss_root.mkdir(parents=True, exist_ok=True)
        gloss_base_dst = gloss_root / "glossary.base"
        need_copy = (
            not gloss_base_dst.is_file()
            or gloss_base_src.stat().st_mtime > gloss_base_dst.stat().st_mtime
        )
        if need_copy:
            body = gloss_base_src.read_text(encoding="utf-8")
            body = body.replace("{{GLOSSARY_DIR}}", glossary_rel)
            gloss_base_dst.write_text(body, encoding="utf-8")
            actions.append(f"glossary_base:{gloss_base_dst}")

    index_tpl = ASSETS_OBSIDIAN / "_专利解读索引.template.md"
    index_dst = papers / "_专利解读索引.md"
    if index_tpl.is_file() and not index_dst.is_file():
        body = index_tpl.read_text(encoding="utf-8")
        body = body.replace("{{PAPERS_DIR}}", papers_dir)
        body = body.replace("Research/Patents", papers_dir)
        body = body.replace("{{GLOSSARY_DIR}}", glossary_rel)
        index_dst.write_text(body, encoding="utf-8")
        actions.append(f"index:{index_dst}")
    elif index_dst.is_file():
        # 已有索引：修补术语网 + 升级证据列中文 + 关系图配色说明
        if _repair_index_glossary_dataview(index_dst, glossary_rel):
            actions.append(f"index_glossary_dv:{index_dst}")
        if _upgrade_index_evidence_dataview(index_dst, papers_dir):
            actions.append(f"index_evidence_zh:{index_dst}")
        try:
            ibody = index_dst.read_text(encoding="utf-8")
            if "自动上色" not in ibody and "## 关联图谱" in ibody:
                tip = (
                    "- 打开左侧 **关系图**：节点已按类型自动上色"
                    "（靛=解读，青绿=Canvas，橙=术语，琥珀=含推测）。"
                    "若仍为灰色，请重载库（Ctrl/Cmd+R）。\n"
                )
                ibody2 = ibody.replace("## 关联图谱\n", f"## 关联图谱\n\n{tip}", 1)
                if ibody2 != ibody:
                    index_dst.write_text(ibody2, encoding="utf-8")
                    actions.append(f"index_graph_tip:{index_dst}")
        except OSError:
            pass

    glossary_root = vault / glossary_rel
    glossary_root.mkdir(parents=True, exist_ok=True)
    gloss_index = glossary_root / "_术语索引.md"
    if not gloss_index.is_file():
        gloss_index.write_text(
            "---\n"
            "tags:\n"
            "  - glossary/index\n"
            "---\n\n"
            "# 术语索引\n\n"
            "本目录存放专利解读产生的术语概念页；Canvas 与笔记第五节可 wikilink 至此。\n\n"
            f"上级：[[{papers_dir}/_专利解读索引|专利解读索引]]\n\n"
            "## 术语仪表盘（Bases）\n\n"
            f"![[{glossary_rel}/glossary.base#全部术语]]\n\n"
            "## 术语列表\n\n",
            encoding="utf-8",
        )
        actions.append(f"glossary:{gloss_index}")

    # 空库也创建 appearance.json 并启用 CSS snippet
    appearance = obsidian_dir / "appearance.json"
    try:
        if appearance.is_file():
            data = json.loads(appearance.read_text(encoding="utf-8"))
        else:
            data = {}
            actions.append("created:appearance.json")
        enabled = data.get("enabledCssSnippets") or []
        if "patent-reader" not in enabled:
            enabled.append("patent-reader")
            data["enabledCssSnippets"] = enabled
            appearance.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            actions.append("enabled_snippet:patent-reader")
    except (json.JSONDecodeError, OSError):
        pass

    # 核心插件 Bases：写入 core-plugins.json（社区插件无法由脚本代装）
    core_plugins = obsidian_dir / "core-plugins.json"
    try:
        if core_plugins.is_file():
            cp = json.loads(core_plugins.read_text(encoding="utf-8"))
        else:
            cp = {}
            actions.append("created:core-plugins.json")
        if isinstance(cp, dict) and cp.get("bases") is not True:
            cp["bases"] = True
            core_plugins.write_text(
                json.dumps(cp, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            actions.append("enabled_core:bases")
    except (json.JSONDecodeError, OSError, TypeError):
        pass

    # 全局关系图自动上色（原生 Groups，无需插件）
    g_act = ensure_graph_color_groups(vault, papers_dir, glossary_rel)
    if g_act:
        actions.append(g_act)
    ct_act = ensure_colored_tags_seed(vault)
    if ct_act:
        actions.append(ct_act)

    # 清理空壳「解读 1.md」与术语反链反斜杠重复
    purged = purge_spurious_patent_notes(vault, papers_dir)
    for rel in purged:
        actions.append(f"purged_spurious:{rel}")
    repaired = repair_glossary_backlinks(vault, glossary_rel)
    if repaired:
        actions.append(f"glossary_backlinks_repaired:{repaired}")

    return actions


def try_obsidian_cli_property(file_rel: str, name: str, value: str, vault: Path) -> bool:
    """若 PATH 中有 obsidian CLI，设置属性。"""
    try:
        r = subprocess.run(
            [
                "obsidian",
                "property:set",
                f'file={file_rel}',
                f"name={name}",
                f"value={value}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(vault),
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def ensure_canvas_nav(content: str, canvas_rel: str, label: str = "专利族图谱") -> str:
    """写入指向 *.canvas 的导航；并清除无扩展名占位链接（点开会生成空 .md）。"""
    rel = canvas_rel.replace("\\", "/")
    if not rel.endswith(".canvas"):
        rel = f"{rel}.canvas"
    link = f"[[{rel}|{label}]]"
    # 去掉模板占位：[[..._图谱|专利族图谱]]（入库后生成）等无 .canvas 链接
    content = re.sub(
        r"^[ \t]*-?\s*\[\[[^\]]*_图谱(?:\|[^\]]*)?\]\][^\n]*\n?",
        "",
        content,
        flags=re.M,
    )
    if link in content:
        return content
    m = re.search(r"^##\s*Obsidian\s*导航\s*\n", content, re.M | re.I)
    if m:
        insert_at = m.end()
        return content[:insert_at] + f"- {link}\n" + content[insert_at:]
    return content
