"""公开检索线索（兼容入口）：实现按职责拆在 vault/clues/ 下，词表在 references/clue_vocab.yaml。"""
from __future__ import annotations

from .clues.vocab import CONF_RANK, DEFAULT_MAX_CLUES  # noqa: F401
from .clues.model import (  # noqa: F401
    _clue_link,
    _clue_stem,
    _conf_rank,
    _region_text,
    _table_wikilink,
    agent_fits_for,
    as_clues,
    clue_filename,
    filter_clues,
    load_clues_sidecar,
    normalize_anchor_fits,
    normalize_clue,
)
from .clues.summary import (  # noqa: F401
    _is_formula_glyph_frag,
    _join_broken_glyph_lines,
    _strip_html,
    fetch_url_summary,
    format_summary_for_markdown,
    sanitize_clue_summary,
)
from .clues.matching import (  # noqa: F401
    SECTION4_RE,
    SECTION6_RE,
    _claim_key_to_num,
    _clue_highlight,
    _clue_snippet_pool,
    _distinct_clue_lines,
    _feature_anchor_tokens,
    _label_hits_blob,
    _score_snippet_for_feature,
    _term_match_tokens,
    _tokenize,
    clue_highlight_for_feature,
    clue_highlight_for_text,
    feature_clue_affinity,
    feature_display_name,
    harvest_claim_bodies,
    harvest_feature_entries,
    harvest_feature_rows,
    match_clue_to_note,
    resolve_feature_entry,
)
from .clues.annotate import (  # noqa: F401
    _insert_after_section,
    _insert_after_section6_feature_table,
    _insert_before_heading,
    _render_warning,
    _strip_injected_clue_blocks,
    inject_clue_annotations,
    render_annotation_callout,
)
from .clues.render import (  # noqa: F401
    APPENDIX_B_RE,
    clue_cards_for_canvas,
    materialize_clues,
    render_appendix_b,
    render_clue_note,
    render_clues_index,
    upsert_appendix_b,
)
