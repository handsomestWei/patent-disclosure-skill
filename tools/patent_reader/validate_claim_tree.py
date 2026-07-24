#!/usr/bin/env python3
"""
校验并规范化 claim_tree.json（权项父子树）。

Agent 校对后应再跑本脚本：修复悬空父号/roots，报告多引用候选与未校对警告。

用法：
  python tools/patent_reader/validate_claim_tree.py -i claim_tree.json
  python tools/patent_reader/validate_claim_tree.py -i claim_tree.json --write
  python tools/patent_reader/validate_claim_tree.py -i claim_tree.json --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from common import normalize_claim_tree, validate_claim_tree
except ImportError:
    from tools.patent_reader.common import normalize_claim_tree, validate_claim_tree


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", required=True, type=Path)
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        type=Path,
        help="校验报告 JSON（默认 stdout 摘要 + 旁路 .lint.json）",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="把 normalize 后的树写回 -i（保留 review 等字段）",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="warnings 也导致非零退出（含 not_agent_reviewed）",
    )
    ap.add_argument(
        "--require-review",
        action="store_true",
        help="未标注 Agent/人工校对时视为失败",
    )
    args = ap.parse_args(argv)

    if not args.input.is_file():
        print(f"FAIL missing {args.input}", file=sys.stderr)
        return 2
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL invalid json: {e}", file=sys.stderr)
        return 2

    result = validate_claim_tree(raw)
    tree = result.get("tree") or normalize_claim_tree(raw)
    # 保留 Agent review 元数据
    if isinstance(raw, dict) and isinstance(raw.get("review"), dict):
        tree["review"] = raw["review"]

    report = {
        "passed": result["passed"],
        "issues": result["issues"],
        "warnings": result["warnings"],
        "count": result["count"],
        "agent_reviewed": isinstance(raw.get("review"), dict)
        and str((raw.get("review") or {}).get("by") or "").lower()
        in ("agent", "human"),
    }
    if args.require_review and not report["agent_reviewed"]:
        report["passed"] = False
        if "not_agent_reviewed" not in report["issues"]:
            report["issues"] = list(report["issues"]) + ["not_agent_reviewed"]

    out_path = args.output or Path(str(args.input) + ".lint.json")
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.write:
        args.input.write_text(
            json.dumps(tree, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"WROTE normalized tree → {args.input}")

    print(
        f"{'OK' if report['passed'] else 'FAIL'} claim_tree "
        f"count={report['count']} issues={len(report['issues'])} "
        f"warnings={len(report['warnings'])} reviewed={report['agent_reviewed']}"
    )
    for x in report["issues"]:
        print(f"  issue: {x}")
    for x in report["warnings"][:12]:
        print(f"  warn: {x}")

    if not report["passed"]:
        return 1
    if args.strict and report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
