# -*- coding: utf-8 -*-
"""海外文献线索：线索包只给事实、线索按市场分组筛选与显示、领域按分类号判定（不联网）。"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "tools"))

import analyze.build_context_anchor as anchor_mod
from extract.fetch_gp_fulltext import write_outputs
from google_patents import parse_detail_html
from shared.common import load_domain_rules, resolve_domain
from vault.clue_vault import filter_clues, render_appendix_b

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "google_patents"


def _anchor_for(fixture: str, pub: str) -> dict:
    detail = parse_detail_html((FIXTURES / fixture).read_text(encoding="utf-8"), pub=pub)
    with tempfile.TemporaryDirectory() as td:
        run = Path(td)
        write_outputs(detail, run)
        with redirect_stdout(io.StringIO()):
            assert anchor_mod.main(["-w", str(run)]) == 0
        return json.loads((run / "context_anchor.json").read_text(encoding="utf-8"))


class OverseasAnchorTests(unittest.TestCase):
    def test_jp_gets_facts_not_queries(self) -> None:
        a = _anchor_for("detail_JP7371268B2.html", "JP7371268B2")
        self.assertEqual(a["jurisdiction"], "JP")
        self.assertEqual(a["web_search_queries"], [])
        plan = a["search_plan"]
        self.assertEqual(plan["status"], "agent_todo")
        self.assertEqual(plan["queries"], [])
        facts = plan["facts"]
        self.assertEqual(facts["jurisdiction"], "JP")
        self.assertEqual(facts["translated_from"], "Japanese")
        self.assertTrue(facts["claim_1"].startswith("A lithium ion secondary battery"))
        self.assertIn("リチウムイオン二次電池", facts["claim_1_original"])
        self.assertTrue(facts["assignees"])
        self.assertEqual(a["domain"], "化工与材料")

    def test_us_has_no_original_text(self) -> None:
        facts = _anchor_for("detail_US11450918B2.html", "US11450918B2")["search_plan"]["facts"]
        self.assertEqual(facts["jurisdiction"], "US")
        self.assertEqual(facts["claim_1_original"], "")
        self.assertEqual(facts["title"], "Battery module gas sensor for battery cell monitoring")

    def test_cn_keeps_chinese_templates_without_plan(self) -> None:
        qs = anchor_mod.build_web_search_queries(
            "CN1", ["某某电池有限公司"], "", {"industry": "电化学储能", "search_hints": ["技术白皮书"]}, ["陶瓷涂层"]
        )
        self.assertIn("(产品 OR 解决方案 OR 发布会)", qs[0]["query"])
        self.assertEqual(qs[-1]["tool"], "cnipa_epub_crawler.py")
        self.assertNotIn("group", qs[0])


class ClueRegionTests(unittest.TestCase):
    def _clue(self, title: str, conf: str, group: str = "") -> dict:
        c = {"title": title, "url": f"https://news.example/{title}", "confidence": conf, "reason": "同主题产品线报道"}
        if group:
            c.update({"region_group": group, "region": "日本", "lang": "日文"})
        return c

    def test_market_first_and_other_needs_high(self) -> None:
        kept, dropped = filter_clues(
            [
                self._clue("other-high", "高", "other"),
                self._clue("other-mid", "中", "other"),
                self._clue("market-mid", "中", "market"),
                self._clue("home-low", "低", "applicant_home"),
            ]
        )
        self.assertEqual([c["title"] for c in kept], ["market-mid", "home-low", "other-high"])
        self.assertEqual([c["title"] for c in dropped], ["other-mid"])

    def test_without_region_keeps_confidence_order(self) -> None:
        kept, _ = filter_clues([self._clue("a", "中"), self._clue("b", "高"), self._clue("c", "低")])
        self.assertEqual([c["title"] for c in kept], ["b", "a", "c"])

    def test_appendix_shows_region(self) -> None:
        clue = {**self._clue("日本ニュース", "中", "market"), "filename": "01-日本ニュース.md"}
        text = render_appendix_b([clue], clues_dir_link="clues/_线索索引")
        self.assertIn("地区：日本（日文 · 本国市场）", text)
        plain = render_appendix_b([{**self._clue("x", "中"), "filename": "01-x.md"}], clues_dir_link="c")
        self.assertNotIn("地区", plain)


class DomainRuleTests(unittest.TestCase):
    def test_inline_ipc_prefixes_loaded(self) -> None:
        rules = {d["label"]: d for d in load_domain_rules()}
        self.assertIn("H01M", rules["化工与材料"]["ipc_prefixes"])
        self.assertEqual(resolve_domain("", "H01M10/48"), "化工与材料")


if __name__ == "__main__":
    unittest.main()
