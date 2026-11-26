# -*- coding: utf-8 -*-
"""从本地文件判断文书角色和专利类型，并决定默认蒸哪些档。"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from distill_validate import evidence_from_inputs, expected_strength

_PUB_RE = re.compile(r"(?i)(?:CN|ZL)\s*(\d{7,12})\s*([ABCUYS])\d?")
_KIND = {"A": "invention", "B": "invention", "C": "invention", "U": "utility_model", "Y": "utility_model", "S": "design"}
_APPLICATION_PIECES = {"权利要求书", "说明书", "说明书摘要", "说明书附图"}
_SPEC_HEADINGS = ("技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式", "说明书摘要")


def read_preview(path: Path, limit: int = 24000) -> str:
    return normalize_patent_text(_raw_text(path, max_pages=8))[:limit]


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (OSError, zipfile.BadZipFile, KeyError):
        return ""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ""
    parts = [node.text or "" for node in root.iter() if node.text]
    return "\n".join(parts)


def _pdf_text(path: Path, *, max_pages: int | None = 8) -> str:
    try:
        head = path.read_bytes()[:5]
    except OSError:
        return ""
    if not head.startswith(b"%PDF"):
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return ""
    try:
        reader = PdfReader(str(path))
        pages = reader.pages if max_pages is None else reader.pages[:max_pages]
        return "\n".join((page.extract_text() or "") for page in pages)
    except Exception:
        return ""


def normalize_patent_text(text: str) -> str:
    """去掉汉字间空格、页眉页码，并把跨页切开的句子接回去。"""
    cleaned = text.replace("\u00a0", " ").replace("\u3000", " ")
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r"CN\s*(\d{6,12})\s*([A-Za-z])", r"CN\1\2", cleaned, flags=re.I)
    cleaned = re.sub(r"(?<=[，。；：、！？])\s+(?=[\u4e00-\u9fffA-Za-z0-9])", "", cleaned)
    header = re.compile(r"(权利要求书|说明书)\s*\d+\s*/\s*\d+\s*页")
    pub_only = re.compile(r"^CN\d{6,12}[A-Z]$", re.I)
    new_block = re.compile(r"^(\d+\.|\[\d+\]|技术领域|背景技术|发明内容|附图说明|具体实施方式|摘要)")
    sentence_end = ("。", "；", "！", "？", "：")
    lines: list[str] = []
    for line in cleaned.splitlines():
        line = header.sub("", line).strip()
        if not line or re.fullmatch(r"\d+", line) or pub_only.match(line):
            continue
        lines.append(line)
    if not lines:
        return ""
    merged = [lines[0]]
    for line in lines[1:]:
        prev = merged[-1]
        if new_block.match(line) or prev.endswith(sentence_end):
            merged.append(line)
        else:
            merged[-1] = prev + line
    return "\n".join(merged)


def _raw_text(path: Path, *, max_pages: int | None) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        return _docx_text(path)
    if suffix == ".pdf":
        return _pdf_text(path, max_pages=max_pages)
    return path.read_text(encoding="utf-8", errors="replace")


def read_full_text(path: Path, limit: int = 400000) -> str:
    return normalize_patent_text(_raw_text(path, max_pages=None))[:limit]


def _kind_letter(text: str, name: str) -> str:
    grant = re.search(r"授权公告号\s*(CN\d{6,12}[A-Za-z])", text, re.I)
    if grant:
        return grant.group(1)[-1].upper()
    laid = re.search(r"申请公布号\s*(CN\d{6,12}[A-Za-z])", text, re.I)
    if laid:
        return laid.group(1)[-1].upper()
    named = _PUB_RE.search(name)
    if named:
        return named.group(2).upper()
    return ""


def _listed_pubs(text: str, name: str) -> dict[str, str]:
    grant = re.search(r"授权公告号\s*(CN\d{6,12}[A-Za-z])", text, re.I)
    laid = re.search(r"申请公布号\s*(CN\d{6,12}[A-Za-z])", text, re.I)
    named = _PUB_RE.search(name)
    pubs = {
        "grant_pub": grant.group(1).upper() if grant else "",
        "laid_open_pub": laid.group(1).upper() if laid else "",
    }
    if named and not pubs["grant_pub"] and named.group(2).upper() in {"B", "C", "U", "S"}:
        pubs["grant_pub"] = f"CN{named.group(1)}{named.group(2).upper()}"
    if named and not pubs["laid_open_pub"] and named.group(2).upper() == "A":
        pubs["laid_open_pub"] = f"CN{named.group(1)}{named.group(2).upper()}"
    return pubs


def _patent_type_of(text: str, name: str) -> tuple[str, str]:
    letter = _kind_letter(text, name)
    from_letter = _KIND.get(letter, "")
    from_words = ""
    if re.search(r"外观设计|外观专利", text):
        from_words = "design"
    elif re.search(r"实用新型", text):
        from_words = "utility_model"
    elif re.search(r"发明公布|发明授权|发明专利|发明交底|本发明", text):
        from_words = "invention"
    if from_letter and from_words and from_letter != from_words:
        return "", f"公开号种类码是{letter}，正文却写成另一类型"
    if from_letter:
        return from_letter, f"公开号种类码 {letter}"
    if from_words:
        return from_words, "正文类型词"
    return "", "未见专利类型"


def _scores(text: str, name: str = "") -> dict[str, int]:
    disclosure = 0
    application = 0
    publication = 0
    if re.search(r"技术交底书", text):
        disclosure += 3
    elif re.search(r"交底书", text):
        disclosure += 2
    if re.search(r"欲保护点|技术关键点", text):
        disclosure += 2
    if re.search(r"现有技术存在的缺点|本发明技术方案", text):
        disclosure += 2
    if re.search(r"(?m)^#{0,3}\s*权利要求书\s*$|^\s*权利要求书\s*$", text):
        application += 4
    elif "权利要求书" in text:
        application += 1
    if re.search(r"其特征在于", text):
        application += 2
    for heading in _SPEC_HEADINGS:
        if heading in text:
            application += 1
    stem = Path(name).stem if name else ""
    if stem in _APPLICATION_PIECES:
        application += 3
    if re.search(r"国家知识产权局", text):
        publication += 2
    if re.search(r"申请公布号|授权公告号|公开（公告）号|公开\(公告\)号", text):
        publication += 3
    if _PUB_RE.search(text):
        publication += 2
    return {"disclosure": disclosure, "application": application, "publication": publication}


def classify_file(path: Path) -> dict[str, str]:
    text = read_preview(path)
    name = path.name
    scores = _scores(text, name)
    if _PUB_RE.search(name) and scores["publication"] < 3:
        scores["publication"] += 3
    patent_type, type_reason = _patent_type_of(text + "\n" + name, name)
    role = ""
    reason = ""
    published = bool(re.search(r"申请公布号|授权公告号|公开（公告）号|公开\(公告\)号|国家知识产权局", text))
    if scores["publication"] >= 3 and scores["publication"] >= scores["disclosure"] and (
        scores["publication"] > scores["application"] or (published and scores["publication"] >= scores["application"])
    ):
        letter = _kind_letter(text, name)
        if letter in {"B", "C"}:
            role = "publication_b"
        elif letter == "A":
            role = "publication_a"
        elif re.search(r"授权公告号", text):
            role = "publication_b"
        elif re.search(r"申请公布号|发明公布", text):
            role = "publication_a"
        else:
            role = "publication"
        reason = "公开单行本著录"
    elif scores["disclosure"] >= 3 and scores["disclosure"] > scores["application"]:
        role = "disclosure"
        reason = "交底书结构"
    elif scores["application"] >= 3 and scores["application"] >= scores["disclosure"]:
        role = "application"
        reason = "权利要求或说明书结构"
    else:
        reason = "正文不足以判断文书"
    if not text.strip() and not role:
        reason = "读不到正文，且文件名也不足以判断"
    pubs = _listed_pubs(text, name)
    return {
        "path": path.as_posix(),
        "role": role,
        "patent_type": patent_type,
        "reason": reason if role else reason,
        "type_reason": type_reason,
        "grant_pub": pubs["grant_pub"],
        "laid_open_pub": pubs["laid_open_pub"],
    }


def _case_id(stem: str, used: set[str]) -> str:
    text = re.sub(r'[\\/:*?"<>|\s]+', "-", stem).strip(".-") or "case"
    base = text[:80]
    candidate = base
    number = 2
    while candidate in used:
        suffix = f"-{number}"
        candidate = f"{base[: 80 - len(suffix)]}{suffix}"
        number += 1
    used.add(candidate)
    return candidate


def _pub_digits(path: str) -> str:
    match = _PUB_RE.search(path)
    return match.group(1) if match else ""


def _shell(
    *,
    profile_id: str,
    patent_type: str,
    ownership: str,
    tracks: list[str],
    inputs: list[dict[str, str]],
    detected: list[dict[str, str]],
) -> dict[str, Any]:
    evidence = evidence_from_inputs(inputs)
    evidence["has_family"] = False
    grants = [str(item.get("grant_pub") or "") for item in detected if item.get("grant_pub")]
    laids = [str(item.get("laid_open_pub") or "") for item in detected if item.get("laid_open_pub")]
    evidence["grant_pub"] = grants[0] if grants else ""
    evidence["laid_open_pub"] = laids[0] if laids else ""
    roles = {str(item.get("role") or "") for item in inputs}
    evidence["pair_in_batch"] = "publication_a" in roles and "publication_b" in roles
    style_on = tracks == ["style"]
    strategy_on = tracks == ["strategy"]
    profile: dict[str, Any] = {
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
        "inputs": inputs,
        "evidence": evidence,
        "style": {
            "enabled": style_on,
            "kinds": ["application"] if style_on else [],
            "status": "draft",
        },
        "strategy": {"enabled": strategy_on, "strength": "none", "status": "draft"},
        "detected": detected,
    }
    if strategy_on:
        profile["strategy"]["strength"] = expected_strength(profile)
    profile["strategy"]["callable"] = bool(strategy_on and profile["strategy"]["strength"] != "observe")
    return profile


def _application_groups(applications: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    buckets: dict[str, list[dict[str, str]]] = {}
    groups: list[list[dict[str, str]]] = []
    for application in applications:
        stem = Path(application["path"]).stem
        parent = str(Path(application["path"]).parent)
        if stem in _APPLICATION_PIECES:
            buckets.setdefault(parent or stem, []).append(application)
        else:
            groups.append([application])
    groups.extend(buckets.values())
    return groups


def _group_case_id(group: list[dict[str, str]], used: set[str]) -> str:
    first = Path(group[0]["path"])
    if len(group) > 1 or first.stem in _APPLICATION_PIECES:
        parent_name = first.parent.name.strip()
        if parent_name and parent_name not in {".", ""}:
            return _case_id(parent_name, used)
    return _case_id(first.stem, used)


def _attach_disclosure(
    group: list[dict[str, str]],
    disclosures: list[dict[str, str]],
    used_disclosures: set[str],
    *,
    sole_pair: bool,
) -> list[dict[str, str]]:
    match = None
    for application in group:
        app_stem = Path(application["path"]).stem
        match = next(
            (
                item
                for item in disclosures
                if item["path"] not in used_disclosures
                and (
                    Path(item["path"]).stem == app_stem
                    or app_stem in Path(item["path"]).stem
                    or Path(item["path"]).stem in app_stem
                )
            ),
            None,
        )
        if match is not None:
            break
    if match is None and sole_pair and disclosures and disclosures[0]["path"] not in used_disclosures:
        match = disclosures[0]
    if match is None:
        return []
    used_disclosures.add(match["path"])
    return [match]


def group_cases(files: list[dict[str, str]]) -> list[dict[str, Any]]:
    applications = [item for item in files if item.get("role") == "application"]
    disclosures = [item for item in files if item.get("role") == "disclosure"]
    publications = [item for item in files if str(item.get("role") or "").startswith("publication")]
    used_disclosures: set[str] = set()
    used_ids: set[str] = set()
    cases: list[dict[str, Any]] = []
    app_groups = _application_groups(applications)
    sole_pair = len(app_groups) == 1 and len(disclosures) == 1
    for group in app_groups:
        attached = _attach_disclosure(group, disclosures, used_disclosures, sole_pair=sole_pair)
        cases.append(
            {
                "case_id": _group_case_id(group, used_ids),
                "files": [*group, *attached],
                "kind": "application",
            }
        )
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in publications:
        key = _pub_digits(item["path"]) or Path(item["path"]).stem
        grouped.setdefault(key, []).append(item)
    for key, group in grouped.items():
        cases.append({"case_id": _case_id(key, used_ids), "files": group, "kind": "publication"})
    return cases


def plan_batch(
    files: list[dict[str, str]],
    *,
    batch_id: str,
    ownership: str,
) -> dict[str, Any]:
    asks: list[str] = []
    usable = [item for item in files if item.get("role")]
    if len(usable) != len(files):
        missing = [item["path"] for item in files if not item.get("role")]
        asks.append("role " + "、".join(missing))
    types = {item["patent_type"] for item in usable if item.get("patent_type")}
    if len(types) == 1:
        agreed = next(iter(types))
        for item in usable:
            if not item.get("patent_type"):
                item["patent_type"] = agreed
                item["type_reason"] = "同批其他文件"
        types = {agreed}
    if len(types) > 1:
        asks.append("patent_type 材料分属不同类型，请拆开")
    if usable and not types:
        asks.append("patent_type " + "、".join(item["path"] for item in usable))
    patent_type = next(iter(types)) if len(types) == 1 else ""
    publications = [item for item in usable if str(item.get("role") or "").startswith("publication")]
    applications = [item for item in usable if item.get("role") == "application"]
    pub_ownership = ownership if ownership in {"own", "third_party"} else "third_party"
    if asks or not patent_type:
        return {"asks": asks, "patent_type": patent_type, "style": None, "cases": []}
    cases_in = group_cases(usable)
    case_profiles = []
    for case in cases_in:
        case_ownership = "own" if case["kind"] == "application" else pub_ownership
        case_profiles.append(
            _shell(
                profile_id=case["case_id"],
                patent_type=patent_type,
                ownership=case_ownership,
                tracks=["strategy"],
                inputs=[{"role": item["role"], "path": item["path"]} for item in case["files"]],
                detected=case["files"],
            )
        )
    style = None
    if applications:
        style = _shell(
            profile_id=batch_id,
            patent_type=patent_type,
            ownership="own",
            tracks=["style"],
            inputs=[{"role": "application", "path": item["path"]} for item in applications],
            detected=applications,
        )
    if style is None and not case_profiles:
        asks.append("文风收录申请文件；思路按案件收录申请文件或公开文本")
    return {"asks": asks, "patent_type": patent_type, "style": style, "cases": case_profiles}
