"""解读笔记内「权 N」「图 N」引用 → 可跳转 / 悬停预览的 wikilink。

权项锚点默认落在旁路笔记 `{公开号}_权项锚点.md`（与说明书段落同级），避免占主笔记版面。
"""
from __future__ import annotations

import re
from pathlib import Path

# 权1/3、权1／8：表示两点，不是闭区间
CLAIM_SLASH_RE = re.compile(
    r"(?<!\[\[)(?<!\|)(?<!#\^claim-)"
    r"权\s*(\d{1,3})\s*[/／]\s*(\d{1,3})"
    r"(?!\]])"
)
CLAIM_CITE_RE = re.compile(
    r"(?<!\[\[)(?<!\|)(?<!#\^claim-)"
    r"权\s*(\d{1,3})(?:\s*[–—\-~至到]\s*(\d{1,3}))?"
    r"(?!\]])"
)
FIG_CITE_RE = re.compile(
    r"(?<!\[\[)(?<!\|)(?<!images/)"
    r"图\s*(\d{1,3})(?:\s*[–—\-~至到]\s*(\d{1,3}))?"
    r"(?!\]])"
)
CLAIM_WIKILINK_RE = re.compile(
    r"\[\[[^\]]*?#\^claim-(\d+)(?:-\d+)?\|[^\]]*\]\]"
)
# 旧版同笔记块锚 → 升级为旁路笔记
LEGACY_SAME_NOTE_CLAIM_RE = re.compile(
    r"\[\[#\^claim-(\d+)\|权\s*\1\]\]"
)


def _protect_zones(content: str) -> tuple[str, list[str]]:
    vault: list[str] = []

    def stash(m: re.Match[str]) -> str:
        vault.append(m.group(0))
        return f"\x00NC{len(vault) - 1}\x00"

    tmp = re.sub(r"```[\s\S]*?```", stash, content)
    tmp = re.sub(r"\[\[[^\]]+\]\]", stash, tmp)
    tmp = re.sub(r"^#{1,6}\s*图\s*\d+[^\n]*$", stash, tmp, flags=re.M)
    tmp = re.sub(r"^#{1,6}\s*权\s*\d+[^\n]*$", stash, tmp, flags=re.M)
    tmp = re.sub(r"^>\s*#{1,6}\s*权\s*\d+[^\n]*$", stash, tmp, flags=re.M)
    tmp = re.sub(r"^\*图\s*\d+[^\n]*\*$", stash, tmp, flags=re.M)
    return tmp, vault


def _restore_zones(content: str, vault: list[str]) -> str:
    return re.sub(
        r"\x00NC(\d+)\x00", lambda m: vault[int(m.group(1))], content
    )


def _expand(a: int, b: int | None) -> list[int]:
    if b is None or b == a:
        return [a]
    lo, hi = (a, b) if a <= b else (b, a)
    if hi - lo > 40:
        return [a, b]
    return list(range(lo, hi + 1))


def claim_anchor_basename(pub: str) -> str:
    try:
        from common import slugify_pub
    except ImportError:
        from tools.patent_reader.common import slugify_pub

    return f"{slugify_pub(pub)}_权项锚点"


def format_claim_wikilinks(
    start: int, end: int | None = None, *, pub: str = ""
) -> str:
    base = claim_anchor_basename(pub) if pub else ""
    prefix = f"{base}#" if base else "#"

    def one(n: int) -> str:
        return f"[[{prefix}^claim-{n}|权{n}]]"

    if end is None or end == start:
        return one(start)
    return f"{one(start)}–{one(end)}"


def format_figure_wikilinks(start: int, end: int | None = None) -> str:
    if end is None or end == start:
        return f"[[#图{start}|图{start}]]"
    return f"[[#图{start}|图{start}]]–[[#图{end}|图{end}]]"


def upgrade_legacy_claim_wikilinks(content: str, *, pub: str) -> str:
    """[[#^claim-N|权N]] → [[{pub}_权项锚点#^claim-N|权N]]"""
    base = claim_anchor_basename(pub)

    def repl(m: re.Match[str]) -> str:
        n = m.group(1)
        return f"[[{base}#^claim-{n}|权{n}]]"

    # 已指向旁路笔记的不改；只改同笔记 #^claim-
    return LEGACY_SAME_NOTE_CLAIM_RE.sub(repl, content)


def wikilink_claim_citations(content: str, *, pub: str = "") -> str:
    """正文「权2–3」→ 旁路笔记块锚 wikilink。"""
    content = upgrade_legacy_claim_wikilinks(content, pub=pub) if pub else content
    protected, vault = _protect_zones(content)

    def repl_slash(m: re.Match[str]) -> str:
        a, b = int(m.group(1)), int(m.group(2))
        return (
            f"{format_claim_wikilinks(a, pub=pub)}/"
            f"{format_claim_wikilinks(b, pub=pub)}"
        )

    def repl(m: re.Match[str]) -> str:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else None
        return format_claim_wikilinks(a, b, pub=pub)

    out = CLAIM_SLASH_RE.sub(repl_slash, protected)
    out = CLAIM_CITE_RE.sub(repl, out)
    return _restore_zones(out, vault)


def wikilink_figure_citations(content: str) -> str:
    """正文「图1–3」→ 文内图标题锚。"""
    protected, vault = _protect_zones(content)

    def repl(m: re.Match[str]) -> str:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else None
        return format_figure_wikilinks(a, b)

    out = FIG_CITE_RE.sub(repl, protected)
    return _restore_zones(out, vault)


def parse_cited_claim_numbers(content: str) -> list[int]:
    found: set[int] = set()
    for m in CLAIM_WIKILINK_RE.finditer(content):
        found.add(int(m.group(1)))
    protected, _ = _protect_zones(content)
    for m in CLAIM_SLASH_RE.finditer(protected):
        found.add(int(m.group(1)))
        found.add(int(m.group(2)))
    for m in CLAIM_CITE_RE.finditer(protected):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else None
        found.update(_expand(a, b))
    return sorted(found)


def strip_inline_claim_anchors(content: str) -> str:
    """去掉主笔记内旧版「权项锚点」节（callout / ###）。"""
    content = re.sub(
        r"\n*> \[!note\]- 权项锚点[\s\S]*?(?=\n##\s|\Z)",
        "\n",
        content,
        count=1,
    )
    content = re.sub(
        r"\n*###\s*权项锚点\s*\n[\s\S]*?(?=\n##\s|\Z)",
        "\n",
        content,
        count=1,
    )
    return content


def render_claim_anchors_note(
    *,
    pub: str,
    claim_tree: dict | None,
    summaries: dict[int, str] | None,
    nums: list[int],
) -> str:
    summaries = summaries or {}
    by_num = {
        int(n.get("number")): n
        for n in (claim_tree or {}).get("nodes") or []
        if n.get("number") is not None
    }
    lines = [
        "---",
        "tags:",
        "  - patent/claim-anchors",
        f"pub_number: {pub}",
        "cssclasses:",
        "  - patent-reader",
        "---",
        f"# {pub} 权项锚点",
        "",
        "## 使用说明",
        "",
        "1. **设置**：Obsidian → 设置 → 核心插件 → **页面预览（Page preview）** → 打开",
        "2. **使用**：在解读笔记中 **按住 Ctrl** 悬停「权 N」链接，即可预览本项摘要；单击跳转至此。",
        "",
        "> 本页供解读正文链接；默认含权项树上的全部权号。",
        "",
    ]
    for n in nums:
        node = by_num.get(n) or {}
        delta = (summaries.get(n) or "").strip()
        if not delta:
            delta = str(node.get("delta") or node.get("text_preview") or "").strip()
            delta = re.sub(r"\s+", " ", delta)[:120]
        if not delta:
            delta = f"见解读笔记第三节权{n} / 第四节独立权展开"
        kind = "独立权" if node.get("is_independent") else "从属权"
        lines.extend(
            [
                f"### 权 {n}（{kind}）",
                "",
                delta,
                "",
                f"^claim-{n}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def ensure_claim_anchors_nav(content: str, *, pub: str) -> str:
    """导航补「权项锚点」入口（无括号说明）。"""
    base = claim_anchor_basename(pub)
    needle = f"[[{base}|权项锚点]]"
    content = re.sub(
        rf"(-\s*\[\[{re.escape(base)}\|[^\]]*\]\])（[^）\n]*）",
        r"\1",
        content,
    )
    if needle in content or f"{base}|" in content:
        return content
    m = re.search(
        r"(##\s*Obsidian 导航\s*\n)([\s\S]*?)(?=\n##\s|\n> \[!|\Z)", content
    )
    if not m:
        return content
    block = m.group(2)
    if not block.strip().startswith("-"):
        return content
    lines = block.rstrip().splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if "说明书段落" in line:
            insert_at = i + 1
            break
        if "图谱" in line or "canvas" in line.lower():
            insert_at = i + 1
    lines.insert(insert_at, f"- {needle}")
    new_block = "\n".join(lines) + "\n"
    return content[: m.start(2)] + new_block + content[m.end(2) :]


def materialize_claim_anchors(
    content: str,
    *,
    pub: str,
    note_dir: Path,
    claim_tree: dict | None = None,
    summaries: dict[int, str] | None = None,
) -> tuple[str, Path | None, list[int]]:
    """写旁路权项锚点笔记，去掉主文内旧锚点节，改写权链接。"""
    content = strip_inline_claim_anchors(content)
    nums: set[int] = set(parse_cited_claim_numbers(content))
    for node in (claim_tree or {}).get("nodes") or []:
        try:
            nums.add(int(node.get("number")))
        except (TypeError, ValueError):
            continue
    ordered = sorted(nums)
    if not ordered:
        content = wikilink_claim_citations(content, pub=pub)
        content = ensure_claim_anchors_nav(content, pub=pub)
        return content, None, []

    note_body = render_claim_anchors_note(
        pub=pub,
        claim_tree=claim_tree,
        summaries=summaries,
        nums=ordered,
    )
    dest = note_dir / f"{claim_anchor_basename(pub)}.md"
    note_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(note_body, encoding="utf-8")

    content = wikilink_claim_citations(content, pub=pub)
    content = ensure_claim_anchors_nav(content, pub=pub)
    return content, dest, ordered


def build_figure_label_map(insert_figs: list[dict]) -> dict[int, dict]:
    """图号 → 优先选用的 figure 记录。"""
    out: dict[int, dict] = {}
    for fig in insert_figs or []:
        label = str(fig.get("label") or "")
        m = re.search(r"图\s*(\d+)", label) or re.search(
            r"图(\d+)", str(fig.get("filename") or "")
        )
        if not m:
            continue
        num = int(m.group(1))
        prev = out.get(num)
        if prev is None:
            out[num] = fig
            continue

        def score(f: dict) -> tuple:
            st = (f.get("quality_signals") or {}).get("status") or ""
            return (
                1 if st == "usable" else 0,
                1 if f.get("decision") == "insert" else 0,
                int(f.get("bytes") or 0),
            )

        if score(fig) > score(prev):
            out[num] = fig
    return out


def ensure_figure_headings(
    content: str, insert_figs: list[dict] | None = None
) -> str:
    """保证第六节/附图区每个图有 `### 图N` + 嵌入。"""
    label_map = build_figure_label_map(insert_figs or [])

    def add_heading_before_embed(text: str) -> str:
        def repl(m: re.Match[str]) -> str:
            embed = m.group(0)
            fname = m.group(1)
            num_m = re.search(r"图(\d+)", fname)
            if not num_m:
                return embed
            num = int(num_m.group(1))
            start = m.start()
            lookback = text[max(0, start - 80) : start]
            if re.search(rf"###\s*图\s*{num}\s*$", lookback, re.M):
                return embed
            return f"### 图{num}\n\n{embed}"

        return re.sub(
            r"!\[\[(?:images/)?([^\]]*?图\d+[^\]]*?)\]\]",
            repl,
            text,
        )

    content = add_heading_before_embed(content)
    existing = {int(x) for x in re.findall(r"^###\s*图\s*(\d+)\s*$", content, re.M)}
    missing = sorted(set(label_map) - existing)
    if not missing:
        return content

    lines: list[str] = []
    for num in missing:
        fig = label_map[num]
        fname = fig.get("filename") or ""
        page = fig.get("page") or fig.get("page_number")
        cap = f"图{num}" + (f"（第 {page} 页）" if page else "")
        lines.extend(
            [
                f"### 图{num}",
                "",
                f"![[images/{fname}]]",
                f"*{cap}*",
                "",
            ]
        )
    block = "\n".join(lines)
    m = re.search(r"^###\s*附图\s*$", content, re.M)
    if m:
        insert_at = m.end()
        rest = content[insert_at:]
        tip = re.match(r"\n*> \[!tip\][\s\S]*?(?:\n\n|\Z)", rest)
        if tip:
            insert_at += tip.end()
        return content[:insert_at] + "\n" + block + content[insert_at:]
    m6 = re.search(r"^##\s*六、.*$", content, re.M)
    if m6:
        end = content.find("\n## ", m6.end())
        if end == -1:
            return content.rstrip() + "\n\n" + block
        return content[:end] + "\n" + block + content[end:]
    return content.rstrip() + "\n\n" + block


def escape_wikilink_pipes_in_tables(content: str) -> str:
    """表格单元格内 wikilink 的「|别名」必须写成「\\|」。"""
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip(">").lstrip()
        if not stripped.startswith("|") or "[[" not in line:
            out.append(line)
            continue
        parts: list[str] = []
        i = 0
        while i < len(line):
            if line.startswith("[[", i):
                j = line.find("]]", i)
                if j < 0:
                    parts.append(line[i:])
                    break
                chunk = line[i : j + 2]
                chunk = re.sub(r"(?<!\\)\|", r"\\|", chunk)
                parts.append(chunk)
                i = j + 2
            else:
                parts.append(line[i])
                i += 1
        out.append("".join(parts))
    return "".join(out)


def enhance_note_citations(
    content: str,
    *,
    pub: str = "",
    note_dir: Path | None = None,
    claim_tree: dict | None = None,
    claim_summaries: dict[int, str] | None = None,
    insert_figs: list[dict] | None = None,
) -> tuple[str, Path | None, list[int]]:
    """图标题 + 权/图引用改写 + 旁路权项锚点笔记。

    返回 (content, claim_anchors_path|None, claim_nums)。
    """
    content = ensure_figure_headings(content, insert_figs)
    content = wikilink_figure_citations(content)
    claim_path: Path | None = None
    claim_nums: list[int] = []
    if pub and note_dir is not None:
        content, claim_path, claim_nums = materialize_claim_anchors(
            content,
            pub=pub,
            note_dir=note_dir,
            claim_tree=claim_tree,
            summaries=claim_summaries,
        )
    else:
        content = wikilink_claim_citations(content, pub=pub)
    return content, claim_path, claim_nums
