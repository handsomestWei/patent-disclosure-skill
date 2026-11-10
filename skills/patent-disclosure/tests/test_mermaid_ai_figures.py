# -*- coding: utf-8 -*-
"""mermaid_render.py --ai-figures：命中已登记生成图则引用；未命中回退本地；不带参数行为不变。"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SHARED = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(SHARED))

import figure_backend  # noqa: E402
import figure_jobs as fj  # noqa: E402
import mermaid_render  # noqa: E402

MD = """# 交底

## 3.2 系统框图

```mermaid
flowchart LR
  A[采集] --> B[调度]
```

## 3.4 流程图

```mermaid
flowchart TD
  S1[采集节点指标] --> S2[计算匹配分]
```
"""


class FakeLocal:
    rendered: list[str] = []

    def __init__(self, **_kw) -> None:
        pass

    def __enter__(self):
        return self

    def render_one(self, src: str, png: Path) -> None:
        FakeLocal.rendered.append(src)
        png.parent.mkdir(parents=True, exist_ok=True)
        png.write_bytes(b"LOCAL")

    def close(self) -> None:
        pass


class MermaidAiFiguresTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeLocal.rendered = []
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)
        self.draft = self.case / "draft.md"
        self.draft.write_text(MD, encoding="utf-8")
        self.env = patch.dict(os.environ, {"PATENT_SKILL_HOME": str(self.case / "home")}, clear=True)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def run_render(self, out_name: str, *extra: str) -> str:
        out = self.case / "out" / out_name
        with patch.object(mermaid_render, "_PlaywrightMermaid", FakeLocal), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mermaid_render.main(["-i", str(self.draft), "-o", str(out), "--no-docx", *extra]), 0)
        return out.read_text(encoding="utf-8")

    def record_flowchart(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fj.main(["prepare", "--case-dir", str(self.case), "--from-md", str(self.draft)])
            figure_backend.set_backend(self.case, "cli", confirmed=True, tool_hint=None, model=None)
            img = self.case / "gen.png"
            img.write_bytes(b"AI")
            fj.main(["record", "--case-dir", str(self.case), "--fig", "mmd_02", "--image", str(img)])

    def test_hit_uses_generated_and_miss_renders_locally(self) -> None:
        self.record_flowchart()
        md = self.run_render("final.md", "--ai-figures", str(fj.manifest_path(self.case)))
        figs = self.case / "out" / "mermaid_figures"
        self.assertEqual((figs / "fig_001.png").read_bytes(), b"LOCAL")
        self.assertEqual((figs / "fig_002.png").read_bytes(), b"AI")
        self.assertEqual(len(FakeLocal.rendered), 1)
        self.assertIn("<!-- ![图示 2](mermaid_figures/fig_002.png) -->", md)

    def test_stale_figure_falls_back(self) -> None:
        self.record_flowchart()
        self.draft.write_text(MD.replace("计算匹配分", "派发任务"), encoding="utf-8")
        self.run_render("final.md", "--ai-figures", str(fj.manifest_path(self.case)))
        self.assertEqual((self.case / "out" / "mermaid_figures" / "fig_002.png").read_bytes(), b"LOCAL")
        self.assertEqual(len(FakeLocal.rendered), 2)

    def test_output_identical_without_flag(self) -> None:
        plain = self.run_render("plain.md")
        with_empty = self.run_render("flag.md", "--ai-figures", str(self.case / "missing.json"))
        self.assertEqual(plain, with_empty)


if __name__ == "__main__":
    unittest.main()
