"""线索数据：读取、规范化、按置信度与市场分组筛选、文件名与链接。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .vocab import CONF_RANK, DEFAULT_MAX_CLUES, REGION_GROUP_LABELS


def as_clues(raw) -> list[dict]:
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    if isinstance(raw, dict):
        clues = raw.get("clues") or raw.get("items") or []
        if isinstance(clues, list):
            return [c for c in clues if isinstance(c, dict)]
    return []


def _conf_rank(conf: str) -> int:
    s = (conf or "").strip()
    if not s:
        return 0
    if s in CONF_RANK:
        return CONF_RANK[s]
    return CONF_RANK.get(s.lower(), 0)


def normalize_clue(c: dict, *, index: int = 0) -> dict:
    title = (c.get("title") or c.get("name") or "").strip()
    url = (c.get("url") or c.get("link") or "").strip()
    conf = (c.get("confidence") or "").strip() or "中"
    reason = (
        c.get("reason") or c.get("rationale") or c.get("note") or ""
    ).strip()
    out = {
        **c,
        "title": title,
        "url": url,
        "confidence": conf,
        "reason": reason,
        "clue_id": c.get("clue_id") or f"clue-{index + 1:02d}",
    }
    return out


def filter_clues(
    clues: list[dict],
    *,
    max_keep: int = DEFAULT_MAX_CLUES,
) -> tuple[list[dict], list[dict]]:
    """按置信度高→低排序，默认最多保留 max_keep 条。

    线索带 ``region_group`` 时：本国市场 / 申请人所在国排在前面；
    ``other``（其他地区）只保留置信度「高」的。不带该字段的线索按原规则只看置信度。
    """
    if max_keep <= 0:
        return [], list(clues)
    ranked: list[tuple[int, int, int, dict]] = []
    off_market: list[dict] = []
    for i, c in enumerate(clues):
        n = normalize_clue(c, index=i)
        conf = _conf_rank(n["confidence"])
        group = str(n.get("region_group") or "").strip()
        if group == "other" and conf < CONF_RANK["高"]:
            off_market.append(n)
            continue
        ranked.append((0 if group == "other" else 1, conf, -i, n))
    ranked.sort(key=lambda t: (-t[0], -t[1], -t[2]))
    kept = [t[3] for t in ranked[:max_keep]]
    dropped = [t[3] for t in ranked[max_keep:]] + off_market
    # 重编号 clue_id
    for i, c in enumerate(kept):
        c["clue_id"] = f"clue-{i + 1:02d}"
    return kept, dropped


def _region_text(clue: dict) -> str:
    """「日本（日文 · 本国市场）」；无地区字段时为空。"""
    region = str(clue.get("region") or "").strip()
    bits = [
        str(clue.get("lang") or "").strip(),
        REGION_GROUP_LABELS.get(str(clue.get("region_group") or "").strip(), ""),
    ]
    bits = [b for b in bits if b]
    if not region:
        return ""
    return f"{region}（{' · '.join(bits)}）" if bits else region


def clue_filename(title: str, index: int) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", (title or "线索").strip())
    base = re.sub(r"-{2,}", "-", base).strip("-")[:36] or "线索"
    return f"{index + 1:02d}-{base}.md"


def _clue_stem(clue: dict) -> str:
    return Path(clue.get("filename") or "x.md").stem


def _clue_link(clue: dict, title: str | None = None) -> str:
    stem = _clue_stem(clue)
    t = title or clue.get("title") or stem
    return f"[[clues/{stem}|{t}]]"


def _table_wikilink(target: str, alias: str) -> str:
    """表格单元格内 wikilink：别名前的 | 必须转义，否则会被拆列。"""
    return f"[[{target}\\|{alias}]]"


def normalize_anchor_fits(clue: dict) -> list[dict]:
    """Agent 写入的锚点贴合：[{kind, key, fit}, ...]。"""
    raw = clue.get("anchor_fits") or clue.get("fits") or []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or item.get("type") or "").strip().lower()
        if kind in ("feat", "特征"):
            kind = "feature"
        elif kind in ("权利要求", "claim_id", "权"):
            kind = "claim"
        elif kind in ("术语",):
            kind = "term"
        if kind not in ("feature", "claim", "term"):
            continue
        key = item.get("key")
        if key is None:
            key = item.get("id") or item.get("name") or item.get("label")
        if key is None or str(key).strip() == "":
            continue
        fit = str(item.get("fit") or item.get("highlight") or item.get("point") or "").strip()
        if not fit:
            continue
        out.append({"kind": kind, "key": str(key).strip(), "fit": fit[:120]})
    return out


def agent_fits_for(clue: dict, kind: str) -> list[tuple[str, str]]:
    """返回 (key, fit) 列表；kind=feature|claim|term。"""
    return [
        (str(x["key"]), str(x["fit"]))
        for x in normalize_anchor_fits(clue)
        if x.get("kind") == kind
    ]


def load_clues_sidecar(note_dir: Path) -> list[dict]:
    path = note_dir / "clues" / "clues.json"
    if not path.is_file():
        return []
    try:
        return as_clues(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return []
