# -*- coding: utf-8 -*-
"""说明书段落锚点与引用改写。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "patent_reader"))

from desc_paragraphs import (  # noqa: E402
    format_citation_wikilinks,
    materialize_description_paragraphs,
    parse_cited_paragraph_numbers,
    split_cn_description_paragraphs,
    upgrade_legacy_citation_wikilinks,
    wikilink_description_citations,
)


class DescParagraphsTest(unittest.TestCase):
    def test_split_paragraphs(self) -> None:
        text = (
            "背景技术\n[0002]\n第一段内容。\n[0003]\n第二段内容。\n"
            "说明书 1/9 页\nCN 119961396 A\n[0004]\n第三段。"
        )
        paras = split_cn_description_paragraphs(text)
        self.assertIn("0002", paras)
        self.assertIn("第一段", paras["0002"])
        self.assertIn("第二段", paras["0003"])
        self.assertNotIn("说明书 1/9", paras["0003"])

    def test_parse_citations(self) -> None:
        note = "难普及（[0002]–[0004]）。另见说明书 0056 与 [0128]–[0131]。"
        cited = parse_cited_paragraph_numbers(note)
        self.assertEqual(
            cited,
            ["0002", "0003", "0004", "0056", "0128", "0129", "0130", "0131"],
        )

    def test_wikilink_rewrite_range_single_link(self) -> None:
        pub = "CN119961396A"
        src = "问题（[0002]–[0004]）。单段说明书 0056。"
        out = wikilink_description_citations(src, pub=pub)
        self.assertIn(
            "[[CN119961396A_说明书段落#^r0002-0004|说明书 0002–0004]]", out
        )
        self.assertIn(
            "[[CN119961396A_说明书段落#^p0056|说明书 0056]]", out
        )
        self.assertNotIn("[0002]", out)
        self.assertNotIn("]]–[[", out)
        out2 = wikilink_description_citations(out, pub=pub)
        self.assertEqual(
            out.count("#^r0002-0004"), out2.count("#^r0002-0004")
        )

    def test_upgrade_legacy_split_links(self) -> None:
        pub = "CN1"
        old = (
            "（[[CN1_说明书段落#0002|说明书 0002]]–"
            "[[CN1_说明书段落#0004|0004]]）。"
        )
        new = upgrade_legacy_citation_wikilinks(old, pub=pub)
        self.assertEqual(
            new,
            "（[[CN1_说明书段落#^r0002-0004|说明书 0002–0004]]）。",
        )

    def test_format_single(self) -> None:
        self.assertEqual(
            format_citation_wikilinks("CN1", "0007"),
            "[[CN1_说明书段落#^p0007|说明书 0007]]",
        )

    def test_materialize_cited_only(self) -> None:
        paras = {
            "0002": "法规更新。",
            "0003": "人力不足。",
            "0004": "成本高。",
            "0099": "未引用。",
        }
        content = (
            "## Obsidian 导航\n\n"
            "- [[Research/Patents/_专利解读索引|专利解读索引]]\n"
            "- [[x/CN1_图谱.canvas|专利族图谱]]\n\n"
            "## 二、连贯叙事\n\n"
            "难普及（说明书 0002–0004）。\n"
        )
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            new_content, path, cited = materialize_description_paragraphs(
                content=content,
                pub="CN1",
                note_dir=base,
                paragraphs=paras,
                cited_only=True,
            )
            self.assertIsNotNone(path)
            assert path is not None
            body = path.read_text(encoding="utf-8")
            self.assertIn("### 0002", body)
            self.assertIn("^p0002", body)
            self.assertIn("### 0002–0004", body)
            self.assertIn("^r0002-0004", body)
            self.assertNotIn("### 0099", body)
            self.assertEqual(cited, ["0002", "0003", "0004"])
            self.assertIn(
                "[[CN1_说明书段落#^r0002-0004|说明书 0002–0004]]",
                new_content,
            )


if __name__ == "__main__":
    raise SystemExit(unittest.main())
