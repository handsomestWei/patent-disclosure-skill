#!/usr/bin/env python
"""权要 / 说明书 / 附图机械对照。语义是否写够仍靠 prompts/consistency.md。

用法：
  python tools/check_support.py --dir outputs/patent-application/{案}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stdio_utf8 import ensure_utf8_stdio
from lexicon import promo_pattern
from check_numeral_register import check_register, _load_mapping as _load_register
from plan_figures import validate_plan as validate_figure_plan

PROMO = promo_pattern()
STEP_LABEL = re.compile(
    r"步骤([一二三四五六七八九十百零\d]+)[，, ]*([^；;。.\n]{0,40})"
)
FIG_REF = re.compile(r"图\s*([0-9]+)")
CLAIM_START = re.compile(r"(?m)^\s*(\d+)\s*[.、．]\s*")
CN_CHARS = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


@dataclass
class Finding:
    level: str
    code: str
    message: str


def _load_plan(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    import yaml

    data = yaml.safe_load(text) or {}
    return data if isinstance(data, dict) else {}


def _split_claims(text: str) -> dict[int, str]:
    matches = list(CLAIM_START.finditer(text))
    claims: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        claims[int(match.group(1))] = text[match.end() : end]
    return claims


def _first_independent_system(claims: dict[int, str]) -> str:
    for number, body in claims.items():
        if number == 1:
            continue
        if "权利要求" in body.replace(" ", "")[:20]:
            continue
        if "系统" in body[:40] or "装置" in body[:40]:
            return body
    return ""


def _step_map(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in STEP_LABEL.finditer(text):
        key = match.group(1)
        tail = re.sub(r"\s+", "", match.group(2) or "")
        if key not in out:
            out[key] = tail
    return out


def _flowchart_step_map(plan: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for fig in plan.get("figures") or []:
        if not isinstance(fig, dict) or fig.get("kind") != "flowchart":
            continue
        for node in fig.get("nodes") or []:
            if isinstance(node, dict):
                out.update(_step_map(str(node.get("label") or "")))
    return out


def _block_labels(plan: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for fig in plan.get("figures") or []:
        if not isinstance(fig, dict) or fig.get("kind") != "block_diagram":
            continue
        for col in list(fig.get("columns") or []) + list(fig.get("extras") or []):
            if not isinstance(col, dict):
                continue
            for node in col.get("nodes") or []:
                if isinstance(node, dict) and node.get("label"):
                    labels.append(str(node["label"]).strip())
    return labels


def _fig_numbers(plan: dict[str, Any]) -> list[int]:
    nums: list[int] = []
    for fig in plan.get("figures") or []:
        if isinstance(fig, dict) and fig.get("fig") is not None:
            try:
                nums.append(int(fig["fig"]))
            except (TypeError, ValueError):
                continue
    return nums


def _abstract_plain(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"[#>*_`]", "", text)
    return text


def audit_dir(root: Path, *, case_dir: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    claims_path = root / "权利要求书.md"
    spec_path = root / "说明书.md"
    abstract_path = root / "说明书摘要.md"
    plan_path = root / "figures" / "invention_figures.yaml"
    if not plan_path.is_file():
        plan_path = root / "figures" / "invention_figures.json"

    if not claims_path.is_file():
        return [Finding("ERROR", "NO_CLAIMS_FILE", "未找到权利要求书.md")]
    if not spec_path.is_file():
        return [Finding("ERROR", "NO_SPEC_FILE", "未找到说明书.md")]

    claims_text = claims_path.read_text(encoding="utf-8")
    spec_text = spec_path.read_text(encoding="utf-8")
    claims = _split_claims(claims_text)
    claim1 = claims.get(1, "")
    plan = _load_plan(plan_path) if plan_path.is_file() else {}

    # 权要写法两式择优（application_plan.claim_style）：numbered=独权步骤N编号；
    # unnumbered=独权分号连接不编号、实施例 S1。声明与正文不一致时报错。
    claim_style = ""
    app_plan_path = root / "application_plan.yaml"
    if not app_plan_path.is_file():
        app_plan_path = root / "application_plan.yml"
    if not app_plan_path.is_file():
        app_plan_path = root / "application_plan.json"
    if app_plan_path.is_file():
        try:
            app_plan_meta = _load_plan(app_plan_path)
        except (OSError, ValueError, json.JSONDecodeError):
            app_plan_meta = {}
        claim_style = str(app_plan_meta.get("claim_style") or "").strip().lower()
    claim_steps = _step_map(claim1)
    if claim_style == "numbered" and not claim_steps:
        findings.append(
            Finding(
                "ERROR",
                "CLAIM_STYLE_MISMATCH",
                "application_plan 记 claim_style=numbered，但独权未见「步骤N」编号。",
            )
        )
    if claim_style == "unnumbered" and claim_steps:
        findings.append(
            Finding(
                "ERROR",
                "CLAIM_STYLE_MISMATCH",
                "application_plan 记 claim_style=unnumbered，但独权出现了「步骤N」编号。",
            )
        )
    flow_steps = _flowchart_step_map(plan)
    if claim_steps and flow_steps:
        if list(claim_steps.keys()) != list(flow_steps.keys()):
            findings.append(
                Finding(
                    "ERROR",
                    "STEP_MISMATCH",
                    f"独权步骤序 {list(claim_steps)} 与流程图 {list(flow_steps)} 不一致。",
                )
            )
        else:
            for key, claim_tail in claim_steps.items():
                flow_tail = flow_steps.get(key, "")
                if claim_tail and flow_tail and claim_tail not in flow_tail and flow_tail not in claim_tail:
                    findings.append(
                        Finding(
                            "ERROR",
                            "STEP_MISMATCH",
                            f"步骤{key} 独权「{claim_tail}」与流程图「{flow_tail}」不同义。",
                        )
                    )
    elif claim_steps and not flow_steps and plan.get("figures"):
        findings.append(
            Finding("WARNING", "NO_FLOW_STEPS", "独权有步骤一…，流程图节点未检出步骤标签。")
        )
    elif flow_steps and not claim_steps and not claim_style:
        findings.append(
            Finding(
                "WARNING",
                "STEP_STYLE_UNVERIFIED",
                "独权未用「步骤N」编号（不编号式），流程图却带步骤标签；独权与图无法机械对照，"
                "人工核同义后在 application_plan 记 claim_style。",
            )
        )

    sys_claim = _first_independent_system(claims)
    for label in _block_labels(plan):
        if label and label not in spec_text:
            findings.append(
                Finding("ERROR", "MODULE_MISSING_SPEC", f"框图模块「{label}」未出现在说明书。")
            )
        if sys_claim and label and label not in sys_claim:
            findings.append(
                Finding("WARNING", "MODULE_MISSING_CLAIM", f"框图模块「{label}」未出现在系统独立权项。")
            )

    fig_nums = _fig_numbers(plan)
    if not fig_nums:
        fig_nums = []
        for png in sorted((root / "figures").glob("图*.png")):
            match = re.search(r"图(\d+)", png.name)
            if match:
                fig_nums.append(int(match.group(1)))
    spec_figs = {int(n) for n in FIG_REF.findall(spec_text)}
    for num in fig_nums:
        if num not in spec_figs:
            findings.append(
                Finding("ERROR", "FIG_UNMENTIONED", f"说明书未点到图{num}（附图说明或实施例）。")
            )

    if abstract_path.is_file():
        plain = _abstract_plain(abstract_path.read_text(encoding="utf-8"))
        nchars = len(CN_CHARS.findall(plain))
        if nchars > 300:
            findings.append(
                Finding("ERROR", "ABSTRACT_TOO_LONG", f"摘要约 {nchars} 字，应不超过 300 字。")
            )
        if PROMO.search(plain):
            findings.append(
                Finding("WARNING", "ABSTRACT_PROMO", "摘要含宣传性措辞。")
            )
        if "摘要附图" not in abstract_path.read_text(encoding="utf-8") and not (
            root / "figures" / "摘要附图.png"
        ).is_file():
            findings.append(Finding("WARNING", "NO_ABSTRACT_FIG", "未找到摘要附图.png。"))
    else:
        findings.append(Finding("WARNING", "NO_ABSTRACT", "未找到说明书摘要.md。"))

    app_plan_path = root / "figures" / "figure_plan.yaml"
    if not app_plan_path.is_file():
        app_plan_path = root / "figures" / "figure_plan.json"
    if app_plan_path.is_file():
        app_plan = _load_plan(app_plan_path)
        findings.extend(
            Finding(item.level, item.code, item.message) for item in validate_figure_plan(app_plan)
        )
        planned_figs = {
            int(item["fig"]): item
            for item in (app_plan.get("figures") or [])
            if isinstance(item, dict) and item.get("fig") is not None
        }
        inv_figs = set(fig_nums)
        for fig, item in planned_figs.items():
            kind = str(item.get("kind") or "")
            if str(item.get("source") or "") == "pending":
                continue
            has_file = (root / "figures" / f"图{fig}.png").is_file() or (
                root / "figures" / f"图{fig}.svg"
            ).is_file()
            if kind in {"flowchart", "block_diagram", "source_image"} and fig not in inv_figs and not has_file:
                findings.append(
                    Finding("ERROR", "FIG_PLAN_MISSING", f"figure_plan 图{fig}（{kind}）未写入 invention_figures 也未出图。")
                )
            elif kind not in {"flowchart", "block_diagram", "source_image"} and not has_file:
                findings.append(
                    Finding(
                        "WARNING",
                        "FIG_PLAN_MISSING",
                        f"figure_plan 图{fig}（{kind}）尚未按交底线稿升格出图；无源图则改记 pending。",
                    )
                )

    register_path = None
    for name in ("件号登记表.yaml", "件号登记表.yml", "件号登记表.json"):
        cand = root / name
        if cand.is_file():
            register_path = cand
            break
    if register_path is not None:
        schema = None
        for search_root in ([case_dir] if case_dir else []) + [root]:
            for name in ("structure_schema.yaml", "structure_schema.yml", "structure_schema.json"):
                cand = search_root / name
                if cand.is_file():
                    schema = _load_register(cand)
                    break
            if schema is not None:
                break
        fig_plan_path = app_plan_path if app_plan_path.is_file() else None
        if fig_plan_path is None:
            for name in ("figure_plan.yaml", "figure_plan.json"):
                cand = root / name
                if cand.is_file():
                    fig_plan_path = cand
                    break
        register = _load_register(register_path)
        fig_plan = _load_register(fig_plan_path) if fig_plan_path else None
        if fig_plan is not None:
            for item in fig_plan.get("figures") or []:
                if isinstance(item, dict) and "use_in_disclosure" not in item:
                    item["use_in_disclosure"] = True
        findings.extend(check_register(register, schema=schema, figure_plan=fig_plan, claims_text=claims_text, spec_text=spec_text))

    return findings


def summarize(findings: list[Finding]) -> tuple[int, int]:
    errors = sum(item.level == "ERROR" for item in findings)
    warnings = sum(item.level == "WARNING" for item in findings)
    return errors, warnings


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument(
        "--case-dir",
        type=Path,
        default=None,
        help="同案交底目录；实用新型传入后，件号登记表会与其 structure_schema 交叉核对",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.dir.expanduser().resolve()
    if not root.is_dir():
        print("APPLICATION_SUPPORT: ok=0 errors=1 warnings=0")
        print(f"目录不存在：{root}", file=sys.stderr)
        return 1
    case_dir = args.case_dir.expanduser().resolve() if args.case_dir else None
    if case_dir is not None and not case_dir.is_dir():
        print("APPLICATION_SUPPORT: ok=0 errors=1 warnings=0")
        print(f"交底目录不存在：{case_dir}", file=sys.stderr)
        return 1
    findings = audit_dir(root, case_dir=case_dir)
    errors, warnings = summarize(findings)
    ok = errors == 0
    numeral_codes = {
        "DUP_ID",
        "EMPTY_ID",
        "EMPTY_NAME",
        "SCHEMA_MISSING",
        "REGISTER_EXTRA",
        "NAME_MISMATCH",
        "FIG_UNREGISTERED",
        "FIG_UNKNOWN",
        "COVERS_MISMATCH",
        "CLAIM_MARK_MISSING",
        "CLAIM_UNLISTED",
        "SPEC_MARK_MISSING",
        "SPEC_UNFLAGGED",
        "SPEC_UNCHECKED",
        "EMPTY_REGISTER",
        "CROSS_NAME",
        "MARK_UNREGISTERED",
        "NAME_SPLIT",
        "OCCURRENCE_NAME",
    }
    numeral = [item for item in findings if item.code in numeral_codes]
    report = root / "标号核对.md"
    lines = ["# 标号核对", "", "件号 ↔ 部件名 ↔ 权要/说明书每一次「名称（号）」。机器通过不等于可提交。", ""]
    if not numeral:
        lines.append("未见结构性串号、未登记号或跨图名称冲突。")
    else:
        for item in numeral:
            lines.append(f"- **{item.level}** `{item.code}` {item.message}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"APPLICATION_SUPPORT: ok={1 if ok else 0} errors={errors} warnings={warnings}")
    if args.json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
    elif not findings:
        print("PASS: 机械对照未发现问题。机器通过不等于充分公开。")
    else:
        for item in findings:
            print(f"{item.level}\t{item.code}\t{item.message}")
        print(f"汇总: {errors} 个错误, {warnings} 个警告。机器通过不等于充分公开。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
