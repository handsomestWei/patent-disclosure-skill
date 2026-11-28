# -*- coding: utf-8 -*-
"""对照表落盘：对照表-{场景}-{时间戳}.xlsx 主交付 + chart.json 底稿。不出 yaml/md，不出 html 工作面、不出 docx。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from highlights import (
    PALETTE,
    clip_needles,
    clip_quote,
    ensure_highlights,
    format_analysis,
    normalize_highlights,
    paint_runs,
    runs_to_xlsx,
    strength_label,
    tidy_cjk_wrap,
)
from xlsx_minimal import (
    HEATMAP,
    QUOTE_TINT,
    S_CLAIM_NO,
    S_FEATURE,
    S_LABEL,
    S_LINK,
    S_MID,
    S_NONE,
    S_WEAK,
    S_WRAP,
    S_ZEBRA,
    STRENGTH_BADGE,
    write_workbook,
)

STRENGTHS = ("强", "中", "弱", "无")
SCENES = ("invalidity", "fto", "infringement", "sep", "patentability", "oa")
SCENE_ZH = {
    "invalidity": "无效对照",
    "fto": "FTO 初筛",
    "infringement": "侵权 / EoU",
    "sep": "标准必要专利",
    "patentability": "可专利性",
    "oa": "审查答复",
}
# 文件名用，避开 / 空格
SCENE_FILE = {
    "invalidity": "无效对照",
    "fto": "FTO初筛",
    "infringement": "侵权对照",
    "sep": "标准必要",
    "patentability": "可专利性",
    "oa": "审查答复",
}
_STAMP_IN_NAME = re.compile(r"(\d{8}-\d{6}(?:-\d+)?)$")


def _file_stamp(folder: Path, fallback: str) -> str:
    found = _STAMP_IN_NAME.search(folder.name)
    return found.group(1) if found else fallback


def chart_xlsx_name(chart: dict[str, Any], stamp: str) -> str:
    scene = SCENE_FILE.get(str(chart.get("scene") or ""), "对照")
    return f"对照表-{scene}-{stamp}.xlsx"


DISCLAIMER = (
    "本对照表是特征—证据底稿，**不构成法律意见**，"
    "不构成无效、侵权、自由实施或可专利性结论。重大决策请咨询专利代理师或律师。"
)


def default_output_dir(start: Path | None = None) -> Path:
    here = (start or Path(__file__).resolve()).resolve()
    cursor = here if here.is_dir() else here.parent
    for parent in [cursor, *cursor.parents]:
        if (parent / ".git").exists() or (parent / "outputs").is_dir():
            return parent / "outputs" / "patent-chart"
    return Path.cwd() / "outputs" / "patent-chart"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if any(c in text for c in ":#{}[]&*?|>'!%@,") or "\n" in text or text.strip() != text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def dump_yaml(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return pad + "{}\n"
        chunks: list[str] = []
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                chunks.append(f"{pad}{key}:\n{dump_yaml(val, indent + 1)}")
            else:
                chunks.append(f"{pad}{key}: {_yaml_scalar(val)}\n")
        return "".join(chunks)
    if isinstance(obj, list):
        if not obj:
            return pad + "[]\n"
        chunks = []
        for item in obj:
            if isinstance(item, dict):
                inner = dump_yaml(item, indent + 1)
                first, _, rest = inner.partition("\n")
                chunks.append(f"{pad}- {first.lstrip()}")
                if rest:
                    chunks.append("\n" + rest if not rest.startswith("\n") else rest)
                    if not rest.endswith("\n"):
                        chunks.append("\n")
            else:
                chunks.append(f"{pad}- {_yaml_scalar(item)}\n")
        return "".join(chunks)
    return pad + _yaml_scalar(obj) + "\n"


def _list_str(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [tidy_cjk_wrap(value.strip())]
    out = []
    for item in value or []:
        text = tidy_cjk_wrap(str(item).strip())
        if text:
            out.append(text)
    return out


def _normalize_rejections(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in raw.get("rejections") or []:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "id": str(item.get("id") or "").strip(),
                "item": str(item.get("item") or item.get("notice_item") or "").strip(),
                "statute": str(item.get("statute") or "").strip(),
                "examiner_view": tidy_cjk_wrap(str(item.get("examiner_view") or item.get("view") or "")),
                "feature_ids": _list_str(item.get("feature_ids")),
                "column_ids": _list_str(item.get("column_ids")),
            }
        )
    return items


def normalize_chart(raw: dict[str, Any]) -> dict[str, Any]:
    scene = str(raw.get("scene") or "patentability").strip().lower()
    if scene not in SCENES:
        scene = "patentability"
    features = []
    for item in raw.get("features") or []:
        if not isinstance(item, dict):
            continue
        features.append(
            {
                "feature_id": str(item.get("feature_id") or "").strip(),
                "claim_no": item.get("claim_no"),
                "text": tidy_cjk_wrap(str(item.get("text") or "").strip()),
            }
        )
    columns = []
    for item in raw.get("columns") or []:
        if not isinstance(item, dict):
            continue
        columns.append(
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or item.get("pub_number") or "").strip(),
                "pub_number": str(item.get("pub_number") or "").strip(),
                "source_url": str(item.get("source_url") or "").strip(),
            }
        )
    cells = []
    for item in raw.get("cells") or []:
        if not isinstance(item, dict):
            continue
        strength = str(item.get("strength") or "无").strip()
        if strength not in STRENGTHS:
            strength = "无"
        risk = RISK_FROM_STRENGTH.get(strength, "未见") if scene in ("fto", "infringement") else ""
        cells.append(
            {
                "feature_id": str(item.get("feature_id") or "").strip(),
                "column_id": str(item.get("column_id") or "").strip(),
                "strength": strength,
                "risk": risk,
                "review_required": _needs_review(scene, strength),
                "quote": tidy_cjk_wrap(str(item.get("quote") or "").strip()),
                "analysis": format_analysis(str(item.get("analysis") or "")),
                "source_url": str(item.get("source_url") or "").strip(),
                "desc_para": str(item.get("desc_para") or "").strip(),
                "covered": _list_str(item.get("covered")),
                "missing": _list_str(item.get("missing")),
                "cite": tidy_cjk_wrap(str(item.get("cite") or "").strip()),
                "highlights": normalize_highlights(item.get("highlights")),
            }
        )
    left = raw.get("left") if isinstance(raw.get("left"), dict) else {}
    chart = {
        "scene": scene,
        "left": {
            "pub_number": str(left.get("pub_number") or "").strip(),
            "features_path": str(left.get("features_path") or "").strip(),
        },
        "features": features,
        "columns": columns,
        "cells": cells,
        "rejections": _normalize_rejections(raw),
        "highlights": normalize_highlights(raw.get("highlights")),
        "disclaimer": DISCLAIMER,
    }
    return ensure_highlights(chart)


def _cell_map(chart: dict[str, Any]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for cell in chart.get("cells") or []:
        out[(cell["feature_id"], cell["column_id"])] = cell
    return out


def _hls_for(chart: dict[str, Any], cell: dict | None) -> list[dict[str, str]]:
    base = list(chart.get("highlights") or [])
    if cell:
        base.extend(cell.get("highlights") or [])
    return base


def _para_tag(cell: dict) -> str:
    para = str(cell.get("desc_para") or "").strip()
    if para:
        return f"[{para}]"
    cite = _cite(cell)
    if "【" in cite:
        return cite
    if "[" in cite and "]" in cite:
        start = cite.find("[")
        end = cite.find("]", start)
        if end > start:
            return cite[start : end + 1]
    return ""


def _clip_needles_for(chart: dict[str, Any], feat: dict, cell: dict) -> list[str]:
    feat_text = str(feat.get("text") or "")
    related = []
    for item in _hls_for(chart, cell):
        claim = str(item.get("claim") or "")
        evid = str(item.get("evidence") or "")
        if claim and claim in feat_text:
            related.append(item)
        elif evid and evid in feat_text:
            related.append(item)
    return clip_needles(cell, related)


def _quote_preview(chart: dict[str, Any], feat: dict, cell: dict) -> str:
    quote = cell.get("quote") or ""
    if not quote:
        return ""
    clipped = clip_quote(quote, _clip_needles_for(chart, feat, cell))
    tag = _para_tag(cell)
    if tag and not clipped.startswith(tag):
        return f"{tag} {clipped}"
    return clipped


def _cite(cell: dict) -> str:
    if cell.get("cite"):
        return str(cell["cite"])
    para = cell.get("desc_para") or ""
    if para:
        return f"说明书 [{para}]"
    return ""


def _pending(chart: dict[str, Any]) -> list[str]:
    cmap = _cell_map(chart)
    pending: list[str] = []
    scene = chart.get("scene") or ""
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        for col in chart.get("columns") or []:
            cell = cmap.get((fid, col["id"]))
            if cell is None or cell["strength"] in ("无", "弱") or not cell.get("quote"):
                pending.append(f"{fid} × {col['id']}")
            elif scene in ("fto", "infringement") and cell.get("strength") == "强":
                pending.append(f"{fid} × {col['id']}（须人审）")
    return pending


STRENGTH_RANK = {"强": 3, "中": 2, "弱": 1, "无": 0}
RISK_FROM_STRENGTH = {"强": "高", "中": "中", "弱": "低", "无": "未见"}
RISK_BADGE = {"高": S_WEAK, "中": S_MID, "低": S_NONE, "未见": S_NONE}


def _needs_review(scene: str, token: str) -> bool:
    return scene in ("fto", "infringement") and token == "强"


def _claim_groups(chart: dict[str, Any]) -> list[tuple[str, list[dict]]]:
    groups: list[tuple[str, list[dict]]] = []
    index: dict[str, list[dict]] = {}
    for feat in chart.get("features") or []:
        key = str(feat.get("claim_no") or "")
        if key not in index:
            index[key] = []
            groups.append((key, index[key]))
        index[key].append(feat)
    return groups


def _tokens_for_claim(
    feats: list[dict], col: dict[str, Any], cmap: dict[tuple[str, str], dict]
) -> list[str]:
    tokens = []
    for feat in feats:
        cell = cmap.get((feat["feature_id"], col["id"])) or {}
        tokens.append(cell.get("strength") or "无")
    return tokens


def _cite_cell(cell: dict[str, Any], col: dict[str, Any]) -> dict[str, Any]:
    cite = _cite(cell)
    url = cell.get("source_url") or col.get("source_url") or ""
    label = cite or ("打开来源" if url else "—")
    return {
        "v": cite or url or "—",
        "s": S_LINK if url else S_WRAP,
        "link": url or None,
        "label": label,
    }


def _scene_sheet(chart: dict[str, Any], anchors: dict[tuple[str, str], int]) -> dict[str, Any] | None:
    scene = chart.get("scene") or ""
    cols = chart.get("columns") or []
    cmap = _cell_map(chart)
    features = chart.get("features") or []
    if scene == "invalidity":
        rows: list[list[Any]] = []
        for feat in features:
            fid = feat["feature_id"]
            covered: list[str] = []
            uncovered: list[str] = []
            best = "无"
            best_cell: dict[str, Any] = {}
            best_col: dict[str, Any] = cols[0] if cols else {}
            for col in cols:
                cell = cmap.get((fid, col["id"])) or {}
                token = cell.get("strength") or "无"
                tag = f"{col['label'] or col['id']}（{strength_label(token)}）"
                if token in ("强", "中"):
                    covered.append(tag)
                else:
                    uncovered.append(tag)
                if STRENGTH_RANK.get(token, 0) > STRENGTH_RANK.get(best, 0):
                    best = token
                    best_cell = cell
                    best_col = col
            loc_row = anchors.get((fid, best_col.get("id") or ""), 4) if best_col else 4
            rows.append(
                [
                    {"v": fid, "s": S_FEATURE},
                    {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
                    {"v": feat.get("text") or "", "s": S_WRAP},
                    {"v": "；".join(covered) or "—", "s": S_WRAP},
                    {"v": "；".join(uncovered) or "—", "s": S_WRAP},
                    {"v": strength_label(best), "s": STRENGTH_BADGE.get(best, S_NONE)},
                    _cite_cell(best_cell, best_col),
                    {
                        "v": "查看摘录",
                        "s": S_LINK,
                        "loc": f"'明细'!A{loc_row}",
                        "label": "查看摘录",
                    },
                ]
            )
        for claim_no, feats in _claim_groups(chart):
            for col in cols:
                tokens = _tokens_for_claim(feats, col, cmap)
                if tokens and all(token in ("强", "中") for token in tokens):
                    reading = "单篇路径：该文献对该权每个特征均为很强或中等，仍须人核能否单独使用"
                else:
                    reading = "缺格：该文献不能单独打该权。已覆盖的特征只说明特征级公开，组合路径须另核"
                rows.append(
                    [
                        {"v": f"权{claim_no}" if claim_no else "权项", "s": S_LABEL},
                        {"v": claim_no, "s": S_CLAIM_NO},
                        {"v": reading, "s": S_WRAP},
                        {"v": col.get("label") or col.get("id") or "", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                    ]
                )
        return {
            "name": "路径备忘",
            "title": "无效对照 · 覆盖路径（不是无效结论）",
            "subtitle": "特征行：很强/中等记入已覆盖。页末按权项：缺任一格则该文献不能单独打该权。不构成法律意见。",
            "headers": ["特征", "权号", "权要原文", "已覆盖", "未覆盖", "最强", "出处", "明细"],
            "rows": rows,
            "widths": [9, 7, 36, 28, 28, 12, 28, 12],
            "row_height": 28,
            "tab": "7C3AED",
            "freeze": True,
        }
    if scene == "fto":
        rows = []
        for feat in features:
            fid = feat["feature_id"]
            for col in cols:
                cell = cmap.get((fid, col["id"])) or {}
                token = cell.get("strength") or "无"
                risk = RISK_FROM_STRENGTH.get(token, "未见")
                loc_row = anchors.get((fid, col["id"]), 4)
                review = "须人审" if _needs_review("fto", token) else "—"
                rows.append(
                    [
                        {"v": fid, "s": S_FEATURE},
                        {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
                        {"v": feat.get("text") or "", "s": S_WRAP},
                        {"v": col["label"] or col["id"], "s": S_WRAP},
                        {"v": strength_label(token), "s": STRENGTH_BADGE.get(token, S_NONE)},
                        {"v": risk, "s": RISK_BADGE.get(risk, S_NONE)},
                        {"v": review, "s": S_WEAK if review == "须人审" else S_WRAP},
                        {"v": "；".join(cell.get("missing") or []) or "—", "s": S_WRAP},
                        _cite_cell(cell, col),
                        {
                            "v": "查看摘录",
                            "s": S_LINK,
                            "loc": f"'明细'!A{loc_row}",
                            "label": "查看摘录",
                        },
                    ]
                )
        for claim_no, feats in _claim_groups(chart):
            for col in cols:
                tokens = _tokens_for_claim(feats, col, cmap)
                if any(token == "无" for token in tokens):
                    reading = "缺格：该权对该方案不构成落入候选。上面单格「高」只表示该特征有对应，不是整权风险"
                elif tokens and all(token in ("强", "中") for token in tokens):
                    reading = "全部特征均为很强或中等：全部对应，须人审。不是自由实施结论"
                else:
                    reading = "无未见格，但仍有偏弱：证据未对齐，须人审后才能判断是否落入"
                rows.append(
                    [
                        {"v": f"权{claim_no}" if claim_no else "权项", "s": S_LABEL},
                        {"v": claim_no, "s": S_CLAIM_NO},
                        {"v": reading, "s": S_WRAP},
                        {"v": col["label"] or col["id"], "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "须人审" if "须人审" in reading or "全部对应" in reading else "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                    ]
                )
        return {
            "name": "风险清单",
            "title": "FTO 初筛 · 覆盖风险（不是自由实施结论）",
            "subtitle": "单格：很强→高、中等→中、偏弱→低、未见→未见，高风险须人审。页末按权项：任一特征未见，则该权不构成落入候选。",
            "headers": ["特征", "权号", "权要原文", "对照对象", "覆盖强弱", "风险", "人审", "缺口", "出处", "明细"],
            "rows": rows,
            "widths": [9, 7, 34, 16, 12, 10, 12, 28, 24, 12],
            "row_height": 28,
            "tab": "B91C1C",
            "freeze": True,
        }
    if scene == "infringement":
        scored: list[tuple[int, list[Any]]] = []
        for feat in features:
            fid = feat["feature_id"]
            for col in cols:
                cell = cmap.get((fid, col["id"])) or {}
                token = cell.get("strength") or "无"
                loc_row = anchors.get((fid, col["id"]), 4)
                gap = "；".join(cell.get("missing") or []) or (
                    "（未见对应原文）" if token in ("弱", "无") else "—"
                )
                scored.append(
                    (
                        STRENGTH_RANK.get(token, 0),
                        [
                            {"v": fid, "s": S_FEATURE},
                            {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
                            {"v": feat.get("text") or "", "s": S_WRAP},
                            {"v": col["label"] or col["id"], "s": S_WRAP},
                            {"v": strength_label(token), "s": STRENGTH_BADGE.get(token, S_NONE)},
                            {"v": "；".join(cell.get("covered") or []) or "—", "s": S_WRAP},
                            {"v": gap, "s": QUOTE_TINT.get(token, S_WRAP)},
                            _cite_cell(cell, col),
                            {
                                "v": "查看摘录",
                                "s": S_LINK,
                                "loc": f"'明细'!A{loc_row}",
                                "label": "查看摘录",
                            },
                        ],
                    )
                )
        scored.sort(key=lambda item: item[0])
        rows = [row for _, row in scored]
        for claim_no, feats in _claim_groups(chart):
            for col in cols:
                tokens = _tokens_for_claim(feats, col, cmap)
                if tokens and all(token == "强" for token in tokens):
                    reading = "该权每个特征均为很强：证据齐，须人审。不是侵权结论"
                else:
                    reading = "缺格或偏弱是待补证据，不是不侵权"
                rows.append(
                    [
                        {"v": f"权{claim_no}" if claim_no else "权项", "s": S_LABEL},
                        {"v": claim_no, "s": S_CLAIM_NO},
                        {"v": reading, "s": S_WRAP},
                        {"v": col["label"] or col["id"], "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                        {"v": "—", "s": S_WRAP},
                    ]
                )
        return {
            "name": "证据缺口",
            "title": "侵权 / EoU · 产品证据缺口（不是侵权结论）",
            "subtitle": "弱格与未见排在前面，是待补证据，不是不侵权。仅当该权全部特征均为很强，页末才写「证据齐，须人审」。",
            "headers": ["特征", "权号", "权要原文", "对照对象", "覆盖强弱", "已对应", "待补证据", "出处", "明细"],
            "rows": rows,
            "widths": [9, 7, 34, 16, 12, 24, 28, 24, 12],
            "row_height": 28,
            "tab": "C2410C",
            "freeze": True,
        }
    if scene == "oa":
        feat_by_id = {feat["feature_id"]: feat for feat in features}
        col_by_id = {col["id"]: col for col in cols}
        rejections = list(chart.get("rejections") or [])
        if not rejections:
            rejections = [
                {
                    "id": "",
                    "item": "（未拆驳回点）",
                    "statute": "",
                    "examiner_view": "",
                    "feature_ids": [feat["feature_id"] for feat in features],
                    "column_ids": [col["id"] for col in cols],
                }
            ]
        scored = []
        for rej in rejections:
            fids = rej.get("feature_ids") or [feat["feature_id"] for feat in features]
            cids = rej.get("column_ids") or [col["id"] for col in cols]
            for fid in fids:
                feat = feat_by_id.get(fid) or {"feature_id": fid, "claim_no": "", "text": ""}
                for cid in cids:
                    col = col_by_id.get(cid) or {"id": cid, "label": cid, "source_url": ""}
                    cell = cmap.get((fid, cid)) or {}
                    token = cell.get("strength") or "无"
                    loc_row = anchors.get((fid, cid), 4)
                    gap = "；".join(cell.get("missing") or []) or (
                        "（未见对应原文）" if token in ("弱", "无") else "—"
                    )
                    scored.append(
                        (
                            STRENGTH_RANK.get(token, 0),
                            [
                                {"v": rej.get("item") or rej.get("id") or "—", "s": S_FEATURE},
                                {"v": rej.get("statute") or "—", "s": S_WRAP},
                                {"v": fid, "s": S_FEATURE},
                                {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
                                {"v": feat.get("text") or "", "s": S_WRAP},
                                {"v": col.get("label") or col.get("id") or cid, "s": S_WRAP},
                                {"v": strength_label(token), "s": STRENGTH_BADGE.get(token, S_NONE)},
                                {"v": rej.get("examiner_view") or "—", "s": S_WRAP},
                                {"v": cell.get("analysis") or "—", "s": S_WRAP},
                                {"v": gap, "s": QUOTE_TINT.get(token, S_WRAP)},
                                _cite_cell(cell, col),
                                {
                                    "v": "查看摘录",
                                    "s": S_LINK,
                                    "loc": f"'明细'!A{loc_row}",
                                    "label": "查看摘录",
                                },
                            ],
                        )
                    )
        scored.sort(key=lambda item: item[0])
        return {
            "name": "驳回映射",
            "title": "审查答复 · 驳回点对照（不是答复结论）",
            "subtitle": "驳回点 × 权要特征 × 对比文件。弱/未见排前，便于找可争点。不写入意见陈述正文。",
            "headers": [
                "驳回点",
                "法条",
                "特征",
                "权号",
                "权要原文",
                "对照对象",
                "覆盖强弱",
                "审查员观点",
                "对应说明",
                "待核",
                "出处",
                "明细",
            ],
            "rows": [row for _, row in scored],
            "widths": [12, 18, 9, 7, 28, 16, 12, 28, 32, 22, 22, 12],
            "row_height": 32,
            "tab": "1D4E89",
            "freeze": True,
        }
    return None


def _paint_md(text: str, highlights: list[dict[str, str]], *, side: str) -> str:
    parts = []
    for chunk, hid in paint_runs(text, highlights, side=side):
        if hid:
            parts.append(f"**{chunk}**")
        else:
            parts.append(chunk)
    return "".join(parts) or text


def _md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_chart_md(chart: dict[str, Any]) -> str:
    scene = SCENE_ZH.get(chart["scene"], chart["scene"])
    left = (chart.get("left") or {}).get("pub_number") or "（未标公开号）"
    cols = chart.get("columns") or []
    pending = _pending(chart)
    cmap = _cell_map(chart)
    hls = chart.get("highlights") or []
    lines = [
        f"# 权利要求对照表 · {scene}",
        "",
        f"> {DISCLAIMER}",
        "",
        "预览用。**给人看、给人传的主文件是同目录 `对照表-{场景}-{时间戳}.xlsx`**（总览可进入明细；同色底纹见「图例」）。",
        "",
        f"- **场景**：{scene}（`{chart['scene']}`）",
        f"- **左列专利**：{left}",
        "",
        "## 覆盖总览",
        "",
    ]
    head = ["特征", "权要原文"] + [c["label"] or c["id"] for c in cols]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("| " + " | ".join(["---"] * len(head)) + " |")
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        bits = [fid, _md_cell(feat.get("text") or "")]
        for col in cols:
            cell = cmap.get((fid, col["id"])) or {}
            token = cell.get("strength") or "无"
            bits.append(strength_label(token))
        lines.append("| " + " | ".join(bits) + " |")
    lines.extend(["", "## 待核清单", ""])
    if pending:
        for item in pending:
            lines.append(f"- {item}")
    else:
        lines.append("- 无（仍须人审，不得视为结论）")
    if hls:
        lines.extend(["", "## 同色图例", ""])
        for h in hls:
            lines.append(
                f"- **{h['id']}** {h.get('label') or ''}：权要「{h.get('claim') or ''}」↔ 对照「{h.get('evidence') or ''}」"
            )
    for col in cols:
        lines.extend(["", f"## 对照表 · {col['label'] or col['id']}", ""])
        lines.append("| 特征 | 权要原文 | 对照摘录 | 对应说明 | 覆盖强弱 |")
        lines.append("| --- | --- | --- | --- | --- |")
        seen_quote: dict[str, str] = {}
        for feat in chart.get("features") or []:
            cell = cmap.get((feat["feature_id"], col["id"])) or {}
            local = _hls_for(chart, cell)
            claim = _paint_md(feat.get("text") or "", local, side="claim")
            preview = _quote_preview(chart, feat, cell)
            if preview and preview in seen_quote:
                tag = _para_tag(cell)
                quote = f"同 {seen_quote[preview]}" + (f" · {tag}" if tag else "")
            else:
                if preview:
                    seen_quote[preview] = feat["feature_id"]
                quote = _paint_md(preview or "（无）", local, side="evidence")
            analysis = cell.get("analysis") or "（未填写对应说明）"
            token = cell.get("strength") or "无"
            badge = strength_label(token)
            lines.append(
                "| "
                + " | ".join(
                    [
                        feat["feature_id"],
                        _md_cell(claim),
                        _md_cell(quote),
                        _md_cell(analysis),
                        badge,
                    ]
                )
                + " |"
            )
    lines.extend(["", "## 逐格摘录", ""])
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        for col in cols:
            cell = cmap.get((fid, col["id"]))
            if not cell:
                continue
            local = _hls_for(chart, cell)
            lines.append(f"### {fid} · {col['id']}")
            lines.append("")
            token = cell.get("strength") or "无"
            lines.append(f"- **覆盖强弱**：{strength_label(token)}")
            cite = _cite(cell)
            if cite:
                lines.append(f"- **出处**：{cite}")
            if cell.get("source_url"):
                lines.append(f"- **来源**：{cell['source_url']}")
            if cell.get("covered"):
                lines.append("- **对应**：" + "；".join(cell["covered"]))
            if cell.get("missing"):
                lines.append("- **未记载**：" + "；".join(cell["missing"]))
            if feat.get("text"):
                lines.append("")
                lines.append("权要原文：")
                lines.append("")
                lines.append(_paint_md(feat["text"], local, side="claim"))
            if cell.get("quote"):
                lines.append("")
                lines.append("对照摘录：")
                lines.append("")
                lines.append(_paint_md(cell["quote"], local, side="evidence"))
            if cell.get("analysis"):
                lines.append("")
                lines.append(cell["analysis"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _rich_cell(text: str, highlights: list[dict[str, str]], *, side: str, style: int) -> dict[str, Any]:
    runs = runs_to_xlsx(paint_runs(text or "", highlights, side=side), highlights)
    return {"v": text or "", "s": style, "runs": runs or [(text or "", None)]}


def _drill_anchors(chart: dict[str, Any]) -> dict[tuple[str, str], int]:
    """明细表数据行号（Excel 行，含标题 3 行之后从 4 起）。每格占 9 行。"""
    anchors: dict[tuple[str, str], int] = {}
    row = 4
    for feat in chart.get("features") or []:
        for col in chart.get("columns") or []:
            anchors[(feat["feature_id"], col["id"])] = row
            row += 9
    return anchors


def _overview_loc(chart: dict[str, Any], feature_id: str, column_id: str) -> str:
    """总览里该特征×该对照列的强弱格。列从 D 起，数据从第 4 行起。"""
    feats = chart.get("features") or []
    cols = chart.get("columns") or []
    fi = next((i for i, feat in enumerate(feats) if feat.get("feature_id") == feature_id), 0)
    ci = next((i for i, col in enumerate(cols) if col.get("id") == column_id), 0)
    col_no = 4 + ci
    letters = ""
    n = col_no
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"'总览'!{letters}{4 + fi}"


def _table_anchors(chart: dict[str, Any]) -> dict[tuple[str, str], int]:
    """对照表数据行号（每特征×对照一格一行，自第 4 行起）。"""
    anchors: dict[tuple[str, str], int] = {}
    row = 4
    for feat in chart.get("features") or []:
        for col in chart.get("columns") or []:
            anchors[(feat["feature_id"], col["id"])] = row
            row += 1
    return anchors


def render_xlsx_book(chart: dict[str, Any], *, title: str, subtitle: str) -> list[dict[str, Any]]:
    cols = chart.get("columns") or []
    cmap = _cell_map(chart)
    anchors = _drill_anchors(chart)
    table_anchors = _table_anchors(chart)
    overview_headers = ["特征", "权号", "权要原文"] + [c["label"] or c["id"] for c in cols] + ["打开明细"]
    overview_rows = []
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        first = anchors.get((fid, cols[0]["id"])) if cols else 4
        row: list[Any] = [
            {"v": fid, "s": S_FEATURE},
            {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
            {"v": feat.get("text") or "", "s": S_WRAP},
        ]
        for col in cols:
            cell = cmap.get((fid, col["id"])) or {}
            token = cell.get("strength") or "无"
            loc_row = anchors.get((fid, col["id"]), first)
            extra_review = " 须人审" if _needs_review(chart.get("scene") or "", token) else ""
            shown = strength_label(token) + extra_review
            row.append(
                {
                    "v": shown,
                    "s": HEATMAP.get(token, S_NONE),
                    "loc": f"'明细'!A{loc_row}",
                    "label": shown,
                }
            )
        row.append(
            {
                "v": "查看摘录",
                "s": S_LINK,
                "loc": f"'明细'!A{first}",
                "label": "查看摘录",
            }
        )
        overview_rows.append(row)

    chart_headers = [
        "特征",
        "权号",
        "权要原文",
        "对照对象",
        "对照摘录",
        "对应说明",
        "覆盖强弱",
        "出处",
        "明细",
    ]
    chart_rows = []
    seen_preview: dict[tuple[str, str], tuple[str, int]] = {}
    table_row_n = 4
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        for i, col in enumerate(cols):
            cell = cmap.get((fid, col["id"])) or {}
            token = cell.get("strength") or "无"
            local = _hls_for(chart, cell)
            zebra = S_ZEBRA if i % 2 else S_WRAP
            cite = _cite(cell)
            url = cell.get("source_url") or col.get("source_url") or ""
            loc_row = anchors[(fid, col["id"])]
            quote_style = QUOTE_TINT.get(token, S_WRAP)
            preview = _quote_preview(chart, feat, cell)
            key = (col["id"], preview)
            if preview and key in seen_preview:
                first_fid, _first_row = seen_preview[key]
                tag = _para_tag(cell)
                label = f"同 {first_fid}" + (f" · {tag}" if tag else "")
                quote_cell: dict[str, Any] = {
                    "v": label,
                    "s": S_WRAP,
                    "note": preview,
                }
            else:
                if preview:
                    seen_preview[key] = (fid, table_row_n)
                quote_cell = _rich_cell(preview, local, side="evidence", style=quote_style)
            chart_rows.append(
                [
                    {"v": fid, "s": S_FEATURE},
                    {"v": str(feat.get("claim_no") or ""), "s": S_CLAIM_NO},
                    _rich_cell(feat.get("text") or "", local, side="claim", style=zebra),
                    {"v": col["label"] or col["id"], "s": zebra},
                    quote_cell,
                    {"v": cell.get("analysis") or "", "s": quote_style},
                    {
                        "v": strength_label(token),
                        "s": STRENGTH_BADGE.get(token, S_NONE),
                    },
                    {"v": cite or url, "s": S_LINK, "link": url or None, "label": cite or ("打开公布页" if url else "")},
                    {"v": "查看摘录", "s": S_LINK, "loc": f"'明细'!A{loc_row}", "label": "查看摘录"},
                ]
            )
            table_row_n += 1

    drill_headers = ["项", "内容", "跳转"]
    drill_rows: list[list[Any]] = []
    drill_heights: list[float] = []
    empty = {"v": "", "s": S_WRAP}
    for feat in chart.get("features") or []:
        fid = feat["feature_id"]
        for col in cols:
            cell = cmap.get((fid, col["id"])) or {}
            token = cell.get("strength") or "无"
            local = _hls_for(chart, cell)
            cite = _cite(cell)
            url = cell.get("source_url") or col.get("source_url") or ""
            table_row = table_anchors.get((fid, col["id"]), 4)
            block = [
                (
                    [
                        {"v": f"{fid} × {col['id']}", "s": S_FEATURE},
                        {"v": "返回总览", "s": S_LINK, "loc": _overview_loc(chart, fid, col["id"]), "label": "返回总览"},
                        {"v": "返回对照表", "s": S_LINK, "loc": f"'对照表'!A{table_row}", "label": "返回对照表"},
                    ],
                    22,
                ),
                (
                    [{"v": "覆盖强弱", "s": S_LABEL}, {"v": strength_label(token), "s": STRENGTH_BADGE.get(token, S_NONE)}, empty],
                    22,
                ),
                (
                    [
                        {"v": "出处", "s": S_LABEL},
                        {"v": cite or url, "s": S_LINK, "link": url or None, "label": cite or ("打开公布页" if url else "")},
                        empty,
                    ],
                    22,
                ),
                (
                    [{"v": "权要原文", "s": S_LABEL}, _rich_cell(feat.get("text") or "", local, side="claim", style=S_WRAP), empty],
                    36,
                ),
                (
                    [{"v": "对照摘录", "s": S_LABEL}, _rich_cell(cell.get("quote") or "（未见对应原文）", local, side="evidence", style=QUOTE_TINT.get(token, S_WRAP)), empty],
                    36,
                ),
                (
                    [{"v": "对应说明", "s": S_LABEL}, {"v": cell.get("analysis") or "（未填写）", "s": S_WRAP}, empty],
                    36,
                ),
                (
                    [{"v": "对应", "s": S_LABEL}, {"v": "；".join(cell.get("covered") or []) or "—", "s": S_WRAP}, empty],
                    22,
                ),
                (
                    [{"v": "未记载", "s": S_LABEL}, {"v": "；".join(cell.get("missing") or []) or "—", "s": S_WRAP}, empty],
                    22,
                ),
                ([{"v": "", "s": S_WRAP}, empty, empty], 12),
            ]
            for row, ht in block:
                drill_rows.append(row)
                drill_heights.append(ht)

    legend_headers = ["色号", "含义", "权要用语", "对照用语"]
    legend_rows: list[list[Any]] = []
    for h in chart.get("highlights") or []:
        rgb = "FF" + str(h.get("fg") or "2563EB")
        name = next((p["name"] for p in PALETTE if p["id"] == h["id"].split("_")[0]), "")
        token = f"{h['id']} {name}".strip()
        legend_rows.append(
            [
                {"v": token, "s": S_WRAP, "runs": [(token, rgb)]},
                {"v": h.get("label") or "", "s": S_WRAP, "runs": [(h.get("label") or "", rgb)]},
                {"v": h.get("claim") or "", "s": S_WRAP, "runs": [(h.get("claim") or "", rgb)]},
                {"v": h.get("evidence") or "", "s": S_WRAP, "runs": [(h.get("evidence") or "", rgb)]},
            ]
        )
    legend_rows.extend(
        [
            [{"v": "很强", "s": STRENGTH_BADGE["强"]}, {"v": "原文几乎覆盖该限定，且有出处", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
            [{"v": "中等", "s": STRENGTH_BADGE["中"]}, {"v": "手段对应但术语或限定不完全对齐", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
            [{"v": "偏弱", "s": STRENGTH_BADGE["弱"]}, {"v": "仅可能构成同义或片段相关", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
            [{"v": "未见", "s": STRENGTH_BADGE["无"]}, {"v": "对照材料中未见对应原文，单元格留空", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
            [
                {"v": "用法", "s": S_LABEL},
                {"v": "对照表摘录按对应短语截取并着色。「同 Fk · [段号]」悬停批注可看摘录；完整原文在明细。无效缺格只断该文献的单篇路径；FTO 缺格则该权不构成落入候选；侵权的弱格与未见格是待补证据，不是不侵权。可专利性缺格不是新颖性结论。", "s": S_WRAP},
                {"v": "", "s": S_WRAP},
                {"v": "", "s": S_WRAP},
            ],
        ]
    )

    extra = _scene_sheet(chart, anchors)
    scene_hint = {
        "invalidity": "  ·  见「路径备忘」。缺格只断该文献的单篇路径",
        "fto": "  ·  见「风险清单」。任一特征未见，则该权不构成落入候选",
        "infringement": "  ·  见「证据缺口」。弱格与未见格是待补证据，不是不侵权",
        "oa": "  ·  见「驳回映射」；不写入意见陈述正文",
        "patentability": "  ·  缺格只表示该文献未记载该特征，不是新颖性或创造性结论",
    }.get(chart.get("scene") or "", "")
    if chart.get("scene") == "fto":
        legend_rows.extend(
            [
                [{"v": "高", "s": RISK_BADGE["高"]}, {"v": "该特征覆盖很强，须人审。整权是否落入看页末：缺格则不构成落入候选", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
                [{"v": "中", "s": RISK_BADGE["中"]}, {"v": "手段对应但不完全对齐，建议人审", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
                [{"v": "低", "s": RISK_BADGE["低"]}, {"v": "仅片段相关", "s": S_WRAP}, {"v": "", "s": S_WRAP}, {"v": "", "s": S_WRAP}],
            ]
        )
    sheets = [
        {
            "name": "总览",
            "title": title,
            "subtitle": subtitle + scene_hint + "  ·  点击强弱格进入明细",
            "headers": overview_headers,
            "rows": overview_rows,
            "widths": [9, 7, 36] + [14] * len(cols) + [12],
            "row_height": 28,
            "tab": "1F4E79",
        },
        {
            "name": "对照表",
            "title": title,
            "subtitle": subtitle + scene_hint + "  ·  摘录按对应短语截取并着色；「同 Fk」悬停可看摘录",
            "headers": chart_headers,
            "rows": chart_rows,
            "widths": [9, 7, 34, 14, 52, 40, 18, 20, 12],
            "row_height": 48,
            "tab": "2E7D32",
        },
        {
            "name": "明细",
            "title": title,
            "subtitle": "每格完整摘录。同色底纹见「图例」。可用「返回总览」「返回对照表」跳转。",
            "headers": drill_headers,
            "rows": drill_rows,
            "widths": [16, 80, 16],
            "heights": drill_heights,
            "row_height": 22,
            "tab": "C65911",
            "freeze": True,
        },
    ]
    if extra:
        sheets.append(extra)
    sheets.append(
        {
            "name": "图例",
            "title": "同色图例与覆盖强弱",
            "subtitle": "色号行：高亮色加粗字。色块区分同一概念在权要与对照中的用语。",
            "headers": legend_headers,
            "rows": legend_rows,
            "widths": [18, 36, 28, 28],
            "row_height": 24,
            "tab": "5B6B7A",
        }
    )
    return sheets


def write_chart_bundle(
    raw: dict[str, Any],
    *,
    output_dir: Path | None = None,
    case_id: str = "chart",
    into: Path | None = None,
) -> dict[str, Path]:
    chart = normalize_chart(raw)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if into:
        folder = Path(into)
        folder.mkdir(parents=True, exist_ok=True)
    else:
        folder = (output_dir or default_output_dir()) / f"{case_id}_{stamp}"
        folder.mkdir(parents=True, exist_ok=True)
    stamp = _file_stamp(folder, stamp)
    xlsx_path = folder / chart_xlsx_name(chart, stamp)
    json_path = folder / "chart.json"
    left_pub = (chart.get("left") or {}).get("pub_number") or ""
    scene = SCENE_ZH.get(chart["scene"], chart["scene"])
    subtitle = (
        f"{scene}"
        + (f"  ·  左列 {left_pub}" if left_pub else "")
        + "  ·  底稿，不构成法律意见"
    )
    write_workbook(
        xlsx_path,
        render_xlsx_book(chart, title="权利要求对照表", subtitle=subtitle),
    )
    json_path.write_text(json.dumps(chart, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"dir": folder, "xlsx": xlsx_path, "json": json_path}


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        raise ValueError("请传入 JSON（chart.json 或 Agent 打分对象），不要把 yaml 再喂给本脚本")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON 须为对象")
    return data


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="写出对照表 xlsx + json")
    ap.add_argument("--json", required=True, help="chart JSON")
    ap.add_argument("--output-dir", help="默认 outputs/patent-chart")
    ap.add_argument("--case-id", default="chart")
    ap.add_argument("--into", help="写入该会话目录（与 intake.json 同层）")
    args = ap.parse_args(argv)
    try:
        raw = _load(Path(args.json))
        paths = write_chart_bundle(
            raw,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            case_id=args.case_id,
            into=Path(args.into) if args.into else None,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"CHART_DIR: {paths['dir']}", flush=True)
    print(f"CHART_XLSX: {paths['xlsx']}", flush=True)
    print(f"CHART_JSON: {paths['json']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
