# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "patent_reader"))

from note_cites import (  # noqa: E402
    enhance_note_citations,
    escape_wikilink_pipes_in_tables,
    format_claim_wikilinks,
    wikilink_claim_citations,
    wikilink_figure_citations,
)


class NoteCitesTest(unittest.TestCase):
    def test_claim_range(self) -> None:
        self.assertEqual(
            format_claim_wikilinks(2, 3, pub="CN1"),
            "[[CN1_权项锚点#^claim-2|权2]]–[[CN1_权项锚点#^claim-3|权3]]",
        )

    def test_rewrite_body(self) -> None:
        src = "### 图1\n\n### 图3\n\n外部知识（权2–3；见图1–3）。"
        out = wikilink_claim_citations(src, pub="CN1")
        out = wikilink_figure_citations(out)
        self.assertIn("[[CN1_权项锚点#^claim-2|权2]]", out)
        self.assertIn("[[CN1_权项锚点#^claim-3|权3]]", out)
        self.assertIn("[[#图1|图1]]", out)
        self.assertIn("[[#图3|图3]]", out)

    def test_enhance_sidecar(self) -> None:
        content = (
            "## Obsidian 导航\n\n"
            "- [[x/CN1_图谱.canvas|专利族图谱]]\n"
            "- [[CN1_说明书段落|说明书段落]]\n\n"
            "## 三、权利要求树\n\n"
            "| 结构 | 权 | 本项新增 |\n"
            "| --- | ---: | --- |\n"
            "| `◆` | 1 | 骨架 |\n"
            "| `└─` | 2 | 建库 |\n\n"
            "## 四、独立权利要求精读\n\n"
            "见（权2–3）。\n"
        )
        tree = {
            "nodes": [
                {"number": 1, "is_independent": True, "delta": "骨架"},
                {"number": 2, "is_independent": False, "delta": "建库"},
                {"number": 3, "is_independent": False, "delta": "训模"},
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out, path, nums = enhance_note_citations(
                content,
                pub="CN1",
                note_dir=base,
                claim_tree=tree,
                claim_summaries={2: "建库", 3: "训模"},
            )
            self.assertIsNotNone(path)
            assert path is not None
            body = path.read_text(encoding="utf-8")
            self.assertIn("^claim-2", body)
            self.assertIn("使用说明", body)
            self.assertIn("[[CN1_权项锚点#^claim-2|权2]]", out)
            self.assertIn("[[CN1_权项锚点|权项锚点]]", out)
            self.assertNotIn("### 权项锚点", out)
            self.assertNotRegex(out, r"^>\s*\^claim-", re.M)
            self.assertEqual(nums, [1, 2, 3])

    def test_escape_pipes_in_table(self) -> None:
        src = (
            "| 特征 | 依据 |\n"
            "| --- | --- |\n"
            "| x | [[CN1_说明书段落#^r0057-0061|说明书 0057–0061]]；"
            "[[CN1_权项锚点#^claim-2|权2]] |\n"
        )
        out = escape_wikilink_pipes_in_tables(src)
        self.assertIn(r"[[CN1_说明书段落#^r0057-0061\|说明书 0057–0061]]", out)
        self.assertIn(r"[[CN1_权项锚点#^claim-2\|权2]]", out)
        self.assertIn("| x |", out)


class CluesIndexTableTest(unittest.TestCase):
    def test_render_clues_index_table_wikilinks(self) -> None:
        from clue_vault import render_clues_index  # noqa: E402

        body = render_clues_index(
            [
                {
                    "title": "甲/乙：测试标题很长很长很长很长很长很长很长",
                    "filename": "01-test.md",
                    "confidence": "高",
                    "status": "agent_fetched",
                    "related_claims": [1, 2],
                }
            ],
            pub="CN1",
        )
        self.assertIn(r"[[01-test\|", body)
        self.assertIn(r"[[CN1_权项锚点#^claim-1\|权1]]", body)
        self.assertIn(r"[[CN1_权项锚点#^claim-2\|权2]]", body)
        # 表行内 wikilink 不得出现未转义的别名 |
        for line in body.splitlines():
            if "| [[" in line:
                self.assertNotRegex(line, r"\[\[[^\]]*(?<!\\)\|[^\]]*\]\]")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
