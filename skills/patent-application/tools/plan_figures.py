# -*- coding: utf-8 -*-
"""按权要语言选定申请附图图型，写出 figures/figure_plan.yaml。

用法：
  python tools/plan_figures.py --claims 权利要求书.md --out figures/figure_plan.yaml
  python tools/plan_figures.py --plan figures/figure_plan.yaml --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stdio_utf8 import ensure_utf8_stdio

ALLOWED_KINDS = (
    "flowchart",
    "block_diagram",
    "section",
    "exploded",
    "multi_state",
    "lineart",
    "source_image",
)
RENDERABLE = {"flowchart", "block_diagram", "lineart", "source_image"}

KIND_RULES: list[tuple[str, tuple[str, ...], str]] = (
    ("flowchart", (r"包括以下步骤", r"包括如下步骤", r"步骤[一二三四五六七八九十百零\d]+"), "独权按步骤展开"),
    ("block_diagram", (r"模块", r"单元", r"处理器", r"存储器"), "权要写了模块/单元"),
    ("section", (r"剖视", r"内设", r"内部设有", r"腔体", r"壳体内"), "权要写到内部构造"),
    ("exploded", (r"可拆卸", r"分解", r"依次套设", r"从.{0,12}拆"), "权要写到拆装/套设"),
    ("multi_state", (r"第一状态", r"第二状态", r"锁定状态", r"触发状态", r"切换至"), "权要写了多种状态"),
)


@dataclass
class Finding:
    level: str
    code: str
    message: str


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml

        data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} 根须为 mapping")
    return data


def _dump_yaml(obj: dict[str, Any]) -> str:
    try:
        import yaml

        return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
    except Exception:
        return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def _kind_from_disclosure_item(item: dict[str, Any]) -> str:
    rels = item.get("relates_to") or []
    for rel in rels:
        if not isinstance(rel, dict):
            continue
        relation = str(rel.get("relation") or "")
        if relation == "section_of":
            return "section"
        if relation == "exploded_of":
            return "exploded"
        if relation in {"same_state", "alternate_view"}:
            return "multi_state"
    kind = str(item.get("kind") or "lineart")
    if kind in ALLOWED_KINDS:
        return kind
    return "lineart"


def from_disclosure(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not plan:
        return out
    for item in plan.get("figures") or []:
        if not isinstance(item, dict) or item.get("use_in_disclosure") is not True:
            continue
        try:
            fig = int(item.get("fig"))
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "fig": fig,
                "kind": _kind_from_disclosure_item(item),
                "reason": str(item.get("reason") or "交底入文图").strip() or "交底入文图",
                "covers": [str(x).strip() for x in (item.get("covers") or []) if str(x).strip()],
                "source": "disclosure",
                "path": str(item.get("path") or ""),
            }
        )
    return out


def suggest_figures(
    claims_text: str,
    *,
    patent_type: str = "invention",
    disclosure_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    text = claims_text or ""
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for kind, patterns, reason in KIND_RULES:
        if any(re.search(pat, text) for pat in patterns):
            hits.append(
                {
                    "kind": kind,
                    "reason": reason,
                    "covers": [],
                    "source": "claim_language",
                    "path": "",
                }
            )
            seen.add(kind)
    head = text[:120]
    if patent_type == "invention":
        if re.search(r"方法|步骤", head) and "flowchart" not in seen:
            hits.insert(
                0,
                {
                    "kind": "flowchart",
                    "reason": "发明方法独权默认流程图",
                    "covers": [],
                    "source": "claim_language",
                    "path": "",
                },
            )
            seen.add("flowchart")
        if re.search(r"系统|装置", head) and "block_diagram" not in seen:
            hits.append(
                {
                    "kind": "block_diagram",
                    "reason": "系统/装置独立权项默认框图",
                    "covers": [],
                    "source": "claim_language",
                    "path": "",
                }
            )
            seen.add("block_diagram")
        if not hits:
            hits.append(
                {
                    "kind": "flowchart",
                    "reason": "未检出特定图型，发明默认流程图",
                    "covers": [],
                    "source": "claim_language",
                    "path": "",
                }
            )
    disclosed = from_disclosure(disclosure_plan)
    disclosed_kinds = {str(item.get("kind")) for item in disclosed}
    extra = [item for item in hits if item["kind"] not in disclosed_kinds]
    merged = list(disclosed)
    for item in extra:
        # 剖视 / 爆炸 / 多状态等脚本不可渲染：交底有可升格路径则保留，否则挂 pending
        # （发明与实用新型同口径；禁止凭权要语言空画内部结构）。
        if item["kind"] not in RENDERABLE and not str(item.get("path") or ""):
            item = dict(item)
            item["source"] = "pending"
        merged.append(item)
    numbered: list[dict[str, Any]] = []
    used = {int(item["fig"]) for item in merged if item.get("fig") is not None}
    next_fig = 1
    for item in merged:
        row = dict(item)
        if row.get("fig") is None:
            while next_fig in used:
                next_fig += 1
            row["fig"] = next_fig
            used.add(next_fig)
            next_fig += 1
        numbered.append(row)
    numbered.sort(key=lambda row: int(row["fig"]))
    return numbered


def validate_plan(plan: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    figs = [item for item in (plan.get("figures") or []) if isinstance(item, dict)]
    if not figs:
        findings.append(Finding("ERROR", "EMPTY_PLAN", "figure_plan.figures 为空。"))
        return findings
    seen: set[int] = set()
    for item in figs:
        kind = str(item.get("kind") or "")
        if kind not in ALLOWED_KINDS:
            findings.append(Finding("ERROR", "BAD_KIND", f"图{item.get('fig')} kind「{kind}」不在允许列表。"))
        if not str(item.get("reason") or "").strip():
            findings.append(Finding("ERROR", "NO_REASON", f"图{item.get('fig')} 缺少 reason。"))
        covers = item.get("covers")
        if covers is None or not isinstance(covers, list):
            findings.append(Finding("ERROR", "NO_COVERS", f"图{item.get('fig')} covers 须为列表（可空）。"))
        try:
            fig = int(item.get("fig"))
        except (TypeError, ValueError):
            findings.append(Finding("ERROR", "BAD_FIG", f"非法 fig：{item.get('fig')}"))
            continue
        if fig in seen:
            findings.append(Finding("ERROR", "DUP_FIG", f"fig {fig} 重复。"))
        seen.add(fig)
        source = str(item.get("source") or "")
        if source == "pending":
            findings.append(
                Finding(
                    "WARNING",
                    "FIG_PENDING",
                    f"图{fig}（{kind}）交底没有可升格线稿，记问题清单，不要空画内部。",
                )
            )
    return findings


def build_plan(
    claims_text: str,
    *,
    patent_type: str = "invention",
    disclosure_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "$schema": "application_figure_plan",
        "version": 1,
        "patent_type": patent_type,
        "figures": suggest_figures(
            claims_text, patent_type=patent_type, disclosure_plan=disclosure_plan
        ),
    }


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--type", dest="patent_type", default="invention")
    parser.add_argument("--disclosure-plan", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--plan", type=Path, help="已有申请 figure_plan，配合 --check")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        if args.check:
            path = args.plan or args.out
            if not path:
                parser.error("--check 需要 --plan 或 --out")
            plan = _load_mapping(path.expanduser().resolve())
        else:
            if not args.claims or not args.out:
                parser.error("生成时需要 --claims 与 --out")
            claims = args.claims.read_text(encoding="utf-8")
            disclosure = _load_mapping(args.disclosure_plan) if args.disclosure_plan else None
            plan = build_plan(claims, patent_type=args.patent_type, disclosure_plan=disclosure)
            out = args.out.expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_dump_yaml(plan), encoding="utf-8")
    except FileNotFoundError as exc:
        print("APPLICATION_FIG_PLAN: ok=0 errors=1 warnings=0")
        print(f"文件不存在：{exc.filename}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("APPLICATION_FIG_PLAN: ok=0 errors=1 warnings=0")
        print(f"无法读取：{exc}", file=sys.stderr)
        return 1

    findings = validate_plan(plan)
    errors = sum(item.level == "ERROR" for item in findings)
    warnings = sum(item.level == "WARNING" for item in findings)
    ok = errors == 0
    print(f"APPLICATION_FIG_PLAN: ok={1 if ok else 0} errors={errors} warnings={warnings}")
    if args.out and not args.check:
        print(f"APPLICATION_FIG_PLAN_PATH: {args.out}")
    if findings:
        for item in findings:
            print(f"{item.level}\t{item.code}\t{item.message}")
    elif ok:
        print("PASS: 图型清单可出图。pending 项须进问题清单。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
