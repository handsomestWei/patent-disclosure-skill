# -*- coding: utf-8 -*-
"""全文抽取词表（references/text_vocab.yaml）生效：独立 / 从属判断、字段标签、机构提示词。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "tools"))

from shared import text_vocab
from shared.biblio import extract_application_number, extract_inventors, organizations_from_assignees
from shared.claims import guess_independent


class TextVocabTests(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertIn("according to claim", text_vocab.DEP_PATTERNS)
        self.assertEqual(text_vocab.INDEPENDENT_CLAIM_STARTS, ("一种", "一種", "a ", "an "))
        self.assertEqual(text_vocab.ASSIGNEE_LABELS["en"], ("Applicant", "Assignee"))
        self.assertIn("GmbH", text_vocab.ORG_HINTS)

    def test_label_driven_extraction(self) -> None:
        self.assertTrue(guess_independent("1. An apparatus comprising a frame."))
        self.assertFalse(guess_independent("2. The apparatus of claim 1, wherein x."))
        self.assertEqual(extract_application_number("Application   Number: US 2019123456"), "US2019123456")
        self.assertEqual(extract_inventors("Inventors: Ann Lee, Bo Wu"), ["Ann Lee", "Bo Wu"])
        self.assertEqual(organizations_from_assignees(["Robert Bosch GmbH", "张三"]), ["Robert Bosch GmbH"])


if __name__ == "__main__":
    unittest.main()
