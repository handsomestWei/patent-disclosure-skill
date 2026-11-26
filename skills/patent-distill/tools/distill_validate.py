# -*- coding: utf-8 -*-
"""校验 profile.yaml 与 playbook.yaml。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from distill_spec import choice, load_contract

_APPLICATION_PIECES = {"权利要求书", "说明书", "说明书摘要", "说明书附图"}

_APPLY_KEYS = ("when_writing_disclosure", "when_writing_claims", "when_writing_spec")
_MAX_APPLY = 400
_MAX_SHORT = 80


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} 须为对象")
    return data


def _enums_ok(value: str, name: str, errors: list[str], label: str) -> None:
    if value not in choice(name):
        errors.append(f"{label} 不在允许值内")


def _list_enums(values: Any, name: str, errors: list[str], label: str) -> None:
    if not isinstance(values, list):
        errors.append(f"{label} 须为列表")
        return
    allowed = choice(name)
    for item in values:
        if str(item) not in allowed:
            errors.append(f"{label} 含非法值: {item}")


def _same_application_bundle(inputs: list[dict[str, Any]]) -> bool:
    apps = [item for item in inputs if isinstance(item, dict) and item.get("role") == "application"]
    if len(apps) <= 1:
        return True
    stems = {Path(str(item.get("path") or "")).stem for item in apps}
    parents = {str(Path(str(item.get("path") or "")).parent) for item in apps}
    return stems <= _APPLICATION_PIECES and len(parents) == 1


def evidence_from_inputs(inputs: list[dict[str, Any]]) -> dict[str, bool]:
    roles = {str(item.get("role") or "") for item in inputs}
    return {
        "has_disclosure": "disclosure" in roles,
        "has_application": "application" in roles,
        "has_publication": bool(roles & {"publication", "publication_a", "publication_b"}),
        "publication_pair": "publication_a" in roles and "publication_b" in roles,
        "has_family": False,
    }


def expected_strength(profile: dict[str, Any]) -> str:
    strategy = profile.get("strategy") or {}
    if not strategy.get("enabled"):
        return "none"
    evidence = profile.get("evidence") or {}
    if profile.get("ownership") == "third_party":
        return "observe"
    has_claims = bool(evidence.get("has_application") or evidence.get("has_publication"))
    if evidence.get("has_disclosure") and has_claims:
        return "strong"
    if has_claims:
        return "weak"
    return "none"


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = load_contract()
    if profile.get("schema") != contract["schema_profile"]:
        errors.append("schema 须为 patent-distill")
    if profile.get("version") not in (1, "1"):
        errors.append("version 须为 1")
    if not str(profile.get("profile_id") or "").strip():
        errors.append("缺少 profile_id")
    _enums_ok(str(profile.get("patent_type") or ""), "patent_type", errors, "patent_type")
    _enums_ok(str(profile.get("ownership") or ""), "ownership", errors, "ownership")
    tracks = profile.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("tracks 至少一项")
        tracks = []
    else:
        _list_enums(tracks, "tracks", errors, "tracks")
    if str(profile.get("industry") or "") and profile.get("industry_confirmed") is not True:
        errors.append("填写 industry 前须 industry_confirmed: true")

    inputs = profile.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append("inputs 至少一条")
        inputs = []
    for i, item in enumerate(inputs):
        if not isinstance(item, dict):
            errors.append(f"inputs[{i}] 须为对象")
            continue
        _enums_ok(str(item.get("role") or ""), "input_role", errors, f"inputs[{i}].role")
        if not str(item.get("path") or "").strip():
            errors.append(f"inputs[{i}] 缺少 path")

    evidence = profile.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("缺少 evidence")
        evidence = {}
    derived = evidence_from_inputs([item for item in inputs if isinstance(item, dict)])
    derived["has_family"] = evidence.get("has_family") is True
    for key in ("has_disclosure", "has_application", "has_publication", "publication_pair"):
        if evidence.get(key) is not derived[key]:
            errors.append(f"evidence.{key} 与 inputs 不一致")

    style = profile.get("style") if isinstance(profile.get("style"), dict) else {}
    strategy = profile.get("strategy") if isinstance(profile.get("strategy"), dict) else {}
    if not style or not strategy:
        errors.append("style 与 strategy 都要写，未启用则 enabled: false")
    style_on = style.get("enabled") is True
    strategy_on = strategy.get("enabled") is True
    if tracks not in (["style"], ["strategy"]):
        errors.append("tracks 为 style 或 strategy")
    if ("style" in tracks) != style_on:
        errors.append("tracks 与 style.enabled 不一致")
    if ("strategy" in tracks) != strategy_on:
        errors.append("tracks 与 strategy.enabled 不一致")

    if style_on:
        if profile.get("ownership") != "own":
            errors.append("文风档案的 ownership 是 own")
        kinds = style.get("kinds")
        if kinds != ["application"]:
            errors.append("style.kinds 为 application")
        roles = [str(item.get("role") or "") for item in inputs if isinstance(item, dict)]
        if not roles or any(role != "application" for role in roles):
            errors.append("文风档案的 inputs 角色是 application")
        _enums_ok(str(style.get("status") or ""), "status", errors, "style.status")
        if style.get("status") == "confirmed" and profile.get("samples_confirmed") is not True:
            errors.append("文风标 confirmed 前须 samples_confirmed: true")
    if strategy_on:
        app_count = sum(1 for item in inputs if isinstance(item, dict) and item.get("role") == "application")
        disclosure_count = sum(1 for item in inputs if isinstance(item, dict) and item.get("role") == "disclosure")
        if app_count > 1 and not _same_application_bundle(inputs):
            errors.append("案件档案收一份申请文件")
        if disclosure_count > 1:
            errors.append("案件档案收一份交底")
        if not (derived["has_application"] or derived["has_publication"]):
            errors.append("思路档案收申请文件或公开文本")
        strength = expected_strength({**profile, "evidence": {**evidence, **derived}})
        if str(strategy.get("strength") or "") != strength:
            errors.append(f"strategy.strength 应为 {strength}")
        _enums_ok(str(strategy.get("status") or ""), "status", errors, "strategy.status")
        if strategy.get("status") == "confirmed":
            if strength == "observe" or profile.get("ownership") != "own":
                errors.append("观察档的思路只能是 draft")
            if profile.get("samples_confirmed") is not True:
                errors.append("思路标 confirmed 前须 samples_confirmed: true")
            if strength not in {"weak", "strong"}:
                errors.append("可调用思路档的 strength 只能是 weak 或 strong")
        if strength == "observe" and strategy.get("callable") is not False:
            errors.append("观察档 strategy.callable 为 false")
        if strength in {"weak", "strong"} and strategy.get("callable") is not True:
            errors.append("可调用思路档 strategy.callable 为 true")
    elif str(strategy.get("strength") or "none") != "none":
        errors.append("未启用思路时 strength 须为 none")
    return errors


def validate_playbook(playbook: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = load_contract()
    if playbook.get("schema") != contract["schema_playbook"]:
        errors.append("playbook.schema 须为 patent-distill-playbook")
    if playbook.get("version") not in (1, "1"):
        errors.append("playbook.version 须为 1")
    if playbook.get("profile_id") != profile.get("profile_id"):
        errors.append("playbook.profile_id 与档案不一致")
    if playbook.get("patent_type") != profile.get("patent_type"):
        errors.append("playbook.patent_type 与档案不一致")
    strategy = profile.get("strategy") or {}
    if playbook.get("status") != strategy.get("status"):
        errors.append("playbook.status 与 strategy.status 不一致")
    if playbook.get("strength") != strategy.get("strength"):
        errors.append("playbook.strength 与 strategy.strength 不一致")

    banned = playbook.get("must_not_copy")
    if not isinstance(banned, list) or len(banned) < 3:
        errors.append("must_not_copy 至少三条")
    else:
        for item in banned:
            if "TODO" in str(item):
                errors.append("must_not_copy 仍含 TODO")

    claims = playbook.get("claims")
    spec = playbook.get("spec")
    disclosure = playbook.get("disclosure")
    layout = playbook.get("layout")
    apply = playbook.get("apply")
    if not all(isinstance(block, dict) for block in (claims, spec, disclosure, layout, apply)):
        errors.append("claims、spec、disclosure、layout、apply 都要是对象")
        return errors

    _enums_ok(str(claims.get("independent_grain") or ""), "independent_grain", errors, "independent_grain")
    _enums_ok(str(claims.get("independent_count") or ""), "independent_count", errors, "independent_count")
    _list_enums(claims.get("dependent_layers"), "dependent_layer", errors, "dependent_layers")
    _list_enums(claims.get("leave_in_spec"), "leave_in_spec", errors, "leave_in_spec")
    _list_enums(claims.get("never_in_independent"), "never_in_independent", errors, "never_in_independent")
    _enums_ok(str(spec.get("support_rule") or ""), "support_rule", errors, "support_rule")
    if not isinstance(spec.get("extra_embodiments"), bool):
        errors.append("spec.extra_embodiments 须为布尔")
    _enums_ok(str(spec.get("figure_binding") or ""), "figure_binding", errors, "figure_binding")
    _enums_ok(str(disclosure.get("point_split") or ""), "point_split", errors, "point_split")
    _enums_ok(str(disclosure.get("points_per_disclosure") or ""), "points_per_disclosure", errors, "points_per_disclosure")
    if not isinstance(disclosure.get("unclaimed_in_chapter6"), bool):
        errors.append("disclosure.unclaimed_in_chapter6 须为布尔")

    if layout.get("enabled") is True:
        if (profile.get("evidence") or {}).get("has_family") is not True:
            errors.append("没有同族或周边案时 layout.enabled 须为 false")
        _enums_ok(str(layout.get("pattern") or ""), "layout_pattern", errors, "layout.pattern")
    elif layout.get("pattern") not in ("", None):
        errors.append("layout 未启用时 pattern 留空")

    for key in _APPLY_KEYS:
        text = str(apply.get(key) or "").strip()
        if not text or "TODO" in text:
            errors.append(f"apply.{key} 须写成可执行短指令")
        elif len(text) > _MAX_APPLY:
            errors.append(f"apply.{key} 超过 {_MAX_APPLY} 字")
    for block_name, block in (("claims", claims), ("spec", spec), ("disclosure", disclosure)):
        for key, value in block.items():
            if isinstance(value, str) and len(value) > _MAX_SHORT:
                errors.append(f"{block_name}.{key} 过长，疑似写入了样本原文")
    return errors


def validate_batch(directory: Path) -> list[str]:
    batch_path = directory / "batch.yaml"
    if not batch_path.is_file():
        return validate_dir(directory)
    batch = yaml.safe_load(batch_path.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    if batch.get("style_dir") == ".":
        errors.extend(validate_dir(directory))
    for case in batch.get("cases") or []:
        if not isinstance(case, dict):
            errors.append("batch.cases 项须为对象")
            continue
        case_dir = directory / str(case.get("dir") or "")
        for item in validate_dir(case_dir):
            errors.append(f"{case.get('case_id')}: {item}")
    return errors


def validate_dir(directory: Path) -> list[str]:
    errors: list[str] = []
    profile_path = directory / "profile.yaml"
    if not profile_path.is_file():
        return ["缺少 profile.yaml"]
    profile = load_yaml(profile_path)
    errors.extend(validate_profile(profile))
    for item in profile.get("inputs") or []:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if not path.is_file():
            errors.append(f"输入文件不存在: {raw}")

    style = profile.get("style") or {}
    strategy = profile.get("strategy") or {}
    if style.get("enabled") is True:
        style_md = directory / "style.md"
        if not style_md.is_file() or "TODO" in style_md.read_text(encoding="utf-8"):
            errors.append("style.md 未写完")
        samples_path = directory / "samples.md"
        if not samples_path.is_file() or "TODO" in samples_path.read_text(encoding="utf-8"):
            errors.append("samples.md 未写完")
        else:
            samples_text = samples_path.read_text(encoding="utf-8")
            for item in profile.get("inputs") or []:
                if isinstance(item, dict) and str(item.get("path") or "") not in samples_text:
                    errors.append(f"samples.md 未列出 {item.get('path')}")
        section_files = ["sections/application.md"]
        for rel in section_files:
            section = directory / rel
            if not section.is_file() or "TODO" in section.read_text(encoding="utf-8"):
                errors.append(f"{rel} 未写完")
    if strategy.get("enabled") is True:
        note = directory / "策略观察.md"
        if not note.is_file() or "TODO" in note.read_text(encoding="utf-8"):
            errors.append("策略观察.md 未写完")
        playbook_path = directory / "playbook.yaml"
        if strategy.get("strength") == "observe":
            if playbook_path.is_file():
                errors.append("观察档的交付文件是策略观察.md")
        elif not playbook_path.is_file():
            errors.append("缺少 playbook.yaml")
        else:
            errors.extend(validate_playbook(load_yaml(playbook_path), profile))
    elif (directory / "playbook.yaml").is_file():
        errors.append("未启用思路时不要留下 playbook.yaml")
    return errors
