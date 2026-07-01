# -*- coding: utf-8 -*-
"""
CNIPA epub 检索链路联调脚本（非测试，无断言）。

本脚本仅用于本地联调验证 cnipa_epub_search.py 能否正常访问国知局公布站。
需 Playwright + Chromium，会发起真实 HTTP 请求。

在仓库根目录执行：
  python tests/test_cnipa_epub_chain.py [可选关键词]

Agent 全流程中，C 每词一次 Bash、自行合并 JSON（见 prior_art_search.md）。
本脚本仅用于开发阶段验证工具链路是否畅通。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


@pytest.mark.skip(reason="联调脚本，发起真实 HTTP 请求，非自动化测试")
def test_cnipa_epub_search_smoke() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("Playwright 未安装")

    os.environ.setdefault("EPUB_WAF_MAX_WAIT_SEC", "180")

    from cnipa_epub_search import main as search_main

    rc = search_main(["知识图谱"])
    # 仅验证不崩溃，不做断言
    assert rc in (0, 1)
