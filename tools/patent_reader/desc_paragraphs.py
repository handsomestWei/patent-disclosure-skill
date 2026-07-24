"""说明书段落锚点：解析 [000N]、生成旁路笔记、改写为可悬停预览的 wikilink。

约定：
- 展示：说明书 0002 / 说明书 0002–0004（区间为**一条**链接）
- 单段：[[{pub}_说明书段落#^p0002|说明书 0002]]
- 区间：[[{pub}_说明书段落#^r0002-0004|说明书 0002–0004]]
- 锚点笔记用块 ID，便于 Obsidian「页面预览」悬停浮出正文
- 默认仅含本解读引用到的段落
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CN_PARA_SPLIT_RE = re.compile(r"\[(\d{4})\]")
# 旧写法：[0002] 或 [0002]–[0004]
BRACKET_CITE_RE = re.compile(
    r"\[(\d{4})\](?:\s*[–—\-]\s*\[(\d{4})\])?"
)
# 新写法（未链）：说明书 0002 或 说明书 0002–0004
PLAIN_CITE_RE = re.compile(
    r"(?<!\[\[)(?<!\|)说明书\s*(\d{4})(?:\s*[–—\-]\s*(\d{4}))?(?!\]])"
)
# 已有 wikilink（标题锚或块锚）
WIKILINK_CITE_RE = re.compile(
    r"\[\[[^\]]*?_说明书段落#(?:\^p)?(\d{4})\|[^\]]*\]\]"
    r"|\[\[[^\]]*?_说明书段落#\^r(\d{4})-(\d{4})\|[^\]]*\]\]"
)
# 旧版区间双链 → 合并为单链（入库幂等升级）
SPLIT_RANGE_WIKILINK_RE = re.compile(
    r"\[\[[^\]]*?_说明书段落#(?:\^p)?(\d{4})\|说明书\s*\1\]\]"
    r"\s*[–—\-]\s*"
    r"\[\[[^\]]*?_说明书段落#(?:\^p)?(\d{4})\|(?:说明书\s*)?\2\]\]"
)
# 旧版单链标题锚 → 块锚
OLD_SINGLE_WIKILINK_RE = re.compile(
    r"\[\[([^\]]*?_说明书段落)#(?!\^)(\d{4})\|(说明书\s*\2)\]\]"
)
PAGE_NOISE_RE = re.compile(
    r"(?:说\s*明\s*书\s*\d+\s*/\s*\d+\s*页)"
    r"|(?:权\s*利\s*要\s*求\s*书\s*\d+\s*/\s*\d+\s*页)"
    r"|(?:CN\s*\d{8,}\s*[A-Z]?)"
    r"|(?:^\d{1,2}\s*$)",
    re.M,
)


def clean_paragraph_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").strip()
    t = PAGE_NOISE_RE.sub("", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def split_cn_description_paragraphs(text: str) -> dict[str, str]:
    """从全文或说明书区提取官方段落号 → 正文。"""
    if not text:
        return {}
    matches = list(CN_PARA_SPLIT_RE.finditer(text))
    if not matches:
        return {}
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = clean_paragraph_text(text[start:end])
        if not body:
            continue
        prev = out.get(num, "")
        if len(body) > len(prev):
            out[num] = body
    return out


def description_text_from_raw_sections(raw_sections_path: Path) -> str:
    if not raw_sections_path.is_file():
        return ""
    chunks: list[str] = []
    with raw_sections_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("kind") in ("description", "description_para"):
                chunks.append(obj.get("text") or "")
    return "\n\n".join(chunks)


def load_description_paragraphs(workdir: Path | None) -> dict[str, str]:
    """优先 description_paragraphs.json，否则从 raw_sections.jsonl 解析。"""
    if workdir is None:
        return {}
    jp = workdir / "description_paragraphs.json"
    if jp.is_file():
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            paras = data.get("paragraphs") if "paragraphs" in data else data
            if isinstance(paras, dict):
                return {
                    str(k).zfill(4)[-4:]: clean_paragraph_text(str(v))
                    for k, v in paras.items()
                    if re.fullmatch(r"\d{1,4}", str(k)) and str(v).strip()
                }
    raw = workdir / "raw_sections.jsonl"
    return split_cn_description_paragraphs(description_text_from_raw_sections(raw))


def write_description_paragraphs_json(
    out_path: Path, paragraphs: dict[str, str], *, pub: str = ""
) -> Path:
    payload = {
        "pub_number": pub,
        "count": len(paragraphs),
        "paragraphs": {k: paragraphs[k] for k in sorted(paragraphs)},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path


def _protect_zones(content: str) -> tuple[str, list[str]]:
    """暂时替换 fenced code / 已有 wikilink，避免二次改写。"""
    vault: list[str] = []

    def stash(m: re.Match[str]) -> str:
        vault.append(m.group(0))
        return f"\x00PD{len(vault) - 1}\x00"

    tmp = re.sub(r"```[\s\S]*?```", stash, content)
    tmp = re.sub(r"\[\[[^\]]+\]\]", stash, tmp)
    return tmp, vault


def _restore_zones(content: str, vault: list[str]) -> str:
    def unstash(m: re.Match[str]) -> str:
        return vault[int(m.group(1))]

    return re.sub(r"\x00PD(\d+)\x00", unstash, content)


def _expand_range(a: str, b: str | None) -> list[str]:
    if not b or b == a:
        return [a]
    lo, hi = int(a), int(b)
    if lo > hi or hi - lo > 50:
        return [a, b]
    return [f"{n:04d}" for n in range(lo, hi + 1)]


def parse_cited_ranges(content: str) -> list[tuple[str, str | None]]:
    """返回引用列表 [(start, end|None), ...]，去重保序。"""
    out: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()

    def add(a: str, b: str | None) -> None:
        key = (a, b if b and b != a else None)
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    for m in SPLIT_RANGE_WIKILINK_RE.finditer(content):
        add(m.group(1), m.group(2))
    for m in WIKILINK_CITE_RE.finditer(content):
        if m.group(1):
            add(m.group(1), None)
        elif m.group(2) and m.group(3):
            add(m.group(2), m.group(3))
    for m in BRACKET_CITE_RE.finditer(content):
        add(m.group(1), m.group(2))
    for m in PLAIN_CITE_RE.finditer(content):
        add(m.group(1), m.group(2))
    return out


def parse_cited_paragraph_numbers(content: str) -> list[str]:
    """从笔记中收集被引用的段落号（展开区间）。"""
    found: set[str] = set()
    for a, b in parse_cited_ranges(content):
        found.update(_expand_range(a, b))
    return sorted(found)


def paragraph_anchor_basename(pub: str) -> str:
    try:
        from common import slugify_pub
    except ImportError:
        from tools.patent_reader.common import slugify_pub

    return f"{slugify_pub(pub)}_说明书段落"


def _para_body(paragraphs: dict[str, str], num: str) -> str:
    return paragraphs.get(num) or paragraphs.get(num.lstrip("0") or "0") or ""


def render_paragraph_anchor_note(
    *,
    pub: str,
    paragraphs: dict[str, str],
    cited: list[str],
    ranges: list[tuple[str, str]] | None = None,
) -> str:
    """生成锚点笔记：单段 ### + ^p；区间另设合并节 + ^r（供悬停一次看全）。"""
    lines = [
        "---",
        "tags:",
        "  - patent/description-paragraphs",
        f"pub_number: {pub}",
        "cssclasses:",
        "  - patent-reader",
        "---",
        f"# {pub} 说明书段落",
        "",
        "## 使用说明",
        "",
        "1. **设置**：Obsidian → 设置 → 核心插件 → **页面预览（Page preview）** → 打开",
        "2. **使用**：在解读笔记中，**按住 Ctrl** 再将鼠标悬停在「说明书 …」链接上，即可预览本段原文；单击仍可跳转至此。",
        "",
        "> 本页默认仅含解读笔记中引用到的段落；区间引用另见下方「区间」节。",
        "",
        "## 单段",
        "",
    ]
    for num in cited:
        body = _para_body(paragraphs, num)
        if not body:
            body = "（原文未解析到该段，请对照官方 PDF。）"
        lines.extend(
            [
                f"### {num}",
                "",
                body,
                "",
                f"^p{num}",
                "",
            ]
        )

    range_list = ranges or []
    if range_list:
        lines.extend(["## 区间（悬停预览用）", ""])
        for start, end in range_list:
            if start == end:
                continue
            nums = _expand_range(start, end)
            lines.extend([f"### {start}–{end}", ""])
            for num in nums:
                body = _para_body(paragraphs, num) or "（缺）"
                lines.extend([f"**{num}**", "", body, ""])
            lines.extend([f"^r{start}-{end}", ""])

    return "\n".join(lines).rstrip() + "\n"


def _link_single(pub: str, num: str) -> str:
    base = paragraph_anchor_basename(pub)
    return f"[[{base}#^p{num}|说明书 {num}]]"


def _link_range(pub: str, start: str, end: str) -> str:
    base = paragraph_anchor_basename(pub)
    return f"[[{base}#^r{start}-{end}|说明书 {start}–{end}]]"


def format_citation_wikilinks(pub: str, start: str, end: str | None = None) -> str:
    if not end or end == start:
        return _link_single(pub, start)
    return _link_range(pub, start, end)


def upgrade_legacy_citation_wikilinks(content: str, *, pub: str) -> str:
    """把旧双链/旧标题锚升级为块锚单链。"""

    def repl_split(m: re.Match[str]) -> str:
        return format_citation_wikilinks(pub, m.group(1), m.group(2))

    def repl_old_single(m: re.Match[str]) -> str:
        return _link_single(pub, m.group(2))

    out = SPLIT_RANGE_WIKILINK_RE.sub(repl_split, content)
    out = OLD_SINGLE_WIKILINK_RE.sub(repl_old_single, out)
    return out


def wikilink_description_citations(content: str, *, pub: str) -> str:
    """将 [0002]/说明书 0002 等改写为可预览 wikilink。"""
    content = upgrade_legacy_citation_wikilinks(content, pub=pub)
    protected, vault = _protect_zones(content)

    def repl_bracket(m: re.Match[str]) -> str:
        return format_citation_wikilinks(pub, m.group(1), m.group(2))

    def repl_plain(m: re.Match[str]) -> str:
        return format_citation_wikilinks(pub, m.group(1), m.group(2))

    out = BRACKET_CITE_RE.sub(repl_bracket, protected)
    out = PLAIN_CITE_RE.sub(repl_plain, out)
    return _restore_zones(out, vault)


def ensure_desc_paragraphs_nav(content: str, *, pub: str) -> str:
    """在 Obsidian 导航列表中补说明书段落入口（无括号说明；用法见该笔记正文）。"""
    base = paragraph_anchor_basename(pub)
    needle = f"[[{base}|说明书段落]]"
    # 去掉历史括号说明
    content = re.sub(
        rf"(-\s*\[\[{re.escape(base)}\|[^\]]*\]\])（[^）\n]*）",
        r"\1",
        content,
    )
    if needle in content or f"{base}|" in content:
        return content
    m = re.search(r"(##\s*Obsidian 导航\s*\n)([\s\S]*?)(?=\n##\s|\n> \[!|\Z)", content)
    if not m:
        return content
    block = m.group(2)
    if not block.strip().startswith("-"):
        return content
    lines = block.rstrip().splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if "图谱" in line or "canvas" in line.lower():
            insert_at = i + 1
            break
    lines.insert(insert_at, f"- {needle}")
    new_block = "\n".join(lines) + "\n"
    return content[: m.start(2)] + new_block + content[m.end(2) :]


def materialize_description_paragraphs(
    *,
    content: str,
    pub: str,
    note_dir: Path,
    paragraphs: dict[str, str],
    cited_only: bool = True,
) -> tuple[str, Path | None, list[str]]:
    """生成锚点笔记并改写正文引用。返回 (new_content, path|None, cited_nums)。"""
    ranges_raw = parse_cited_ranges(content)
    # 也解析升级前的旧双链
    content_for_parse = content
    cited = parse_cited_paragraph_numbers(content_for_parse)
    ranges = [(a, b) for a, b in ranges_raw if b and b != a]

    if not cited and not paragraphs:
        return content, None, []
    if cited_only:
        if not cited:
            content2 = wikilink_description_citations(content, pub=pub)
            content2 = ensure_desc_paragraphs_nav(content2, pub=pub)
            return content2, None, []
        selected = cited
    else:
        selected = sorted(set(cited) | set(paragraphs))

    note_body = render_paragraph_anchor_note(
        pub=pub,
        paragraphs=paragraphs,
        cited=selected,
        ranges=ranges,
    )
    dest = note_dir / f"{paragraph_anchor_basename(pub)}.md"
    note_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(note_body, encoding="utf-8")

    content2 = wikilink_description_citations(content, pub=pub)
    content2 = ensure_desc_paragraphs_nav(content2, pub=pub)
    return content2, dest, selected
