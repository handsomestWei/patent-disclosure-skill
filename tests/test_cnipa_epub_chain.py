# -*- coding: utf-8 -*-
"""
串联验证：与同目录能力对齐——运行 `tools/cnipa_epub_search.py`（一步：爬取 + 解析，**不落盘 HTML**）。

需已安装：pip install -r tools/requirements-cnipa.txt && python -m playwright install chromium
或设 BROWSER_BACKEND=agent-browser 并安装 agent-browser（npm i -g agent-browser && agent-browser install）

在仓库根目录执行：

  python tests/test_cnipa_epub_chain.py

可选参数指定关键词：

  python tests/test_cnipa_epub_chain.py 批处理

无参数时本测试脚本仍传入「知识图谱」以便本地联调；**命令行直接运行** `cnipa_epub_search.py` **须自带关键词**（不设默认）。技能要求 Agent 在 Step 5 **每词一次 Bash、自行合并 JSON**（见 `prior_art_search.md`）；本测试单次传参仅为联调。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv:
        extra = argv
    else:
        extra = ["知识图谱"]
    os.environ.setdefault("EPUB_WAF_MAX_WAIT_SEC", "180")

    backend = os.environ.get("BROWSER_BACKEND", "").strip().lower()
    if backend == "agent-browser":
        from shutil import which

        if not which("agent-browser"):
            print("请先安装: npm i -g agent-browser && agent-browser install", file=sys.stderr)
            return 1
    else:
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("请先安装: pip install -r tools/requirements-cnipa.txt", file=sys.stderr)
            return 1

    from cnipa_epub_search import main as search_main

    return search_main(extra)


if __name__ == "__main__":
    raise SystemExit(main())
