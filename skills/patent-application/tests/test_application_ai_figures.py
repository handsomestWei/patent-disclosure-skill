# -*- coding: utf-8 -*-
"""申请发明附图走生图：job 登记即出黑白 图N.png/svg；未过 QA 的图用 --only 回退本地渲染。"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PKG = Path(__file__).resolve().parents[1]
if str(PKG / "tools") not in sys.path:
    sys.path.insert(0, str(PKG / "tools"))

import figure_backend  # noqa: E402
import figure_jobs as fj  # noqa: E402
import render_invention_figures as rif  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

PLAN = """$schema: invention_figures
version: 1
figures:
  - fig: 1
    kind: block_diagram
    caption: 系统模块关系示意图
    columns:
      - id: a
        label: 工作节点
        nodes:
          - {id: n1, label: 指标采集}
    edges: []
  - fig: 2
    kind: flowchart
    caption: 主流程
    abstract: true
    nodes:
      - {id: s1, row: 0, col: 0, shape: rect, label: "步骤一，采集"}
      - {id: s2, row: 1, col: 0, shape: rect, label: "步骤二，派发"}
    edges:
      - {from: s1, to: s2}
"""


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class ApplicationAiFigureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)
        self.figures = self.case / "figures"
        self.figures.mkdir()
        self.plan = self.figures / "invention_figures.yaml"
        self.plan.write_text(PLAN, encoding="utf-8")
        self.env = patch.dict(os.environ, {"PATENT_SKILL_HOME": str(self.case / "home")}, clear=True)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_from_md_is_disclosure_only(self) -> None:
        md = self.case / "a.md"
        md.write_text("```mermaid\nflowchart TD\n  A-->B\n```\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-md", str(md)])

    @unittest.skipIf(Image is None, "Pillow 未安装")
    def test_record_writes_bw_figure_and_abstract(self) -> None:
        quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-invention-yaml", str(self.plan)])
        figure_backend.set_backend(self.case, "cli", confirmed=True, tool_hint=None, model=None)
        gen = self.case / "gen.png"
        im = Image.new("RGB", (800, 1000), (250, 250, 250))
        ImageDraw.Draw(im).rectangle((300, 200, 500, 400), outline=(30, 30, 30), width=5)
        im.save(gen)
        quiet(fj.main, ["record", "--case-dir", str(self.case), "--fig", "fig_2", "--image", str(gen)])
        with Image.open(self.figures / "图2.png") as out:
            self.assertEqual(out.mode, "1")
            self.assertLess(out.size[0], 400)
        self.assertTrue((self.figures / "图2.svg").is_file())
        self.assertTrue((self.figures / "摘要附图.png").is_file())
        self.assertFalse((self.figures / "图1.png").exists())

    def test_only_filters_figures(self) -> None:
        plan = rif._load(self.plan)
        with patch.object(rif, "svg_to_png", return_value=False):
            result = rif.render_plan(plan, self.figures, plan_dir=self.figures, only={1})
        self.assertEqual(result["svg"], 1)
        self.assertTrue((self.figures / "图1.svg").is_file())
        self.assertFalse((self.figures / "图2.svg").exists())


if __name__ == "__main__":
    unittest.main()
