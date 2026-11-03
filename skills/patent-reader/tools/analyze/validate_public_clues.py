#!/usr/bin/env python
"""
校验并筛选 Agent 生成的 public_clues.json（附录 B 线索）。

默认按置信度高→低排序后最多保留 3 条；可用 --max 调整，--no-filter 关闭筛选。
线索带 region_group 时本国市场 / 申请人所在国优先，其他地区（other）只保留置信度「高」的。

用法：
  python skills/patent-reader/tools/analyze/validate_public_clues.py -i public_clues.json [-o public_clues.lint.json]
  python skills/patent-reader/tools/analyze/validate_public_clues.py -i public_clues.json --write-filtered
  python skills/patent-reader/tools/analyze/validate_public_clues.py -i public_clues.json --strict
"""
from __future__ import annotations

# Ensure tools/patent_reader is importable when run as a script.
from pathlib import Path as _Path
import sys as _sys

_PR_ROOT = _Path(__file__).resolve().parents[1]
if str(_PR_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PR_ROOT))

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from vault.clue_vault import (
        DEFAULT_MAX_CLUES,
        as_clues,
        filter_clues,
        normalize_clue,
    )
except ImportError:
    from tools.patent_reader.vault.clue_vault import (
        DEFAULT_MAX_CLUES,
        as_clues,
        filter_clues,
        normalize_clue,
    )

ALLOWED_CONF = {"高", "中", "低", "high", "medium", "low", "med", "mid"}
ALLOWED_REGION_GROUPS = {"market", "applicant_home", "other"}


def validate_clues(clues: list[dict]) -> dict:
    issues: list[str] = []
    warnings: list[str] = []

    if not clues:
        warnings.append("empty_clues_ok_if_none_found")
        return {"passed": True, "issues": issues, "warnings": warnings, "count": 0}

    for i, c in enumerate(clues):
        prefix = f"clue[{i}]"
        n = normalize_clue(c, index=i)
        title = n["title"]
        url = n["url"]
        conf = n["confidence"]
        reason = n["reason"]

        if not title:
            issues.append(f"{prefix}:missing_title")
        if not url:
            issues.append(f"{prefix}:missing_url")
        else:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                issues.append(f"{prefix}:invalid_url")
            if re.search(r"example\.com|localhost|127\.0\.0\.1", url, re.I):
                warnings.append(f"{prefix}:placeholder_url")
        if not conf:
            warnings.append(f"{prefix}:missing_confidence")
        elif conf.lower() not in {x.lower() for x in ALLOWED_CONF} and conf not in ALLOWED_CONF:
            warnings.append(f"{prefix}:unusual_confidence:{conf}")
        if not reason:
            warnings.append(f"{prefix}:missing_reason")
        elif len(reason) < 8:
            warnings.append(f"{prefix}:reason_too_short")
        # Agent 主路径应写入 summary；缺则提醒（不阻断，可由脚本降级）
        summary = (c.get("summary") or "").strip()
        status = (c.get("status") or "").strip()
        if not summary and status not in ("fetch_failed",):
            warnings.append(f"{prefix}:missing_summary_agent_should_fetch")
        group = (c.get("region_group") or "").strip()
        if group and group not in ALLOWED_REGION_GROUPS:
            warnings.append(f"{prefix}:unknown_region_group:{group}")
        if group and not (c.get("region") or "").strip():
            warnings.append(f"{prefix}:region_group_without_region")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "count": len(clues),
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", required=True, type=Path)
    ap.add_argument("-o", "--output", default=None, type=Path)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="warnings 也导致非零退出",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        default=True,
        help="允许空列表（表示未发现线索）",
    )
    ap.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX_CLUES,
        help=f"按置信度排序后最多保留条数（默认 {DEFAULT_MAX_CLUES}）",
    )
    ap.add_argument(
        "--no-filter",
        action="store_true",
        help="不做条数筛选（仍校验）",
    )
    ap.add_argument(
        "--write-filtered",
        action="store_true",
        help="将筛选后的线索写回 -i（或 --filtered-out）",
    )
    ap.add_argument(
        "--filtered-out",
        default=None,
        type=Path,
        help="筛选结果输出路径（默认与 --write-filtered 时覆盖 -i）",
    )
    args = ap.parse_args(argv)

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    clues = as_clues(raw)
    result = validate_clues(clues)

    kept = clues
    dropped: list[dict] = []
    if not args.no_filter:
        kept, dropped = filter_clues(clues, max_keep=max(0, args.max))
        if dropped:
            result["warnings"].append(
                f"filtered_to_{len(kept)}_dropped_{len(dropped)}"
            )
        result["count_before_filter"] = len(clues)
        result["count"] = len(kept)
        result["kept_titles"] = [c.get("title") for c in kept]
        result["dropped_titles"] = [c.get("title") for c in dropped]

    if args.write_filtered or args.filtered_out:
        out_path = args.filtered_out or args.input
        # 保持与输入同形：list 或 {clues:[]}
        payload: list | dict
        if isinstance(raw, dict) and not isinstance(raw, list):
            payload = {**raw, "clues": kept}
        else:
            payload = kept
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"FILTERED: {out_path} keep={len(kept)} drop={len(dropped)}")

    if args.output:
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    for w in result["warnings"]:
        print(f"WARN {w}", file=sys.stderr)
    if not result["passed"]:
        for i in result["issues"]:
            print(f"FAIL {i}", file=sys.stderr)
        return 1
    if args.strict and result["warnings"]:
        print("FAIL strict_warnings", file=sys.stderr)
        return 1

    print(f"OK public_clues count={result['count']}")
    if args.output:
        print(f"CLUES_LINT: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
