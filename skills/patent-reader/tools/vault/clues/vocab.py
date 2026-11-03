"""线索词表与阈值：读取 references/clue_vocab.yaml。"""
from __future__ import annotations

import yaml

try:
    from shared.paths import ROOT
except ImportError:
    from tools.patent_reader.shared.paths import ROOT

VOCAB_PATH = ROOT / "references" / "clue_vocab.yaml"

_VOCAB = yaml.safe_load(VOCAB_PATH.read_text(encoding="utf-8")) or {}

DEFAULT_MAX_CLUES: int = int(_VOCAB.get("max_clues", 3))
CONF_RANK: dict[str, int] = {str(k): int(v) for k, v in (_VOCAB.get("confidence_rank") or {}).items()}
REGION_GROUP_LABELS: dict[str, str] = {
    str(k): str(v) for k, v in (_VOCAB.get("region_group_labels") or {}).items()
}
NAV_NOISE: frozenset[str] = frozenset(str(x) for x in _VOCAB.get("nav_noise") or [])
MENU_WORDS: frozenset[str] = frozenset(str(x) for x in _VOCAB.get("menu_words") or [])
MENU_SUFFIXES: tuple[str, ...] = tuple(str(x) for x in _VOCAB.get("menu_suffixes") or [])
TOKEN_STOPWORDS: frozenset[str] = frozenset(str(x) for x in _VOCAB.get("token_stopwords") or [])
FEATURE_LABEL_STOPWORDS: frozenset[str] = frozenset(
    str(x) for x in _VOCAB.get("feature_label_stopwords") or []
)
FEATURE_SYNONYMS: dict[str, tuple[str, ...]] = {
    str(k): tuple(str(x) for x in v) for k, v in (_VOCAB.get("feature_synonyms") or {}).items()
}
