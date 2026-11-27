# -*- coding: utf-8 -*-
"""读取用户点名的专利蒸馏档，按写作阶段筛出可读的文风与思路文件。

只做机械筛选：档案在不在、专利类型是否一致、文风是否适用本阶段、
思路档可调用还是只作观察。是否适合本案由 prompts/distill_ref.md 逐条判断。
不修改蒸馏档。

用法：
  python tools/distill_ref.py --ref outputs/patent-distill/<档案id> --type invention --stage application
  python tools/distill_ref.py --ref <档案id> --ref <另一档案id> --type invention --stage disclosure
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stdio_utf8 import ensure_utf8_stdio

ENV_OUTPUT_DIR = "PATENT_DISTILL_OUTPUT_DIR"
STAGES = ("disclosure", "application")
TYPES = ("invention", "utility_model", "design")
APPLY_KEYS = {
    "disclosure": ("when_writing_disclosure",),
    "application": ("when_writing_claims", "when_writing_spec"),
}
BLOCKS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "disclosure": (("disclosure", ()), ("claims", ("never_in_independent",))),
    "application": (("claims", ()), ("spec", ())),
}
_ENTRY_FILES = {"profile.yaml", "batch.yaml", "playbook.yaml", "style.md", "samples.md", "策略观察.md"}


def distill_root() -> Path:
    env = (os.environ.get(ENV_OUTPUT_DIR) or "").strip()
    return Path(env) if env else Path.cwd() / "outputs" / "patent-distill"


def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _done(path: Path) -> bool:
    try:
        return path.is_file() and "TODO" not in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _is_archive(path: Path) -> bool:
    return path.is_dir() and ((path / "profile.yaml").is_file() or (path / "batch.yaml").is_file())


def resolve_ref(raw: str, root: Path | None = None) -> Path | None:
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    path = Path(text)
    if path.is_file() and path.name in _ENTRY_FILES:
        path = path.parent
    if _is_archive(path):
        return path
    base = root or distill_root()
    if any(sep in text for sep in ("/", "\\")):
        return None
    candidate = base / text
    if _is_archive(candidate):
        return candidate
    if base.is_dir():
        for case in sorted(base.glob(f"*/cases/{text}")):
            if _is_archive(case):
                return case
    return None


def _split(ref_dir: Path) -> tuple[Path | None, list[Path]]:
    batch = _load(ref_dir / "batch.yaml")
    if batch:
        cases = [
            ref_dir / str(item["dir"])
            for item in batch.get("cases") or []
            if isinstance(item, dict) and item.get("dir")
        ]
        return (ref_dir if batch.get("style_dir") == "." else None), cases
    profile = _load(ref_dir / "profile.yaml")
    tracks = profile.get("tracks") or []
    return (ref_dir if "style" in tracks else None), ([ref_dir] if "strategy" in tracks else [])


def _type_mismatch(profile: dict[str, Any], patent_type: str) -> str:
    found = str(profile.get("patent_type") or "")
    if patent_type and found and found != patent_type:
        return f"专利类型不同（档案为 {found}）"
    return ""


def inspect_style(style_dir: Path, *, patent_type: str, stage: str) -> dict[str, Any]:
    profile = _load(style_dir / "profile.yaml")
    row: dict[str, Any] = {
        "kind": "style",
        "id": str(profile.get("profile_id") or style_dir.name),
        "status": str((profile.get("style") or {}).get("status") or ""),
        "files": [],
        "reason": "",
    }
    if stage == "disclosure":
        row.update(verdict="skip", reason="交底不套申请文风")
        return row
    mismatch = _type_mismatch(profile, patent_type)
    if mismatch:
        row.update(verdict="skip", reason=mismatch)
        return row
    files = [style_dir / "style.md", style_dir / "sections" / "application.md"]
    if not all(_done(item) for item in files):
        row.update(verdict="skip", reason="文风文件缺失或未写完")
        return row
    row.update(verdict="use", files=files)
    return row


def _block_text(playbook: dict[str, Any], stage: str) -> list[str]:
    lines: list[str] = []
    for name, keys in BLOCKS[stage]:
        block = playbook.get(name)
        if not isinstance(block, dict):
            continue
        parts = []
        for key, value in block.items():
            if keys and key not in keys:
                continue
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            elif isinstance(value, bool):
                value = "true" if value else "false"
            parts.append(f"{key}={value}")
        if parts:
            lines.append(f"{name} " + " ".join(parts))
    return lines


def inspect_case(case_dir: Path, *, patent_type: str, stage: str) -> dict[str, Any]:
    profile = _load(case_dir / "profile.yaml")
    strategy = profile.get("strategy") or {}
    row: dict[str, Any] = {
        "kind": "case",
        "id": str(profile.get("profile_id") or case_dir.name),
        "status": str(strategy.get("status") or ""),
        "strength": str(strategy.get("strength") or ""),
        "files": [],
        "apply": {},
        "blocks": [],
        "reason": "",
    }
    if not profile:
        row.update(verdict="skip", reason="缺少 profile.yaml")
        return row
    mismatch = _type_mismatch(profile, patent_type)
    if mismatch:
        row.update(verdict="skip", reason=mismatch)
        return row
    if strategy.get("enabled") is not True:
        row.update(verdict="skip", reason="该档未启用思路")
        return row
    if stage == "application" and patent_type == "design":
        row.update(verdict="skip", reason="外观申请不写权要")
        return row
    strength = row["strength"]
    if strength == "observe":
        note = case_dir / "策略观察.md"
        if not _done(note):
            row.update(verdict="skip", reason="策略观察.md 缺失或未写完")
            return row
        row.update(verdict="observe", files=[note])
        return row
    if strength not in {"weak", "strong"}:
        row.update(verdict="skip", reason="该档没有可用思路")
        return row
    playbook_path = case_dir / "playbook.yaml"
    playbook = _load(playbook_path)
    if not playbook:
        row.update(verdict="skip", reason="缺少 playbook.yaml")
        return row
    apply = playbook.get("apply") or {}
    texts = {key: str(apply.get(key) or "").strip() for key in APPLY_KEYS[stage]}
    if any(not text or "TODO" in text for text in texts.values()):
        row.update(verdict="skip", reason="playbook 指令未写完")
        return row
    row.update(verdict="use", files=[playbook_path], apply=texts, blocks=_block_text(playbook, stage))
    return row


def inspect_ref(ref_dir: Path, *, patent_type: str, stage: str) -> list[dict[str, Any]]:
    style_dir, case_dirs = _split(ref_dir)
    rows: list[dict[str, Any]] = []
    if style_dir is not None:
        rows.append(inspect_style(style_dir, patent_type=patent_type, stage=stage))
    elif stage == "application":
        rows.append(
            {"kind": "style", "id": ref_dir.name, "verdict": "skip", "reason": "本档没有文风（只有申请文件合并文风）", "files": []}
        )
    for case_dir in case_dirs:
        rows.append(inspect_case(case_dir, patent_type=patent_type, stage=stage))
    if not rows:
        rows.append({"kind": "ref", "id": ref_dir.name, "verdict": "skip", "reason": "档案里没有文风或思路", "files": []})
    return rows


def _show(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="筛选写作可读的专利蒸馏档")
    parser.add_argument("--ref", action="append", required=True, help="档案目录或档案 id，可重复")
    parser.add_argument("--type", dest="patent_type", default="", choices=["", *TYPES])
    parser.add_argument("--stage", required=True, choices=STAGES)
    args = parser.parse_args(argv)
    counts = {"use": 0, "observe": 0, "skip": 0}
    for raw in args.ref:
        ref_dir = resolve_ref(raw)
        if ref_dir is None:
            counts["skip"] += 1
            print(f"DISTILL_REF_SKIP: {raw} reason=找不到蒸馏档")
            continue
        print(f"DISTILL_REF: {raw} dir={_show(ref_dir)}")
        for row in inspect_ref(ref_dir, patent_type=args.patent_type, stage=args.stage):
            verdict = row["verdict"]
            counts[verdict] += 1
            label = "DISTILL_REF_STYLE" if row["kind"] == "style" else "DISTILL_REF_CASE"
            if verdict == "skip":
                print(f"{label}: {row['id']} skip reason={row['reason']}")
                continue
            files = ",".join(_show(item) for item in row["files"])
            extra = f" strength={row['strength']}" if row["kind"] == "case" else ""
            print(f"{label}: {row['id']} {verdict} status={row['status'] or '-'}{extra} files={files}")
            for key, text in (row.get("apply") or {}).items():
                print(f"DISTILL_REF_APPLY: {row['id']} {key}={text}")
            for line in row.get("blocks") or []:
                print(f"DISTILL_REF_BLOCK: {row['id']} {line}")
    print(f"DISTILL_REF_SUMMARY: use={counts['use']} observe={counts['observe']} skip={counts['skip']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
