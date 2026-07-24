#!/usr/bin/env python3
"""
从专利全文（.txt / .md / .pdf）抽取结构化片段，供专利通俗解读使用。

产出（在 -o 目录下）：
  source_manifest.json   章节与覆盖率
  raw_sections.jsonl     每行一节（claim_n / abstract / description）
  claim_tree.json        权利要求父子树
  synthesis_bundle.json  模型阅读入口

PDF 需：pip install pymupdf

用法：
  python tools/patent_reader/extract_patent_text.py -i patent.md -o tmp/patent_reader/run1
  python tools/patent_reader/extract_patent_text.py -i patent.pdf -o tmp/run1 --pub-number CN107785522B
  python tools/patent_reader/extract_patent_text.py -i abstract_only.txt -o tmp/run1 --abstract-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from common import (
        extract_assignees,
        extract_ipc_codes,
        guess_independent,
        normalize_claim_tree,
        parent_claim_number,
        parent_claim_numbers,
        slugify_pub,
    )
except ImportError:
    from tools.patent_reader.common import (
        extract_assignees,
        extract_ipc_codes,
        guess_independent,
        normalize_claim_tree,
        parent_claim_number,
        parent_claim_numbers,
        slugify_pub,
    )

CLAIM_START_RE = re.compile(
    r"^\s*(\d+)\s*[.\．、]\s*(.+)",
    re.DOTALL,
)


def read_input(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # type: ignore
        except ImportError as e:
            raise SystemExit(
                "PDF 需安装 pymupdf：pip install pymupdf"
            ) from e
        doc = fitz.open(path)
        parts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(parts)
    return path.read_text(encoding="utf-8", errors="replace")


def split_claims_block(text: str) -> list[dict]:
    """按「数字.」切分权利要求块。"""
    claims: list[dict] = []
    # 找权利要求书区域
    m = re.search(
        r"(权利要求书|权\s*利\s*要\s*求)(.+)",
        text,
        re.I | re.DOTALL,
    )
    block = m.group(2) if m else text
    # 在说明书开始前截断
    for stop in ("说明书", "技术领域", "【书式", "附图说明"):
        idx = block.find(stop)
        if idx > 50:
            block = block[:idx]
            break

    parts = re.split(r"(?=\n\s*\d+\s*[.\．、])", "\n" + block)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = CLAIM_START_RE.match(part.replace("\n", " ", 1)[:2000])
        if not m and not CLAIM_START_RE.match(part.split("\n", 1)[0]):
            continue
        m2 = re.match(r"^\s*(\d+)\s*[.\．、]\s*", part, re.DOTALL)
        if not m2:
            continue
        num = int(m2.group(1))
        body = part[m2.end() :].strip()
        if len(body) < 4:
            continue
        cands = parent_claim_numbers(body)
        claims.append(
            {
                "number": num,
                "text": body,
                "is_independent": guess_independent(f"{num}. {body}"),
                "parent": cands[0] if cands else parent_claim_number(body),
                "parent_candidates": cands,
            }
        )
    claims.sort(key=lambda c: c["number"])
    return claims


def extract_glossary(text: str) -> list[dict]:
    """从说明书抽「本文中…是指」类定义（要求成对引号）。"""
    glossary: list[dict] = []
    patterns = [
        # 「术语」是指/定义为…
        r"(?:本文中[，,]?)?"
        r"[\u300c\u300e\u201c\"]([^\u300d\u300f\u201d\"\n。]{1,30})"
        r"[\u300d\u300f\u201d\"]"
        r"\s*(?:是指|指|定义为|意为)\s*"
        r"([^。\n]{4,120})",
        # 术语是指…（无引号，短术语）
        r"(?:本文中[，,]?)?"
        r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9]{1,15})"
        r"\s*是指\s*"
        r"([^。\n]{4,120})",
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            term, defn = m.group(1).strip(), m.group(2).strip()
            if "本文中" in term or "。" in term or len(term) < 2:
                continue
            if term.startswith("指"):
                continue
            if term in seen:
                continue
            seen.add(term)
            glossary.append({"term": term, "definition": defn})
    return glossary[:40]


def extract_embodiments(text: str) -> list[dict]:
    """抽取实施例/示例段落。"""
    embodiments: list[dict] = []
    block_m = re.search(
        r"(?:具体实施方式|实施例|DETAILED DESCRIPTION)([\s\S]+?)(?=\n\s*(?:附图说明|权利要求|【|$))",
        text,
        re.I,
    )
    block = block_m.group(1) if block_m else text
    for m in re.finditer(
        r"(实施例\s*\d+|Example\s*\d+)[：:]\s*([^\n]{10,500})",
        block,
        re.I,
    ):
        embodiments.append(
            {
                "label": m.group(1).strip(),
                "text": m.group(2).strip(),
            }
        )
    if not embodiments:
        for i, p in enumerate(
            [x.strip() for x in re.split(r"\n\s*\n", block) if len(x.strip()) > 30][:5],
            1,
        ):
            if re.search(r"实施|例如|优选", p):
                embodiments.append({"label": f"段落{i}", "text": p[:400]})
    return embodiments[:8]


def extract_background_snippets(text: str) -> list[str]:
    """背景技术/技术领域短句。"""
    snippets: list[str] = []
    for label in ("背景技术", "技术领域", "BACKGROUND"):
        m = re.search(rf"{label}\s*([\s\S]{{20,800}}?)(?=\n\s*(?:发明内容|具体实施|附图|权利要求))", text, re.I)
        if m:
            para = m.group(1).strip().split("\n")[0][:300]
            if para:
                snippets.append(para)
    return snippets[:3]


def build_claim_tree(claims: list[dict]) -> dict:
    nodes = []
    for c in claims:
        parent = c.get("parent")
        cands = list(c.get("parent_candidates") or [])
        if c["is_independent"]:
            parent = None
            cands = []
        elif parent is None:
            # 从属但未解析到父号：挂到前一条
            parent = next(
                (p["number"] for p in reversed(claims) if p["number"] < c["number"]),
                None,
            )
        node = {
            "number": c["number"],
            "is_independent": c["is_independent"],
            "parent": parent,
            "text_preview": c["text"][:200],
        }
        if cands:
            node["parent_candidates"] = cands
        nodes.append(node)
    return normalize_claim_tree({"roots": [], "nodes": nodes})


def sections_from_text(
    text: str, pub_number: str, abstract_only: bool
) -> tuple[list[dict], list[dict]]:
    sections: list[dict] = []
    claims = [] if abstract_only else split_claims_block(text)

    abs_m = re.search(
        r"(?:摘\s*要|ABSTRACT)\s*[:：]?\s*([\s\S]{20,2000}?)(?=\n\s*(?:权利要求|说明书|【|$))",
        text,
        re.I,
    )
    abstract = abs_m.group(1).strip() if abs_m else ""
    if abstract:
        sections.append(
            {
                "section_id": "abstract",
                "kind": "abstract",
                "text": abstract,
            }
        )

    for c in claims:
        sections.append(
            {
                "section_id": f"claim_{c['number']}",
                "kind": "claim",
                "number": c["number"],
                "text": c["text"],
                "is_independent": c["is_independent"],
            }
        )

    desc_m = re.search(
        r"(?:说明书|技术领域)([\s\S]+)",
        text,
        re.I,
    )
    desc = desc_m.group(1).strip() if desc_m and not abstract_only else ""
    if desc:
        # 按段落切 desc_001 ...
        paras = [p.strip() for p in re.split(r"\n\s*\n", desc) if len(p.strip()) > 20]
        for i, p in enumerate(paras[:80], 1):
            sections.append(
                {
                    "section_id": f"desc_{i:03d}",
                    "kind": "description",
                    "text": p[:4000],
                }
            )

    return sections, claims


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", required=True, type=Path)
    ap.add_argument("-o", "--output", required=True, type=Path)
    ap.add_argument("--pub-number", default="", help="公开号，如 CN107785522B")
    ap.add_argument(
        "--abstract-only",
        action="store_true",
        help="仅摘要级（无权利要求正文时）",
    )
    args = ap.parse_args(argv)

    in_path = args.input.resolve()
    if not in_path.is_file():
        print(f"错误：找不到 {in_path}", file=sys.stderr)
        return 1

    text = read_input(in_path)
    pub = args.pub_number.strip() or slugify_pub(in_path.stem).upper()
    if re.match(r"^CN\d", pub, re.I):
        pub = pub.upper()

    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sections, claims = sections_from_text(text, pub, args.abstract_only)
    glossary = extract_glossary(text)
    claim_tree = build_claim_tree(claims)
    assignees = extract_assignees(text)
    ipc_codes = extract_ipc_codes(text)
    embodiments = extract_embodiments(text) if not args.abstract_only else []
    background_snippets = extract_background_snippets(text) if not args.abstract_only else []

    try:
        from desc_paragraphs import (
            split_cn_description_paragraphs,
            write_description_paragraphs_json,
        )
    except ImportError:
        from tools.patent_reader.desc_paragraphs import (
            split_cn_description_paragraphs,
            write_description_paragraphs_json,
        )

    description_paragraphs = (
        {} if args.abstract_only else split_cn_description_paragraphs(text)
    )

    has_claims_heading = bool(
        re.search(r"(权利要求书|权\s*利\s*要\s*求|CLAIMS?)", text, re.I)
    )
    if args.abstract_only:
        scope = "abstract_only"
    elif claims:
        scope = "full_text" if sections else "partial"
    elif has_claims_heading:
        scope = "partial"  # 有权项标题但解析失败，勿误标仅摘要
    else:
        scope = "abstract_only"

    manifest = {
        "pub_number": pub,
        "source_path": str(in_path),
        "evidence_scope": scope,
        "claims_parse_failed": bool(has_claims_heading and not claims and not args.abstract_only),
        "section_count": len(sections),
        "claim_count": len(claims),
        "independent_claim_count": sum(1 for c in claims if c["is_independent"]),
        "glossary_count": len(glossary),
        "assignees": assignees,
        "ipc_codes": ipc_codes,
        "embodiment_count": len(embodiments),
        "description_paragraph_count": len(description_paragraphs),
    }

    jsonl_path = out_dir / "raw_sections.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for sec in sections:
            f.write(json.dumps(sec, ensure_ascii=False) + "\n")

    manifest_path = out_dir / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    tree_path = out_dir / "claim_tree.json"
    tree_path.write_text(
        json.dumps(claim_tree, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    bundle = {
        "manifest": manifest,
        "claim_tree": claim_tree,
        "glossary_candidates": glossary,
        "embodiments": embodiments,
        "background_snippets": background_snippets,
        "assignees": assignees,
        "ipc_codes": ipc_codes,
        "claims": [
            {"number": c["number"], "text": c["text"], "is_independent": c["is_independent"]}
            for c in claims
        ],
        "sections_preview": [
            {"section_id": s["section_id"], "kind": s.get("kind"), "len": len(s.get("text", ""))}
            for s in sections
        ],
    }
    bundle_path = out_dir / "synthesis_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    para_path = None
    if description_paragraphs:
        para_path = write_description_paragraphs_json(
            out_dir / "description_paragraphs.json",
            description_paragraphs,
            pub=pub,
        )

    print(f"OK claims={len(claims)} sections={len(sections)} scope={manifest['evidence_scope']}")
    print(f"MANIFEST: {manifest_path}")
    print(f"BUNDLE: {bundle_path}")
    print(f"CLAIM_TREE: {tree_path}")
    print(f"SECTIONS: {jsonl_path}")
    if para_path:
        print(f"DESC_PARAS: {para_path} ({len(description_paragraphs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
