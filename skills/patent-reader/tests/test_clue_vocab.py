# -*- coding: utf-8 -*-
"""线索词表配置：常量正确、兼容入口仍导出原有名字。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "tools"))

from vault import clue_vault
from vault.clues import vocab


class ClueVocabTests(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual(vocab.DEFAULT_MAX_CLUES, 3)
        self.assertEqual(vocab.CONF_RANK["高"], 3)
        self.assertEqual(vocab.REGION_GROUP_LABELS["market"], "本国市场")
        self.assertIn("copyright", vocab.NAV_NOISE)
        self.assertIn("本专利", vocab.TOKEN_STOPWORDS)
        self.assertEqual(vocab.FEATURE_SYNONYMS, {})
        self.assertFalse(hasattr(vocab, "FEATURE_ID_HINTS"))
        self.assertEqual(vocab.MENU_SUFFIXES, ("隔膜",))

    def test_facade_exports(self) -> None:
        for name in (
            "DEFAULT_MAX_CLUES",
            "as_clues",
            "filter_clues",
            "normalize_clue",
            "sanitize_clue_summary",
            "format_summary_for_markdown",
            "harvest_feature_entries",
            "match_clue_to_note",
            "inject_clue_annotations",
            "materialize_clues",
            "render_appendix_b",
            "render_clues_index",
            "upsert_appendix_b",
            "load_clues_sidecar",
            "clue_cards_for_canvas",
        ):
            self.assertTrue(hasattr(clue_vault, name), name)


if __name__ == "__main__":
    unittest.main()
