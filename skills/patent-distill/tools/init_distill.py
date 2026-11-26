# -*- coding: utf-8 -*-
"""新建蒸馏档案目录与未填完的骨架。填完后跑 validate_distill.py。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from distill_paths import default_output_root, normalize_profile_id, profile_dir_for
from stdio_utf8 import ensure_utf8_stdio


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def empty_profile(
    *,
    profile_id: str,
    patent_type: str,
    ownership: str,
    tracks: list[str],
) -> dict[str, Any]:
    style_on = "style" in tracks
    strategy_on = "strategy" in tracks
    strength = "observe" if strategy_on and ownership == "third_party" else "none"
    return {
        "schema": "patent-distill",
        "version": 1,
        "profile_id": profile_id,
        "patent_type": patent_type,
        "ownership": ownership,
        "suggested_industry": "",
        "industry": "",
        "industry_confirmed": False,
        "samples_confirmed": False,
        "tracks": tracks,
        "inputs": [],
        "evidence": {
            "has_disclosure": False,
            "has_application": False,
            "has_publication": False,
            "publication_pair": False,
            "has_family": False,
        },
        "style": {
            "enabled": style_on,
            "kinds": [],
            "status": "draft",
        },
        "strategy": {
            "enabled": strategy_on,
            "strength": strength,
            "status": "draft",
        },
    }


def empty_playbook(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "patent-distill-playbook",
        "version": 1,
        "profile_id": profile["profile_id"],
        "patent_type": profile["patent_type"],
        "status": "draft",
        "strength": profile["strategy"]["strength"],
        "must_not_copy": [
            "样本权要原文",
            "样本数值、件号、产品名",
            "推测栏结论",
        ],
        "claims": {
            "independent_grain": "method_steps",
            "independent_count": "single",
            "dependent_layers": ["preferred_param"],
            "leave_in_spec": ["extra_embodiment"],
            "never_in_independent": ["numeric_range"],
        },
        "spec": {
            "support_rule": "every_independent_limitation_has_embodiment",
            "extra_embodiments": True,
            "figure_binding": "claim_order",
        },
        "disclosure": {
            "point_split": "necessary_vs_preferred",
            "points_per_disclosure": "one_core",
            "unclaimed_in_chapter6": True,
        },
        "layout": {"enabled": False, "pattern": ""},
        "apply": {
            "when_writing_disclosure": "TODO",
            "when_writing_claims": "TODO",
            "when_writing_spec": "TODO",
        },
    }


def init_profile(
    *,
    profile_id: str,
    patent_type: str,
    ownership: str,
    tracks: list[str],
    root: Path | None = None,
    force: bool = False,
) -> Path:
    slug = normalize_profile_id(profile_id)
    directory = profile_dir_for(slug, root=root)
    if directory.exists() and any(directory.iterdir()) and not force:
        raise FileExistsError(f"档案已存在: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sections").mkdir(exist_ok=True)
    profile = empty_profile(
        profile_id=slug,
        patent_type=patent_type,
        ownership=ownership,
        tracks=tracks,
    )
    _dump(directory / "profile.yaml", profile)
    if "style" in tracks:
        (directory / "style.md").write_text("# 文风\n\nTODO\n", encoding="utf-8")
        (directory / "samples.md").write_text("# 样本\n\nTODO\n", encoding="utf-8")
    if "strategy" in tracks:
        (directory / "策略观察.md").write_text("# 策略观察\n\nTODO\n", encoding="utf-8")
        _dump(directory / "playbook.yaml", empty_playbook(profile))
    return directory


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="新建专利蒸馏档案骨架")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--patent-type", required=True, choices=["invention", "utility_model", "design"])
    parser.add_argument("--ownership", required=True, choices=["own", "third_party"])
    parser.add_argument("--tracks", required=True, help="style,strategy 或其中之一")
    parser.add_argument("--out-root", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    tracks = [part.strip() for part in str(args.tracks).split(",") if part.strip()]
    allowed = {"style", "strategy"}
    if not tracks or any(part not in allowed for part in tracks):
        print("DISTILL_ERROR: tracks 只能是 style 与 strategy", file=sys.stderr)
        return 2
    if "style" in tracks and args.ownership != "own":
        print("DISTILL_ERROR: 文风轨道只用于申请文件档案", file=sys.stderr)
        return 2
    root = Path(args.out_root) if args.out_root else default_output_root()
    try:
        directory = init_profile(
            profile_id=args.profile_id,
            patent_type=args.patent_type,
            ownership=args.ownership,
            tracks=tracks,
            root=root,
            force=args.force,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"DISTILL_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"DISTILL_DIR: {directory.as_posix()}")
    print(f"DISTILL_PROFILE: {(directory / 'profile.yaml').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
