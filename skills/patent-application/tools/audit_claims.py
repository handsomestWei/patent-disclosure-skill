#!/usr/bin/env python
"""中国发明/实用新型权利要求结构检查（编号、引用、过渡语、宣传措辞）。

用法：
  python tools/audit_claims.py 权利要求书.md
  python tools/audit_claims.py 权利要求书.md --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stdio_utf8 import ensure_utf8_stdio
from lexicon import promo_pattern

CLAIM_START = re.compile(r"(?m)^\s*(\d+)\s*[.、．]\s*")
REFERENCE = re.compile(r"权利要求\s*\d+(?:\s*(?:或|、|[-—~～]|至)\s*\d+)*")
_REF_NUM = re.compile(r"\d+")
_REF_RANGE = re.compile(r"[-—~～]|至")
TERM_INTRO = re.compile(r"(?:所述|该)([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_-]{1,20})")
PLACEHOLDER = re.compile(r"\[(?:TO CONFIRM|待确认)[^\]]*\]", re.IGNORECASE)
INDEPENDENT_OPEN = re.compile(r"^一种.{0,60}(方法|系统|装置|设备)")
PROMO = promo_pattern()


@dataclass
class Finding:
    level: str
    claim: Optional[int]
    code: str
    message: str


def split_claims(text: str) -> list[tuple[int, str]]:
    matches = list(CLAIM_START.finditer(text))
    claims: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        claims.append((int(match.group(1)), text[match.end() : end].strip()))
    return claims


def references(body: str) -> list[int]:
    """引用权号：「权利要求1」「权利要求1或2」「权利要求1、2或3」「权利要求1-3」均展开。"""
    result: list[int] = []
    for match in REFERENCE.finditer(body):
        phrase = match.group(0)
        nums = _REF_NUM.findall(phrase)
        if not nums:
            continue
        start = int(nums[0])
        if len(nums) == 1:
            result.append(start)
        elif _REF_RANGE.search(phrase):
            result.extend(range(start, int(nums[-1]) + 1))
        else:
            result.extend(int(n) for n in nums)
    return sorted(set(result))


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_further_independent(compact: str) -> bool:
    """第二条及以后的独立权项（一种…方法/系统/装置/设备），不是漏写引用的从属。"""
    if compact.startswith("根据权利要求") or "根据权利要求" in compact[:20]:
        return False
    return bool(INDEPENDENT_OPEN.match(compact))


def audit(text: str) -> list[Finding]:
    claims = split_claims(text)
    findings: list[Finding] = []
    if not claims:
        return [Finding("ERROR", None, "NO_CLAIMS", "未识别到以“1.”形式起始的权利要求。")]

    numbers = [number for number, _ in claims]
    expected = list(range(1, len(claims) + 1))
    if numbers != expected:
        findings.append(
            Finding("ERROR", None, "NUMBER_SEQUENCE", f"编号应连续为{expected}，实际为{numbers}。")
        )

    previous_text = ""
    claim_map: dict[int, str] = {}
    for number, body in claims:
        compact = normalize(body)
        claim_map[number] = compact
        refs = references(body)

        if not body:
            findings.append(Finding("ERROR", number, "EMPTY", "权利要求正文为空。"))
            continue
        if PLACEHOLDER.search(body):
            findings.append(
                Finding("ERROR", number, "PLACEHOLDER", "正式权利要求中仍含待确认标记。")
            )
        if number == 1 and refs:
            findings.append(
                Finding("ERROR", number, "INDEPENDENT_REFERENCE", "权利要求1不应引用其他权利要求。")
            )
        if number > 1 and not refs and not is_further_independent(compact):
            findings.append(
                Finding("WARNING", number, "NO_REFERENCE", "未检测到从属引用；确认其是否为独立权利要求。")
            )
        for ref in refs:
            if ref >= number:
                findings.append(
                    Finding("ERROR", number, "FORWARD_REFERENCE", f"引用了非在先权利要求{ref}。")
                )
            if ref not in claim_map:
                findings.append(
                    Finding("ERROR", number, "MISSING_REFERENCE", f"引用的权利要求{ref}不存在。")
                )

        if "其特征在于" not in compact:
            findings.append(
                Finding("WARNING", number, "TRANSITION", "未检测到“其特征在于”过渡语。")
            )
        if len(compact) < 25:
            findings.append(
                Finding("WARNING", number, "TOO_SHORT", "权利要求较短，确认是否完整限定技术方案。")
            )
        if PROMO.search(compact):
            findings.append(
                Finding("WARNING", number, "RESULT_LANGUAGE", "含结果或宣传性措辞，确认是否改为技术限定。")
            )

        searchable_basis = previous_text + "".join(claim_map.get(ref, "") for ref in refs)
        skip_terms = {"方法", "装置", "设备", "系统", "步骤", "程序", "权利要求"}
        for match in re.finditer(
            r"所述(?!的方法|的装置|的系统|的设备|权利要求)([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_-]{1,20})",
            body,
        ):
            captured = match.group(1)
            before = normalize(body[: match.start()])
            introduced = False
            for length in range(len(captured), 1, -1):
                term = captured[:length]
                if term in skip_terms:
                    continue
                if term in searchable_basis or term in before:
                    introduced = True
                    break
            if not introduced:
                findings.append(
                    Finding(
                        "WARNING",
                        number,
                        "SAID_ANTECEDENT",
                        f"「所述{captured}」在本项及在先权项中未见首次出现。",
                    )
                )
        for term in sorted(set(TERM_INTRO.findall(body))):
            if term in skip_terms:
                continue
            if term not in searchable_basis and compact.find(term) <= 4:
                findings.append(
                    Finding(
                        "WARNING",
                        number,
                        "ANTECEDENT_BASIS",
                        f"术语“{term}”可能缺少清晰的前置基础。",
                    )
                )
        previous_text += compact

    return findings


def summarize(findings: list[Finding]) -> tuple[int, int]:
    errors = sum(item.level == "ERROR" for item in findings)
    warnings = sum(item.level == "WARNING" for item in findings)
    return errors, warnings


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path, help="UTF-8 权利要求书")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    path = args.claims.expanduser().resolve()
    if not path.is_file():
        print("APPLICATION_CLAIMS: ok=0 errors=1 warnings=0")
        print(f"文件不存在：{path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    findings = audit(text)
    errors, warnings = summarize(findings)
    ok = errors == 0
    print(f"APPLICATION_CLAIMS: ok={1 if ok else 0} errors={errors} warnings={warnings}")
    if args.json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
    elif not findings:
        print("PASS: 未发现结构性问题。机器通过不等于可提交。")
    else:
        for item in findings:
            location = f"权利要求{item.claim}" if item.claim else "整体"
            print(f"{item.level}\t{location}\t{item.code}\t{item.message}")
        print(f"汇总: {errors} 个错误, {warnings} 个警告。机器通过不等于可提交。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
