"""全文抽取词表：读取 references/text_vocab.yaml。"""
from __future__ import annotations

import re

import yaml

from .paths import ROOT

VOCAB_PATH = ROOT / "references" / "text_vocab.yaml"

_VOCAB = yaml.safe_load(VOCAB_PATH.read_text(encoding="utf-8")) or {}


def _strs(key: str) -> tuple[str, ...]:
    return tuple(str(x) for x in _VOCAB.get(key) or [])


def _lang_labels(key: str) -> dict[str, tuple[str, ...]]:
    groups = _VOCAB.get(key) or {}
    return {lang: tuple(str(x) for x in groups.get(lang) or []) for lang in ("zh", "en")}


def label_pattern(labels: tuple[str, ...]) -> str:
    """标签 → 正则分支；标签里的空格匹配任意空白。"""
    return "|".join(re.escape(label).replace(r"\ ", r"\s*") for label in labels)


DEP_PATTERNS: tuple[str, ...] = _strs("dependent_claim_patterns")
INDEPENDENT_CLAIM_STARTS: tuple[str, ...] = _strs("independent_claim_starts")
ASSIGNEE_LABELS: dict[str, tuple[str, ...]] = _lang_labels("assignee_labels")
INVENTOR_LABELS: dict[str, tuple[str, ...]] = _lang_labels("inventor_labels")
APPLICATION_NUMBER_LABELS: tuple[str, ...] = _strs("application_number_labels")
TITLE_LABELS: tuple[str, ...] = _strs("title_labels")
FILING_DATE_LABELS: tuple[str, ...] = _strs("filing_date_labels")
PUBLICATION_DATE_LABELS: tuple[str, ...] = _strs("publication_date_labels")
ORG_HINTS: tuple[str, ...] = _strs("org_hints")
