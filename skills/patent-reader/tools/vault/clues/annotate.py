"""把线索旁注注入解读笔记各节（导航入口、权项、术语、特征、差别、建议、场景）。"""
from __future__ import annotations

import re

from .matching import (
    _claim_key_to_num,
    _clue_highlight,
    _distinct_clue_lines,
    _term_match_tokens,
    clue_highlight_for_feature,
    clue_highlight_for_text,
    feature_clue_affinity,
    feature_display_name,
    harvest_claim_bodies,
    harvest_feature_entries,
    match_clue_to_note,
    resolve_feature_entry,
)
from .model import _clue_link, _clue_stem, agent_fits_for
from .vocab import DEFAULT_MAX_CLUES


def _strip_injected_clue_blocks(content: str) -> str:
    """幂等：去掉先前 L1–L3 注入的线索旁注/入口。"""
    titles = (
        "公开线索入口",
        "公开线索",
        "公开案例（推测）",
        "外部线索（推测）",
        "权项—公开语境（推测）",
        "特征—公开语境（推测）",
        "阅读建议·公开线索",
        "差别对照·公开线索",
        "场景·公开线索",
        "术语·公开语境",
    )
    for title in titles:
        content = re.sub(
            rf"\n?>\s*\[!(?:warning|tip)\]-?\s*{re.escape(title)}[\s\S]*?"
            rf"(?=\n##\s|\n###\s|\n>\s*\[!|\Z)",
            "\n",
            content,
        )
    content = re.sub(
        r"^[ \t]*-\s*\[\[[^\]]*clues/_线索索引[^\]]*\]\][^\n]*\n?",
        "",
        content,
        flags=re.M,
    )
    return content


def _insert_before_heading(content: str, heading_pat: str, block: str) -> str:
    m = re.search(heading_pat, content, re.M)
    if not m:
        return content
    return content[: m.start()].rstrip() + "\n\n" + block.strip() + "\n\n" + content[m.start() :]


def _insert_after_section(content: str, section_re: re.Pattern[str], block: str) -> str:
    m = section_re.search(content)
    if not m:
        return content
    end = m.end()
    return content[:end].rstrip() + "\n\n" + block.strip() + "\n\n" + content[end:]


def _render_warning(title: str, body_lines: list[str]) -> str:
    lines = [f"> [!warning]- {title}", ">"]
    for ln in body_lines:
        lines.append(f"> {ln}" if ln else ">")
    return "\n".join(lines)


def _insert_after_section6_feature_table(content: str, block: str) -> str:
    """插在第六节对照表正下方（附图/扫描预览之前），避免沉到节末看不见。"""
    sec = re.search(
        r"(^##\s*六、[^\n]*\n)([\s\S]*?)(?=^##\s*七、|\Z)",
        content,
        re.M,
    )
    if not sec:
        if re.search(r"^##\s*七、", content, re.M):
            return _insert_before_heading(content, r"^##\s*七、", block)
        return content.rstrip() + "\n\n" + block.strip() + "\n"

    head, body = sec.group(1), sec.group(2)
    # 节内第一张 markdown 表（特征|说明书|附图）
    m_table = re.search(
        r"(\|[^\n]+\|\n\|[-: |]+\|\n(?:\|[^\n]+\|\n)+)",
        body,
    )
    if m_table:
        insert_at = sec.start(2) + m_table.end()
        return (
            content[:insert_at].rstrip()
            + "\n\n"
            + block.strip()
            + "\n\n"
            + content[insert_at:].lstrip("\n")
        )
    # 无表则插在「### 附图」前，再不行节末（七之前）
    m_fig = re.search(r"^###\s*附图", body, re.M)
    if m_fig:
        insert_at = sec.start(2) + m_fig.start()
        return (
            content[:insert_at].rstrip()
            + "\n\n"
            + block.strip()
            + "\n\n"
            + content[insert_at:]
        )
    return _insert_before_heading(content, r"^##\s*七、", block)


def inject_clue_annotations(content: str, clues: list[dict]) -> str:
    """L1–L3：导航入口 + 一/二/七/八/九语境旁注 + 权/特征点对点；L4 附录由 upsert_appendix_b。"""
    if not clues:
        return content
    content = _strip_injected_clue_blocks(content)
    n = len(clues)
    primary = clues[0]
    distinct_l2 = _distinct_clue_lines(clues, limit=3)

    # —— L1：导航 + 文首入口 ——
    nav_item = f"[[clues/_线索索引|公开线索（{n} 条）]]"
    if "## Obsidian 导航" in content and f"公开线索（{n} 条）" not in content:
        content = re.sub(
            r"(##\s*Obsidian\s*导航\s*\n(?:- .+\n)*)",
            rf"\1- {nav_item}\n",
            content,
            count=1,
        )
    l1 = (
        f"> [!tip]- 公开线索入口\n"
        f"> 本案整理了 **{n}** 条公开检索线索（推测语境）。"
        f"详见 [[clues/_线索索引|线索文件夹]]；"
        f"下文各节有折叠旁注，**不是**说明书/权利要求证据。"
    )
    if "公开线索入口" not in content:
        content = _insert_before_heading(content, r"^##\s*一、", l1)

    # —— L2：氛围旁注（各节角度不同，避免同一摘要首句跨节刷屏）——
    l2_one = _render_warning(
        "公开案例（推测）",
        [
            "进入正文前可先扫一眼公开语境（**不能**等同保护范围）：",
            *(distinct_l2[:1] or [f"- {_clue_link(primary)}"]),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*二、", l2_one)

    l2_two_body = [
        "叙事对照：下列为公开材料各自强调的要点；本案以**权要/说明书**为准。",
        *(distinct_l2[:3] or [f"- {_clue_link(c)}" for c in clues[:3]]),
    ]
    l2_two = _render_warning("公开案例（推测）", l2_two_body)
    content = _insert_before_heading(content, r"^##\s*三、", l2_two)

    l2_seven = _render_warning(
        "差别对照·公开线索",
        [
            "对照公开话术时：分清哪些差别来自**专利文本**，哪些只是行业语境。",
            "线索入口：[[clues/_线索索引|线索文件夹]]"
            + (" · " + " · ".join(_clue_link(c) for c in clues[:3]) if clues else ""),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*八、", l2_seven)

    l2_eight = _render_warning(
        "阅读建议·公开线索",
        [
            "建议打开 [[clues/_线索索引|线索文件夹]] 扫摘要，再回看权1骨架与特征表。",
            "详细贴合点见第四节权项旁注、第六节「特征—公开语境」。",
        ],
    )
    content = _insert_before_heading(content, r"^##\s*九、", l2_eight)

    l2_nine = _render_warning(
        "场景·公开线索",
        [
            "应用场景的专利内依据见上表；公开线索仅补充同主题落地/产品语境。",
            " · ".join(_clue_link(c) for c in clues[:3]),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*十、", l2_nine)

    # —— L3：权项点对点（优先 Agent anchor_fits；否则按权正文启发式）——
    claim_bodies = harvest_claim_bodies(content)
    claim_groups: dict[int, list[dict]] = {}
    for c in clues:
        claim_nums: set[int] = set()
        for num in c.get("related_claims") or []:
            try:
                claim_nums.add(int(num))
            except (TypeError, ValueError):
                continue
        for key, _fit in agent_fits_for(c, "claim"):
            n = _claim_key_to_num(key)
            if n:
                claim_nums.add(n)
        for num in claim_nums:
            claim_groups.setdefault(num, []).append(c)
    # 从后往前插，避免偏移
    for num, group in sorted(claim_groups.items(), reverse=True):
        # 去重同一线索
        uniq_group: list[dict] = []
        seen_stem: set[str] = set()
        for c in group:
            st = _clue_stem(c)
            if st in seen_stem:
                continue
            seen_stem.add(st)
            uniq_group.append(c)
        anchor = claim_bodies.get(num, f"权利要求{num}")
        body = [
            f"与**权利要求 {num}** 弱匹配的公开语境（非权要证据）；"
            f"贴合句优先来自 Agent 读页归纳：",
        ]
        seen_hl: set[str] = set()
        for c in uniq_group[:3]:
            agent_hl = next(
                (
                    fit
                    for key, fit in agent_fits_for(c, "claim")
                    if _claim_key_to_num(key) == num
                ),
                "",
            )
            if agent_hl:
                hl, specific = agent_hl[:52], True
            else:
                hl, specific = clue_highlight_for_text(c, anchor, limit=52)
            if specific and hl:
                key = re.sub(r"\s+", "", hl)[:20]
                if key in seen_hl:
                    body.append(f"- {_clue_link(c)}")
                else:
                    seen_hl.add(key)
                    body.append(f"- {_clue_link(c)} — {hl}")
            else:
                body.append(
                    f"- {_clue_link(c)} — 同主题语境（摘要未点名该权项）"
                )
        block = _render_warning("权项—公开语境（推测）", body)
        pat = re.compile(
            rf"(>\s*\[!patent-claim\]\s*权利要求\s*{num}\b[\s\S]*?)(?=\n>\s*\[!patent-claim\]|\n##\s|\n\| 特征 \||\Z)",
            re.M,
        )
        m = pat.search(content)
        if m:
            content = content[: m.end()].rstrip() + "\n\n" + block + "\n\n" + content[m.end() :]
        else:
            pass

    # 若完全没插到权 callout，保留总览挂在第四节末
    if "权项—公开语境（推测）" not in content:
        overview = render_annotation_callout(clues)
        if overview:
            content = _insert_before_heading(content, r"^##\s*五、", overview.strip())

    # —— L3：特征公开语境 → 紧挨第六节对照表下方（附图之前）——
    # 优先 Agent anchor_fits；无则启发式。按线索去重呈现。
    catalog = harvest_feature_entries(content)
    # stem -> {clue, pairs: [(score, ent, hl, specific)]}
    clue_buckets: dict[str, dict] = {}
    for c in clues:
        stem = _clue_stem(c)
        bucket = clue_buckets.setdefault(stem, {"clue": c, "pairs": []})
        agent_feat = agent_fits_for(c, "feature")
        if agent_feat:
            for key, fit in agent_feat[:6]:
                ent = resolve_feature_entry(str(key), catalog)
                if not ent:
                    # Agent 已点名：即使当前表无完全同名行，仍展示贴合句
                    ent = {
                        "id": "",
                        "label": str(key)[:40],
                        "text": str(key),
                    }
                bucket["pairs"].append((100, ent, fit[:52], True))
            continue
        keys = list(c.get("related_feature_ids") or [])
        if not keys and c.get("related_features"):
            keys = [str(x) for x in c.get("related_features")[:2]]
        resolved: list[dict] = []
        for key in keys:
            ent = resolve_feature_entry(str(key), catalog)
            if ent:
                resolved.append(ent)
        if not resolved and catalog:
            live = match_clue_to_note(c, feature_entries=catalog)
            for key in live.get("related_feature_ids") or []:
                ent = resolve_feature_entry(str(key), catalog)
                if ent:
                    resolved.append(ent)
        seen_disp: set[str] = set()
        for ent in resolved:
            disp = feature_display_name(ent)
            if disp in seen_disp:
                continue
            seen_disp.add(disp)
            sc = feature_clue_affinity(ent, c)
            hl, specific = clue_highlight_for_feature(c, ent, limit=52)
            bucket["pairs"].append((sc, ent, hl if specific else "", specific))
    clue_buckets = {k: v for k, v in clue_buckets.items() if v.get("pairs")}
    if clue_buckets:
        lines = [
            "按**公开线索**归纳（每条只出现一次）；贴合句优先来自 Agent 读页归纳，否则启发式抽取。",
            "仅供语境理解，**不是**说明书/权利要求证据。",
            "",
        ]
        for stem, bucket in list(clue_buckets.items())[:DEFAULT_MAX_CLUES]:
            c = bucket["clue"]
            pairs = sorted(
                bucket["pairs"], key=lambda x: (-x[0], feature_display_name(x[1]))
            )
            # 每条线索最多展开 3 条有专属贴合句的特征；其余收进「另涉」
            specific_rows = [
                (sc, ent, hl) for sc, ent, hl, sp in pairs if sp and sc >= 2
            ][:3]
            specific_names = {feature_display_name(e) for _, e, _ in specific_rows}
            other = [
                feature_display_name(ent)
                for _sc, ent, _hl, _sp in pairs
                if feature_display_name(ent) not in specific_names
            ][:6]
            lines.append(f"**{_clue_link(c, (c.get('title') or '')[:28])}**")
            if specific_rows:
                for _sc, ent, hl in specific_rows:
                    lines.append(f"- **{feature_display_name(ent)}** — {hl}")
                if other:
                    lines.append("- 另涉（同主题、摘要未点名）：" + "；".join(other))
            elif pairs:
                lines.append(f"- 同主题语境：{_clue_highlight(c, limit=48)}")
                names = "；".join(
                    feature_display_name(ent) for _sc, ent, _hl, _sp in pairs[:5]
                )
                lines.append(f"- 相关特征：{names}")
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        feat_block = _render_warning("特征—公开语境（推测）", lines)
        content = _insert_after_section6_feature_table(content, feat_block)

    # —— L2 补充：术语节（按线索去重 + 术语贴合句）——
    sec5 = re.search(r"^##\s*五、专利内术语表([\s\S]*?)(?=^##\s*六、|\Z)", content, re.M)
    if sec5:
        terms = re.findall(r"\|\s*\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", sec5.group(1))
        if not terms:
            terms = [
                m.group(1).strip()
                for m in re.finditer(
                    r"^\|\s*([^|]+?)\s*\|", sec5.group(1), re.M
                )
                if m.group(1).strip()
                and not re.match(r"^[-:]+$", m.group(1).strip())
                and m.group(1).strip() not in ("术语", "本文含义/位置", "备注")
            ]
        term_buckets: dict[str, dict] = {}
        # 先吃 Agent 术语贴合
        for c in clues:
            agent_terms = agent_fits_for(c, "term")
            if not agent_terms:
                continue
            stem = _clue_stem(c)
            bucket = term_buckets.setdefault(stem, {"clue": c, "rows": []})
            for key, fit in agent_terms[:6]:
                # 尽量对齐笔记术语表用词
                matched = next(
                    (t for t in terms if t == key or key in t or t in key),
                    key,
                )
                if matched not in terms and key not in terms:
                    # 仍展示 Agent 点名的术语
                    matched = key
                bucket["rows"].append((matched, fit[:44], True))
        # 无 Agent 术语贴合时，启发式共现
        if not term_buckets:
            for term in terms[:12]:
                tokens = _term_match_tokens(term)
                if not tokens:
                    continue
                for c in clues:
                    blob = f"{c.get('title')} {c.get('summary')} {c.get('reason')}"
                    if not any(t in blob for t in tokens):
                        continue
                    stem = _clue_stem(c)
                    bucket = term_buckets.setdefault(stem, {"clue": c, "rows": []})
                    hl, specific = clue_highlight_for_text(c, term, limit=44)
                    bucket["rows"].append((term, hl if specific else "", specific))
                    break
        if term_buckets:
            lines = [
                "按线索归纳术语共现（推测）；贴合句优先来自 Agent 读页归纳。",
                "",
            ]
            for stem, bucket in list(term_buckets.items())[:DEFAULT_MAX_CLUES]:
                c = bucket["clue"]
                lines.append(f"**{_clue_link(c, (c.get('title') or '')[:28])}**")
                specific_rows = [(t, hl) for t, hl, sp in bucket["rows"] if sp][:4]
                other = [t for t, hl, sp in bucket["rows"] if not sp][:6]
                for t, hl in specific_rows:
                    lines.append(f"- **{t}** — {hl}")
                if other:
                    if specific_rows:
                        lines.append("- 另涉：" + "；".join(other))
                    else:
                        lines.append(
                            f"- 同主题语境：{_clue_highlight(c, limit=40)}"
                        )
                        lines.append("- 相关术语：" + "；".join(other))
                lines.append("")
            while lines and lines[-1] == "":
                lines.pop()
            term_block = _render_warning("术语·公开语境", lines)
            content = _insert_before_heading(content, r"^##\s*六、", term_block)

    return content


def render_annotation_callout(clues: list[dict]) -> str:
    matched = [
        c
        for c in clues
        if c.get("related_claims")
        or c.get("related_features")
        or c.get("related_feature_ids")
    ]
    if not matched:
        matched = list(clues)
    if not matched:
        return ""
    lines = [
        "",
        "> [!warning]- 外部线索（推测）",
        "> 下列公开线索与权项/特征有**弱匹配**，仅供理解语境，**不是**说明书依据。",
        "> （每条线索一行；详细贴合见权项/特征旁注。）",
    ]
    seen_hl: set[str] = set()
    for c in matched:
        bits: list[str] = []
        if c.get("related_claims"):
            bits.append("权" + "、".join(str(n) for n in c["related_claims"]))
        fids = c.get("related_feature_ids") or []
        if fids:
            bits.append("特征 " + "、".join(str(x) for x in fids[:4]))
        elif c.get("related_features"):
            bits.append("特征共现：" + "；".join(c["related_features"][:2]))
        hl = _clue_highlight(c, limit=40)
        key = re.sub(r"\s+", "", hl)[:18]
        if key and key in seen_hl:
            hl = ""
        elif key:
            seen_hl.add(key)
        tail = " · ".join(bits) if bits else (hl or "同主题语境")
        if bits and hl:
            tail = f"{' · '.join(bits)} — {hl}"
        lines.append(f"> - {_clue_link(c)} — {tail}")
    lines.append("")
    return "\n".join(lines)
