"""从全文启发式抽取著录：申请人、发明人、申请号、名称、日期、IPC、引证公开号、机构。"""
from __future__ import annotations

import re

from .text_vocab import (
    APPLICATION_NUMBER_LABELS,
    ASSIGNEE_LABELS,
    FILING_DATE_LABELS,
    INVENTOR_LABELS,
    ORG_HINTS,
    PUBLICATION_DATE_LABELS,
    TITLE_LABELS,
    label_pattern,
)


def extract_assignees(text: str) -> list[str]:
    """从专利文本启发式抽取申请人/专利权人。"""
    assignees: list[str] = []
    patterns = [
        rf"(?:{label_pattern(ASSIGNEE_LABELS['zh'])})\s*[:：]\s*([^\n；;]{{2,80}})",
        rf"(?:{label_pattern(ASSIGNEE_LABELS['en'])})\s*[:：]\s*([^\n;]{{2,80}})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            name = m.group(1).strip().strip("；;，,")
            if name and name not in assignees:
                assignees.append(name)
    return assignees[:8]


def extract_ipc_codes(text: str) -> list[str]:
    codes = re.findall(r"\b([A-H]\d{2}[A-Z]\d+/\d+)\b", text, re.I)
    seen: list[str] = []
    for c in codes:
        up = c.upper()
        if up not in seen:
            seen.append(up)
    return seen[:10]


_CN_DATE = re.compile(
    r"(20\d{2}|19\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_ISO_DATE = re.compile(r"(20\d{2}|19\d{2})[-/.](\d{1,2})[-/.](\d{1,2})")
_PUB_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:CN|US|EP|WO|JP|KR)\s*\d{6,13}\s*[A-Z]\d?)(?![A-Za-z0-9])",
    re.I,
)


def _norm_date(year: str, month: str, day: str) -> str:
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return ""


def _date_after_label(text: str, labels: tuple[str, ...]) -> str:
    head = text[:8000]
    for label in labels:
        for m in re.finditer(re.escape(label) + r"\s*[:：]?\s*", head):
            chunk = head[m.end() : m.end() + 40]
            cm = _CN_DATE.search(chunk) or _ISO_DATE.search(chunk)
            if cm:
                got = _norm_date(cm.group(1), cm.group(2), cm.group(3))
                if got:
                    return got
    return ""


def extract_filing_date(text: str) -> str:
    return _date_after_label(text, FILING_DATE_LABELS)


def extract_publication_date(text: str) -> str:
    return _date_after_label(text, PUBLICATION_DATE_LABELS)


def extract_application_number(text: str) -> str:
    m = re.search(
        rf"(?:{label_pattern(APPLICATION_NUMBER_LABELS)})\s*[:：]\s*([A-Z]{{0,2}}\s*\d[\d.]{{6,20}})",
        text[:8000],
        re.I,
    )
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def extract_inventors(text: str) -> list[str]:
    people: list[str] = []
    patterns = [
        rf"(?:{label_pattern(INVENTOR_LABELS['zh'])})\s*[:：]\s*([^\n]{{2,120}})",
        rf"(?:{label_pattern(INVENTOR_LABELS['en'])})\s*[:：]\s*([^\n]{{2,120}})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:8000], re.I)
        if not m:
            continue
        raw = m.group(1)
        parts = re.split(r"[、，,;/；]\s*", raw)
        for p in parts:
            name = p.strip().strip("。．")
            if 1 < len(name) <= 40 and name not in people:
                people.append(name)
    return people[:12]


def extract_invention_title(text: str) -> str:
    m = re.search(
        rf"(?:{label_pattern(TITLE_LABELS)})\s*[:：]\s*([^\n]{{2,120}})",
        text[:4000],
        re.I,
    )
    return m.group(1).strip().strip("。．;；") if m else ""


def extract_cited_pub_numbers(text: str, self_pub: str = "") -> list[str]:
    """说明书/背景里出现的公开号（不含本文）。"""
    self_n = re.sub(r"\s+", "", (self_pub or "")).upper()
    seen: list[str] = []
    for m in _PUB_NUM_RE.finditer(text):
        n = re.sub(r"\s+", "", m.group(1)).upper()
        if n == self_n or n in seen:
            continue
        seen.append(n)
        if len(seen) >= 20:
            break
    return seen


def organizations_from_assignees(assignees: list[str]) -> list[str]:
    orgs: list[str] = []
    for a in assignees or []:
        name = str(a).strip()
        if not name:
            continue
        if any(h.lower() in name.lower() for h in ORG_HINTS):
            if name not in orgs:
                orgs.append(name)
    return orgs
