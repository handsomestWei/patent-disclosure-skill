#!/usr/bin/env python3
"""
专利解读笔记结构、免责声明、应用场景与附录粗校验。

用法：
  python tools/patent_reader/lint_patent_note.py --note out.md --manifest source_manifest.json \\
      --claim-tree claim_tree.json [--plan note_plan.json] [--context-anchor context_anchor.json] \\
      [--figures-manifest figures/manifest.json] [--output lint.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 按 ## 标题匹配，避免「特征」等裸词假阴性
REQUIRED_HEADINGS = [
    (re.compile(r"^##\s*Obsidian\s*导航\s*$", re.M | re.I), "Obsidian 导航"),
    (re.compile(r"^##\s*一、\s*一句话", re.M), "一句话"),
    (re.compile(r"^##\s*二、\s*连贯叙事", re.M), "连贯叙事"),
    (re.compile(r"^##\s*三、\s*权利要求树", re.M), "权利要求树"),
    (re.compile(r"^##\s*四、\s*独立权利要求精读", re.M), "独立权利要求精读"),
    (re.compile(r"^##\s*五、\s*专利内术语表", re.M), "专利内术语表"),
    (re.compile(r"^##\s*六、\s*特征", re.M), "特征—说明书—附图对照"),
    (re.compile(r"^##\s*八、\s*(?:给你的)?阅读建议", re.M), "阅读建议"),
    (re.compile(r"^##\s*九、\s*技术应用场景", re.M), "技术应用场景"),
    (re.compile(r"^##\s*十、\s*附录", re.M), "附录"),
    (re.compile(r"^##\s*十一、\s*免责声明", re.M), "免责声明"),
]

DISCLAIMER_PHRASES = (
    "不构成法律意见",
    "专利保护范围以官方法律文本为准",
    "重大决策请咨询专利代理师",
)

QUOTE_RE = re.compile(
    r"^>\s*【([A-Z]{2}\d+[A-Z]?\d?)·权利要求(\d+)】",
    re.M,
)


try:
    from common import optional_path
except ImportError:
    from tools.patent_reader.common import optional_path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--note", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--claim-tree", required=True, type=Path)
    ap.add_argument("--plan", default=None, type=optional_path)
    ap.add_argument("--context-anchor", default=None, type=optional_path)
    ap.add_argument("--figures-manifest", default=None, type=optional_path)
    ap.add_argument("--output", default=None, type=optional_path)
    args = ap.parse_args(argv)

    note = args.note.read_text(encoding="utf-8", errors="replace")
    manifest = load_json(args.manifest)
    tree = load_json(args.claim_tree)
    issues: list[str] = []
    warnings: list[str] = []

    for pat, label in REQUIRED_HEADINGS:
        if not pat.search(note):
            issues.append(f"missing_section:{label}")

    for phrase in DISCLAIMER_PHRASES:
        if phrase not in note:
            issues.append(f"disclaimer_missing:{phrase}")

    scope = manifest.get("evidence_scope", "")
    if scope == "abstract_only":
        if "权利要求" in note and "摘要级" not in note and "仅摘要" not in note:
            if re.search(r"保护范围", note):
                issues.append("abstract_only_but_claims_scope_asserted")

    ind_count = manifest.get("independent_claim_count", 0) or len(
        tree.get("roots") or []
    )
    if ind_count > 0 and "权利要求精读" in note:
        quotes = QUOTE_RE.findall(note)
        if len(quotes) < min(ind_count, 1):
            issues.append("missing_claim_quote_block")
        # 引文权项号应落在树节点上
        node_nums = {n.get("number") for n in (tree.get("nodes") or []) if n.get("number")}
        if node_nums:
            for _pub, num_s in quotes:
                try:
                    num = int(num_s)
                except ValueError:
                    continue
                if num not in node_nums:
                    warnings.append(f"quote_claim_not_in_tree:{num}")

    if "[!patent-meta]" not in note:
        issues.append("missing_callout:patent-meta")
    if "[!grounding]" not in note:
        issues.append("missing_callout:grounding")
    if "[!warning]" not in note and "warning]-" not in note:
        issues.append("missing_callout:warning")

    if "patent-reader" not in note[:1500]:
        issues.append("missing_cssclass:patent-reader")
    if "ipc:" not in note[:1200] and "IPC" not in note[:2500]:
        issues.append("missing_ipc_field")

    # 第三节：推荐单一树形表（缺则 warning）
    sec3 = re.search(r"##\s*三、权利要求树[\s\S]*?(?=##\s*四、)", note)
    if sec3:
        s3 = sec3.group(0)
        if "本项新增" not in s3 and "| 权 |" not in s3:
            warnings.append("section3_missing_claim_table")
        if "```mermaid" in s3 and "| 结构 |" in s3:
            warnings.append("section3_mermaid_and_table_redundant")

    # 交付正文不得暴露实现痕迹（脚本名 / 流水线字段 / 内部文件名说明）
    if re.search(
        r"`?[a-z_]+\.py`?|"
        r"context_anchor\.[a-z_]+|"
        r"第\s*\d+\s*页\s*[·•]\s*`?page_\d+_xref_",
        note,
        re.I,
    ):
        warnings.append("user_facing_internal_tool_leakage")


    # 第九节须含专利内依据标记
    sec9_m = re.search(r"##\s*九、技术应用场景[\s\S]*?(?=##\s*十、)", note)
    if sec9_m:
        sec9 = sec9_m.group(0)
        if not re.search(
            r"desc_|实施例|背景|说明书\s*\d{4}|说明书段落",
            sec9,
        ):
            issues.append("section9_missing_patent_grounding")
        if re.search(r"https?://", sec9):
            issues.append("section9_contains_url_use_appendix_b")

    # 附录 A IPC
    if "IPC" not in note and "行业坐标" not in note:
        issues.append("appendix_missing_ipc")

    # 附录 B：有线索须有 URL，或无发现说明
    appendix_m = re.search(r"##\s*十、附录[\s\S]*?(?=##\s*十一、免责声明)", note)
    if appendix_m:
        appendix = appendix_m.group(0)
        has_clue = re.search(r"置信度", appendix) or "线索" in appendix
        has_url = "http" in appendix
        has_none = "未发现" in appendix or "防御性" in appendix
        if has_clue and not has_url and not has_none:
            issues.append("appendix_b_missing_url_or_none_statement")

    if args.plan and args.plan.is_file():
        plan = load_json(args.plan)
        grounding = plan.get("grounding") or {}
        if not grounding and plan.get("sections"):
            issues.append("plan_missing_grounding")
        if not plan.get("context_anchor_ref"):
            issues.append("plan_missing_context_anchor_ref")

    if args.context_anchor and args.context_anchor.is_file():
        anchor = load_json(args.context_anchor)
        domain = anchor.get("domain", "")
        if domain and f"domain:" not in note[:1200] and domain not in note[:2000]:
            issues.append("frontmatter_or_body_missing_domain")

    # 附图：写入阶段会自动补嵌，此处仅 warning，避免 lint↔inject 时序死锁
    if args.figures_manifest and args.figures_manifest.is_file():
        fig_man = load_json(args.figures_manifest)
        for fig in fig_man.get("figures") or []:
            if fig.get("decision") != "insert":
                continue
            fname = fig.get("filename") or ""
            rel = fig.get("relative_path") or ""
            if not fname:
                continue
            if fname not in note and (not rel or rel not in note):
                if f"![[images/{fname}" not in note:
                    warnings.append(f"insert_figure_not_referenced:{fname}")

    passed = len(issues) == 0
    result = {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "evidence_scope": scope,
    }

    if args.output:
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    for w in warnings:
        print(f"WARN {w}", file=sys.stderr)
    if not passed:
        for i in issues:
            print(f"FAIL {i}", file=sys.stderr)
        return 1

    print("OK lint passed")
    if warnings:
        print(f"WARNINGS: {len(warnings)}")
    if args.output:
        print(f"LINT_JSON: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
