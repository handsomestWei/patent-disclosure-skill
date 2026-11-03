"""权利要求：独立 / 从属判断、引用权号解析、权要树规范化与 Agent 校对校验。"""
from __future__ import annotations

import re

from .text_vocab import DEP_PATTERNS, INDEPENDENT_CLAIM_STARTS


def guess_independent(claim_text: str) -> bool:
    body = re.sub(r"^\s*\d+\s*[.\．、]\s*", "", claim_text.strip())
    if body.lower().startswith(tuple(s.lower() for s in INDEPENDENT_CLAIM_STARTS)):
        return True
    low = body.lower()
    return not any(p.lower() in low for p in DEP_PATTERNS)


def parent_claim_numbers(claim_text: str) -> list[int]:
    """解析从属权引用的全部权号（含「权1或2」「claims 1-3」）。"""
    text = claim_text or ""
    nums: list[int] = []

    def _extend_chunk(chunk: str) -> None:
        for n in re.findall(r"\d+", chunk or ""):
            try:
                nums.append(int(n))
            except ValueError:
                continue

    for m in re.finditer(
        r"(?:根据|如|按照|按|依据)(?:前述)?权利要求\s*"
        r"([\d或与以及至到、,，\s与和及\-–—]+)",
        text,
    ):
        _extend_chunk(m.group(1))
    for m in re.finditer(
        r"according to claims?\s*([\d\s,orand\-–—]+)",
        text,
        re.I,
    ):
        _extend_chunk(m.group(1))
    for m in re.finditer(
        r"权利要求?\s*(\d+)\s*或\s*(?:权利要求?\s*)?(\d+)",
        text,
    ):
        nums.extend([int(m.group(1)), int(m.group(2))])
    # 去重保序
    return list(dict.fromkeys(n for n in nums if n > 0))


def parent_claim_number(claim_text: str) -> int | None:
    """启发式单父号：取引用列表首个（多选一时由 Agent 校对 claim_tree）。"""
    nums = parent_claim_numbers(claim_text)
    return nums[0] if nums else None


def normalize_claim_tree(tree: dict | None) -> dict:
    """规范化权项树：独立权清 parent、重建 roots、修正悬空父号。"""
    if not isinstance(tree, dict):
        return {"roots": [], "nodes": []}
    nodes_in = list(tree.get("nodes") or [])
    nodes: list[dict] = []
    seen: set[int] = set()
    for raw in nodes_in:
        if not isinstance(raw, dict):
            continue
        try:
            num = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        if num <= 0 or num in seen:
            continue
        seen.add(num)
        node = dict(raw)
        node["number"] = num
        indep = bool(node.get("is_independent"))
        node["is_independent"] = indep
        parent = node.get("parent")
        try:
            parent_i = int(parent) if parent is not None else None
        except (TypeError, ValueError):
            parent_i = None
        if indep:
            parent_i = None
        elif parent_i is not None and parent_i == num:
            parent_i = None
        node["parent"] = parent_i
        # 保留多引用候选供 Agent/展示
        cands = node.get("parent_candidates")
        if isinstance(cands, list):
            cleaned = []
            for x in cands:
                try:
                    xi = int(x)
                except (TypeError, ValueError):
                    continue
                if xi > 0 and xi != num:
                    cleaned.append(xi)
            node["parent_candidates"] = list(dict.fromkeys(cleaned))
        nodes.append(node)

    by_num = {n["number"]: n for n in nodes}
    # 悬空父号 → 挂到最近的更小编号独立权，否则前一条
    for n in nodes:
        if n["is_independent"]:
            n["parent"] = None
            continue
        p = n.get("parent")
        if p in by_num and p != n["number"]:
            continue
        cands = [c for c in (n.get("parent_candidates") or []) if c in by_num]
        if cands:
            n["parent"] = cands[0]
            continue
        fallback = next(
            (
                x["number"]
                for x in reversed(nodes)
                if x["number"] < n["number"] and x.get("is_independent")
            ),
            None,
        )
        if fallback is None:
            fallback = next(
                (x["number"] for x in reversed(nodes) if x["number"] < n["number"]),
                None,
            )
        n["parent"] = fallback

    # 断环：若沿 parent 走回自身，改为挂最近独立权
    for n in nodes:
        if n["is_independent"]:
            continue
        seen_path: set[int] = set()
        cur: int | None = n["number"]
        guard = 0
        while cur is not None and guard < 64:
            if cur in seen_path:
                n["parent"] = next(
                    (
                        x["number"]
                        for x in reversed(nodes)
                        if x["number"] < n["number"] and x.get("is_independent")
                    ),
                    None,
                )
                break
            seen_path.add(cur)
            cur = (by_num.get(cur) or {}).get("parent")
            guard += 1

    roots = [n["number"] for n in nodes if n.get("is_independent")]
    out = {**tree, "roots": roots, "nodes": nodes}
    return out


def validate_claim_tree(tree: dict | None) -> dict:
    """校验权项树；返回 passed/issues/warnings/count。"""
    issues: list[str] = []
    warnings: list[str] = []
    norm = normalize_claim_tree(tree)
    nodes = norm.get("nodes") or []
    if not nodes:
        warnings.append("empty_claim_tree")
        return {
            "passed": True,
            "issues": issues,
            "warnings": warnings,
            "count": 0,
            "tree": norm,
        }
    by_num = {n["number"]: n for n in nodes}
    for n in nodes:
        num = n["number"]
        if n.get("is_independent"):
            if n.get("parent") is not None:
                issues.append(f"claim[{num}]:independent_has_parent")
        else:
            p = n.get("parent")
            if p is None:
                issues.append(f"claim[{num}]:dependent_missing_parent")
            elif p not in by_num:
                issues.append(f"claim[{num}]:parent_not_found:{p}")
            elif p == num:
                issues.append(f"claim[{num}]:parent_self")
        cands = n.get("parent_candidates") or []
        if isinstance(cands, list) and len(cands) >= 2:
            warnings.append(f"claim[{num}]:multi_parent_candidates:{cands}")
            if n.get("parent") not in cands and n.get("parent") is not None:
                warnings.append(
                    f"claim[{num}]:parent_not_in_candidates:{n.get('parent')}"
                )

    # 环检测
    for n in nodes:
        if n.get("is_independent"):
            continue
        seen_path: set[int] = set()
        cur: int | None = n["number"]
        guard = 0
        while cur is not None and guard < 64:
            if cur in seen_path:
                issues.append(f"claim[{n['number']}]:cycle_via:{cur}")
                break
            seen_path.add(cur)
            cur = (by_num.get(cur) or {}).get("parent")
            guard += 1

    declared_roots = list(norm.get("roots") or [])
    expected = [n["number"] for n in nodes if n.get("is_independent")]
    if declared_roots != expected:
        warnings.append(f"roots_mismatch:declared={declared_roots}:expected={expected}")

    review = (tree or {}).get("review") if isinstance(tree, dict) else None
    if not (isinstance(review, dict) and str(review.get("by") or "").lower() in ("agent", "human")):
        warnings.append("not_agent_reviewed")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "count": len(nodes),
        "tree": norm,
    }
