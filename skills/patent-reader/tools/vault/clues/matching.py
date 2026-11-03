"""线索 ↔ 权项 / 特征 / 术语的弱匹配与贴合句抽取（推测层，非说明书证据）。"""
from __future__ import annotations

import re

from .model import _clue_link
from .summary import sanitize_clue_summary
from .vocab import FEATURE_LABEL_STOPWORDS, FEATURE_SYNONYMS, TOKEN_STOPWORDS


SECTION4_RE = re.compile(
    r"(^##\s*四、独立权利要求精读[\s\S]*?)(?=^##\s*五、|\Z)",
    re.M,
)


SECTION6_RE = re.compile(
    r"(^##\s*六、[\s\S]*?)(?=^##\s*七、|\Z)",
    re.M,
)


def _tokenize(text: str) -> set[str]:
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9\-]{2,}", text or "")
    return {p for p in parts if p not in TOKEN_STOPWORDS and len(p) >= 2}


def _term_match_tokens(term: str) -> list[str]:
    """术语共现匹配：整词 + 连续汉字二元组（避免「陶瓷涂层」整词过严）。"""
    term = (term or "").strip()
    if not term:
        return []
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", term))
    tokens: list[str] = [term]
    if len(chars) >= 2:
        if chars != term:
            tokens.append(chars)
        tokens.extend(chars[i : i + 2] for i in range(len(chars) - 1))
    tokens.extend(re.findall(r"[A-Za-z0-9]{2,}", term))
    return list(dict.fromkeys(t for t in tokens if len(t) >= 2))


def harvest_feature_rows(content: str) -> list[str]:
    return [e["text"] for e in harvest_feature_entries(content)]


def harvest_feature_entries(content: str) -> list[dict]:
    """从第四节/第六节表收集特征行；优先识别 F1、F2… 编号。"""
    entries: list[dict] = []
    seen: set[str] = set()
    for sec_re in (SECTION4_RE, SECTION6_RE):
        m = sec_re.search(content or "")
        block = m.group(1) if m else ""
        for line in block.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or cells[0] in ("特征", "---") or re.match(r"^[-:]+$", cells[0]):
                continue
            head = cells[0]
            fm = re.match(r"^(F\d+)\s*(.*)$", head, re.I)
            fid = fm.group(1).upper() if fm else ""
            label = (fm.group(2).strip() if fm else head)[:40]
            text = " ".join(cells)
            key = fid or text[:48]
            if key in seen:
                continue
            seen.add(key)
            entries.append({"id": fid, "label": label or head, "text": text})
    return entries


def feature_display_name(ent: dict) -> str:
    """旁注展示名：有 F 编号则「F1 标签」，否则用对照表特征名。"""
    fid = (ent.get("id") or "").strip()
    label = (ent.get("label") or "").strip()
    if fid and label:
        return f"{fid} {label}"
    return fid or label or "特征"


def resolve_feature_entry(key: str, catalog: list[dict]) -> dict | None:
    """把 related_feature_ids 中的 F1 / 特征名 解析到笔记内真实特征行。"""
    key = (key or "").strip()
    if not key or not catalog:
        return None
    ku = key.upper()
    for e in catalog:
        if e.get("id") and str(e["id"]).upper() == ku:
            return e
    for e in catalog:
        lab = (e.get("label") or "").strip()
        if lab == key or key == feature_display_name(e):
            return e
    for e in catalog:
        lab = (e.get("label") or "").strip()
        if lab and (key in lab or lab in key):
            return e
    return None


def _label_hits_blob(label: str, blob: str) -> bool:
    """特征名与线索文本弱共现（含水系/水性等同义）。"""
    label = (label or "").strip()
    blob = blob or ""
    if not label or not blob:
        return False
    if label in blob:
        return True
    blob_l = blob.lower()
    for eng in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", label):
        if eng.lower() in blob_l:
            return True
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", label))
    for i in range(max(0, len(chars) - 1)):
        d = chars[i : i + 2]
        if d in FEATURE_LABEL_STOPWORDS:
            continue
        alts = FEATURE_SYNONYMS.get(d, (d,))
        if any(a in blob for a in alts):
            return True
    return False


def _clue_highlight(clue: dict, *, limit: int = 72) -> str:
    """取摘要首条要点或理由短句，供旁注。"""
    summary = sanitize_clue_summary(
        clue.get("summary") or "",
        title=clue.get("title") or "",
        reason=clue.get("reason") or "",
    )
    for ln in summary.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            return s[2:].strip()[:limit]
        if s and s != "页面要点：":
            return s[:limit]
    reason = (clue.get("reason") or "").strip()
    return reason[:limit] if reason else (clue.get("title") or "公开线索")


def _feature_anchor_tokens(ent: dict) -> list[str]:
    """特征名/行文本中用于贴合抽取的锚点词。"""
    label = (ent.get("label") or "").strip()
    text = (ent.get("text") or "").strip()
    tokens = _term_match_tokens(label)
    tokens.extend(_term_match_tokens(text))
    # 三字词（如「纤维素」「碱尿素」）比二元组更贴切
    for src in (label, text):
        chars = "".join(re.findall(r"[\u4e00-\u9fff]", src or ""))
        tokens.extend(chars[i : i + 3] for i in range(max(0, len(chars) - 2)))
    tokens.extend(re.findall(r"\d+(?:\.\d+)?(?:万|%|nm|μm|um|µm|mm)?", label, re.I))
    # 同义扩展，便于「涂覆」对上「涂布」
    expanded: list[str] = []
    for t in tokens:
        expanded.append(t)
        if t in FEATURE_SYNONYMS:
            expanded.extend(FEATURE_SYNONYMS[t])
        elif len(t) == 2 and t in FEATURE_SYNONYMS:
            expanded.extend(FEATURE_SYNONYMS[t])
    return list(dict.fromkeys(t for t in expanded if len(t) >= 2))[:36]


def _clue_snippet_pool(clue: dict, *, include_title: bool = False) -> list[str]:
    """线索可抽取短句池：只用摘要要点/分句做专属贴合（不用标题/理由抢分）。"""
    pool: list[str] = []
    summary = sanitize_clue_summary(
        clue.get("summary") or "",
        title=clue.get("title") or "",
        reason=clue.get("reason") or "",
    )
    for ln in summary.replace("\\n", "\n").splitlines():
        s = ln.strip()
        if s.startswith("- "):
            s = s[2:].strip()
        if not s or s.startswith("页面要点"):
            continue
        if len(s) <= 100:
            pool.append(s)
        for part in re.split(r"[。；;，,]", s):
            part = part.strip(" 　，,")
            if 8 <= len(part) <= 90:
                pool.append(part)
    if include_title:
        title = (clue.get("title") or "").strip()
        if title:
            pool.append(title)
    return list(dict.fromkeys(pool))


def _score_snippet_for_feature(snippet: str, tokens: list[str]) -> int:
    """命中分 − 长度惩罚，使更短、更贴特征的分句胜出。"""
    if not snippet or not tokens:
        return 0
    hits = 0
    weight = 0
    for t in tokens:
        if t in snippet:
            hits += 1
            weight += 5 if len(t) >= 3 else 2
            if re.search(r"\d", t):
                weight += 3
    if hits <= 0:
        return 0
    # 密度优先：同等命中偏好短句
    return weight * 10 + hits * 3 - min(len(snippet), 80)


def clue_highlight_for_feature(clue: dict, ent: dict, *, limit: int = 56) -> tuple[str, bool]:
    """按特征从线索摘要中抽一句贴合点。

    返回 (短句, 是否特征专属)。专属=摘要中命中该特征锚点；标题弱共现不算专属。
    """
    label = (ent.get("label") or "").strip()
    tokens = _feature_anchor_tokens(ent)
    best = ""
    best_score = 0
    for sn in _clue_snippet_pool(clue, include_title=False):
        sc = _score_snippet_for_feature(sn, tokens)
        if sc > best_score:
            best_score = sc
            best = sn
    if not best or best_score < 20:
        return "", False
    # 数值/尺寸类特征：摘要未出现数字或单位时，不算专属贴合
    nums = re.findall(r"\d+", label)
    if nums and not any(n in best for n in nums):
        if re.search(r"分子量|直径|粒径|厚度|孔隙|孔隙率|μm|um|nm|%|万", label, re.I):
            return "", False
    return best[:limit], True


def clue_highlight_for_text(clue: dict, text: str, *, limit: int = 56) -> tuple[str, bool]:
    """按任意锚点文本（权项摘要/术语名）从线索摘要抽贴合句（启发式降级）。"""
    text = (text or "").strip()
    if not text:
        return "", False
    return clue_highlight_for_feature(
        clue,
        {"id": "", "label": text[:48], "text": text[:240]},
        limit=limit,
    )


def _claim_key_to_num(key: str) -> int | None:
    m = re.search(r"\d+", str(key or ""))
    return int(m.group(0)) if m else None


def harvest_claim_bodies(content: str) -> dict[int, str]:
    """从第四节 patent-claim callout 抽取权号 → 正文短摘。"""
    out: dict[int, str] = {}
    for m in re.finditer(
        r">\s*\[!patent-claim\]\s*权利要求\s*(\d+)\b([\s\S]*?)(?=\n>\s*\[!patent-claim\]|\n##\s|\n\| 特征 \||\Z)",
        content or "",
        re.M,
    ):
        num = int(m.group(1))
        body = m.group(2)
        # 去掉引用前缀与空行，拼成一段
        bits: list[str] = []
        for ln in body.splitlines():
            s = ln.strip()
            if s.startswith(">"):
                s = s[1:].strip()
            if not s or s.startswith("[!"):
                continue
            bits.append(s)
        text = " ".join(bits)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out[num] = text[:320]
    return out


def _distinct_clue_lines(clues: list[dict], *, limit: int = 3, hl_limit: int = 42) -> list[str]:
    """多条线索各取一句不重复的摘要要点（供 L2 氛围旁注）。"""
    lines: list[str] = []
    seen: set[str] = set()
    for c in clues:
        hl = _clue_highlight(c, limit=hl_limit)
        key = re.sub(r"\s+", "", hl)[:18]
        if not key or key in seen:
            continue
        seen.add(key)
        lines.append(f"- {_clue_link(c, (c.get('title') or '')[:22])} — {hl}")
        if len(lines) >= limit:
            break
    return lines


def feature_clue_affinity(ent: dict, clue: dict) -> int:
    """特征↔线索相关度（越高越值得展开贴合句）。"""
    blob = " ".join(
        [
            clue.get("title") or "",
            clue.get("reason") or "",
            clue.get("summary") or "",
            clue.get("page_title") or "",
        ]
    )
    label = (ent.get("label") or "").strip()
    score = 0
    if _label_hits_blob(label, blob):
        score += 3
    overlap = _tokenize(ent.get("text") or label) & _tokenize(blob)
    score += min(4, len(overlap))
    nums = re.findall(r"\d+", label)
    if nums:
        if any(n in blob for n in nums):
            score += 4
        else:
            score -= 1
    _, specific = clue_highlight_for_feature(clue, ent)
    if specific:
        score += 3
    return score


def match_clue_to_note(
    clue: dict,
    *,
    claim_summaries: dict[int, str] | None = None,
    feature_rows: list[str] | None = None,
    feature_entries: list[dict] | None = None,
    extra_text: str = "",
) -> dict:
    """弱匹配：线索文本 ↔ 权项摘要 / 特征行（含 F1…）。"""
    blob = " ".join(
        [
            clue.get("title") or "",
            clue.get("reason") or "",
            clue.get("summary") or "",
            clue.get("page_title") or "",
            extra_text,
        ]
    )
    tokens = _tokenize(blob)
    related_claims: list[int] = []
    claim_hits: list[str] = []
    for num, summ in sorted((claim_summaries or {}).items()):
        ct = _tokenize(str(summ))
        overlap = sorted(tokens & ct)
        if len(overlap) >= 1 and (
            len(overlap) >= 2 or any(len(x) >= 4 for x in overlap)
        ):
            related_claims.append(int(num))
            claim_hits.append("、".join(overlap[:4]))

    entries = list(feature_entries or [])
    if not entries and feature_rows:
        entries = [{"id": "", "label": "", "text": r} for r in feature_rows]

    related_features: list[str] = []
    related_feature_ids: list[str] = []
    for ent in entries:
        ft = _tokenize(ent.get("text") or "")
        overlap = sorted(tokens & ft)
        label_hit = _label_hits_blob(ent.get("label") or "", blob)
        if (
            len(overlap) >= 2
            or (overlap and any(len(x) >= 4 for x in overlap))
            or label_hit
        ):
            related_features.append(
                "、".join(overlap[:4]) if overlap else (ent.get("label") or "")[:20]
            )
            if ent.get("id"):
                related_feature_ids.append(str(ent["id"]))
            elif ent.get("label"):
                related_feature_ids.append(str(ent["label"])[:40])
    return {
        "related_claims": related_claims[:6],
        "related_features": related_features[:4],
        "related_feature_ids": list(dict.fromkeys(related_feature_ids))[:6],
        "claim_hit_terms": claim_hits[:6],
        "match_score": len(related_claims) + len(related_feature_ids or related_features),
    }
