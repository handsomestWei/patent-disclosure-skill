# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cnipa_epub_crawler import (  # noqa: E402
    EPUB_TITLE_NO_HIT,
    EPUB_TITLE_RESULT,
    _RESULT_PAGE_READY_JS,
    submit_index_search,
)


class SubmitIndexSearchTests(unittest.TestCase):
    def test_uses_committed_navigation_and_result_ready_wait(self) -> None:
        page = MagicMock()

        submit_index_search(page, "数据标注")

        page.expect_navigation.assert_called_once_with(timeout=120_000, wait_until="commit")
        page.wait_for_function.assert_called_once()
        page.wait_for_load_state.assert_not_called()
        page.wait_for_timeout.assert_not_called()

    def test_wait_checks_result_dom_not_title_only(self) -> None:
        page = MagicMock()

        submit_index_search(page, "数据标注")

        js = page.wait_for_function.call_args.args[0]
        self.assertIs(js, _RESULT_PAGE_READY_JS)
        self.assertIn("#result", js)
        self.assertIn("div.item", js)
        self.assertIn("h1.title", js)
        self.assertIn("titles.noHit", js)
        self.assertIn("titles.result", js)

    def test_passes_title_constants_as_wait_arg(self) -> None:
        page = MagicMock()

        submit_index_search(page, "测试")

        kwargs = page.wait_for_function.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 120_000)
        self.assertEqual(
            kwargs["arg"],
            {"result": EPUB_TITLE_RESULT, "noHit": EPUB_TITLE_NO_HIT},
        )


if __name__ == "__main__":
    unittest.main()
