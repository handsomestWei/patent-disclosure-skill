# -*- coding: utf-8 -*-
"""读入本地文件，合并申请文风，并按案件拆开思路档案。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from classify_inputs import classify_file, plan_batch, read_full_text
from distill_paths import default_output_root, normalize_profile_id
from init_distill import empty_playbook, init_profile
from stdio_utf8 import ensure_utf8_stdio


def _suggest_id(paths: list[Path]) -> str:
    stem = re.sub(r'[\\/:*?"<>|\s]+', "-", paths[0].stem).strip(".-")
    return (stem or "distill")[:80]


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="按文件自动判断并新建蒸馏档案")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--profile-id", default="")
    parser.add_argument("--ownership", default="", choices=["", "own", "third_party"])
    parser.add_argument("--out-root", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    files = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            print(f"DISTILL_ERROR: 文件不存在: {raw}", file=sys.stderr)
            return 2
        files.append(classify_file(path))
    batch_id = args.profile_id.strip() or _suggest_id([Path(item) for item in args.paths])
    try:
        batch_id = normalize_profile_id(batch_id)
    except ValueError as exc:
        print(f"DISTILL_ERROR: {exc}", file=sys.stderr)
        return 2
    planned = plan_batch(files, batch_id=batch_id, ownership=args.ownership)
    for item in files:
        print(
            f"DISTILL_ROLE: {item['path']} {item['role'] or '-'} "
            f"{item['patent_type'] or '-'} {item['reason']}"
        )
    if planned["asks"]:
        for ask in planned["asks"]:
            print(f"DISTILL_ASK: {ask}", file=sys.stderr)
        return 3
    root = Path(args.out_root) if args.out_root else default_output_root()
    style = planned["style"]
    try:
        if style is not None:
            batch_dir = init_profile(
                profile_id=batch_id,
                patent_type=style["patent_type"],
                ownership="own",
                tracks=["style"],
                root=root,
                force=args.force,
            )
            _dump(batch_dir / "profile.yaml", style)
        else:
            batch_dir = root / batch_id
            if batch_dir.exists() and any(batch_dir.iterdir()) and not args.force:
                raise FileExistsError(f"档案已存在: {batch_dir}")
            batch_dir.mkdir(parents=True, exist_ok=True)
        case_rows = []
        for case in planned["cases"]:
            case_dir = init_profile(
                profile_id=case["profile_id"],
                patent_type=case["patent_type"],
                ownership=case["ownership"],
                tracks=["strategy"],
                root=batch_dir / "cases",
                force=args.force,
            )
            _dump(case_dir / "profile.yaml", case)
            playbook = case_dir / "playbook.yaml"
            if case["strategy"].get("callable") is True:
                _dump(playbook, empty_playbook(case))
            elif playbook.is_file():
                playbook.unlink()
            parts = []
            for item in case.get("inputs") or []:
                source = str(item.get("path") or "")
                if source and Path(source).is_file():
                    parts.append(read_full_text(Path(source)))
            if parts:
                (case_dir / "全文.txt").write_text("\n\n".join(parts), encoding="utf-8")
            laid = str((case.get("evidence") or {}).get("laid_open_pub") or "")
            grant = str((case.get("evidence") or {}).get("grant_pub") or "")
            if laid and grant and not (case.get("evidence") or {}).get("pair_in_batch"):
                print(f"DISTILL_NOTE: 扉页同时有 {laid} 与 {grant}，本批只有其中一份，时间轴不比较两稿")
            case_rows.append({"case_id": case["profile_id"], "dir": f"cases/{case['profile_id']}"})
            print(f"DISTILL_CASE: {case['profile_id']} {case_dir.as_posix()}")
    except (ValueError, FileExistsError) as exc:
        print(f"DISTILL_ERROR: {exc}", file=sys.stderr)
        return 2
    _dump(
        batch_dir / "batch.yaml",
        {
            "schema": "patent-distill-batch",
            "version": 1,
            "batch_id": batch_id,
            "patent_type": planned["patent_type"],
            "style_dir": "." if style is not None else "",
            "cases": case_rows,
        },
    )
    print(f"DISTILL_TYPE: {planned['patent_type']}")
    if style is not None:
        print("DISTILL_STYLE: " + batch_dir.as_posix())
    print(f"DISTILL_DIR: {batch_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
