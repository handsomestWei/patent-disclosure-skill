# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import io
import json
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

MD = """# 交底书

## 3.2 系统框图

```mermaid
flowchart LR
  subgraph W [工作节点]
    A[指标采集]
  end
  B["资源画像聚合"] --> C(匹配分计算)
  A -->|上报| B
```

## 3.4 流程图

```mermaid
flowchart TD
  S1[采集节点指标] --> S2{是否达阈}
  S2 -->|是| S3[重排队首窗口]
```
"""

INVENTION = """$schema: invention_figures
version: 1
figures:
  - fig: 1
    kind: block_diagram
    caption: 系统模块关系示意图
    columns:
      - id: worker
        label: 工作节点
        nodes:
          - {id: n31, label: 指标采集}
      - id: scheduler
        label: 调度器
        nodes:
          - {id: n21, label: 资源画像聚合}
    edges:
      - {from: n31, to: n21}
  - fig: 2
    kind: flowchart
    caption: 调度主流程示意图
    abstract: true
    nodes:
      - {id: step2, row: 1, col: 0, shape: rect, label: "步骤二，计算各节点匹配分"}
      - {id: step1, row: 0, col: 0, shape: rect, label: "步骤一，采集节点指标"}
    edges:
      - {from: step1, to: step2}
  - fig: 3
    kind: source_image
    caption: 场景
    source: floor.png
"""


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class FigureJobsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / "case"
        self.case.mkdir()
        self.env = patch.dict(os.environ, {"PATENT_SKILL_HOME": str(Path(self.tmp.name) / "home")}, clear=True)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def jobs(self) -> list[dict]:
        return fj.load_manifest(self.case)["jobs"]


class MermaidJobsTests(FigureJobsTestBase):
    def prepare(self, text: str = MD) -> list[dict]:
        md = self.case / "draft.md"
        md.write_text(text, encoding="utf-8")
        quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-md", str(md)])
        return self.jobs()

    def test_one_job_per_block_with_kind_and_labels(self) -> None:
        jobs = self.prepare()
        self.assertEqual([j["fig_id"] for j in jobs], ["mmd_01", "mmd_02"])
        self.assertEqual(jobs[0]["kind"], "block_diagram")
        self.assertEqual(jobs[1]["kind"], "flowchart")
        self.assertEqual(jobs[0]["text_verbatim"], ["工作节点", "指标采集", "资源画像聚合", "匹配分计算", "上报"])
        self.assertEqual(jobs[1]["size"], "1536x2048")
        self.assertTrue((self.case / "figure_jobs" / "mmd_02.json").is_file())

    def test_step_ids_written_into_verbatim_and_prompt(self) -> None:
        job = self.prepare()[1]
        self.assertIn("S1 采集节点指标", job["text_verbatim"])
        self.assertIn('S1["S1 采集节点指标"]', job["prompt"])
        self.assertIn("Text (verbatim):", job["prompt"])
        self.assertIn("Do not draw a figure number", job["prompt"])
        self.assertIn("Do not add start/end terminals", job["prompt"])
        self.assertEqual(job["background"], "opaque")

    def test_sha_matches_mermaid_render_normalisation(self) -> None:
        from mermaid_render import ensure_step_ids_in_visible_labels

        job = self.prepare()[1]
        body = "flowchart TD\n  S1[采集节点指标] --> S2{是否达阈}\n  S2 -->|是| S3[重排队首窗口]\n"
        fixed, _ = ensure_step_ids_in_visible_labels(body)
        self.assertEqual(job["source"]["sha"], fj.mermaid_sha(fixed))

    def test_record_requires_confirmed_backend(self) -> None:
        self.prepare()
        img = self.case / "gen.png"
        img.write_bytes(b"png")
        with self.assertRaises(SystemExit):
            quiet(fj.main, ["record", "--case-dir", str(self.case), "--fig", "mmd_01", "--image", str(img)])
        self.assertFalse(Path(self.jobs()[0]["out"]).exists())

    def test_record_status_and_reprepare_keeps_unchanged(self) -> None:
        self.prepare()
        figure_backend.set_backend(self.case, "builtin", confirmed=True, tool_hint=None, model=None)
        img = self.case / "gen.png"
        img.write_bytes(b"png")
        quiet(fj.main, ["record", "--case-dir", str(self.case), "--fig", "mmd_01", "--image", str(img),
                        "--qa-note", "ok"])
        job = self.jobs()[0]
        self.assertEqual((job["status"], job["backend"]), ("recorded", "builtin"))
        self.assertEqual(Path(job["out"]).read_bytes(), b"png")
        self.assertEqual(quiet(fj.main, ["status", "--case-dir", str(self.case)]), 2)

        # 迭代：只改流程图，框图保持已登记
        jobs = self.prepare(MD.replace("重排队首窗口", "保持队序"))
        self.assertEqual([j["status"] for j in jobs], ["recorded", "pending"])

        quiet(fj.main, ["block", "--case-dir", str(self.case), "--fig", "mmd_02", "--reason", "错字"])
        self.assertEqual(quiet(fj.main, ["status", "--case-dir", str(self.case)]), 2)
        quiet(fj.main, ["fallback", "--case-dir", str(self.case), "--fig", "mmd_02", "--reason", "mermaid_render"])
        self.assertEqual(quiet(fj.main, ["status", "--case-dir", str(self.case)]), 0)
        summary = fj.summarize(fj.load_manifest(self.case))
        self.assertEqual(summary["fallback_local"], [{"fig_id": "mmd_02", "reason": "mermaid_render"}])

    def test_recorded_image_lookup(self) -> None:
        self.prepare()
        figure_backend.set_backend(self.case, "cli", confirmed=True, tool_hint=None, model=None)
        out = Path(self.jobs()[1]["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ai")
        quiet(fj.main, ["record", "--case-dir", str(self.case), "--fig", "mmd_02"])
        manifest = fj.manifest_path(self.case)
        src = 'flowchart TD\n  S1["S1 采集节点指标"] --> S2{"S2 是否达阈"}\n  S2 -->|是| S3["S3 重排队首窗口"]\n'
        self.assertEqual(fj.recorded_image_for_mermaid(manifest, src), out)
        self.assertIsNone(fj.recorded_image_for_mermaid(manifest, "flowchart TD\n  A --> B\n"))


class InventionJobsTests(FigureJobsTestBase):
    def test_jobs_and_post_processing_paths(self) -> None:
        figures = self.case / "figures"
        figures.mkdir()
        plan = figures / "invention_figures.yaml"
        plan.write_text(INVENTION, encoding="utf-8")
        quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-invention-yaml", str(plan)])
        jobs = self.jobs()
        self.assertEqual([j["fig_id"] for j in jobs], ["fig_1", "fig_2"])
        block, flow = jobs
        self.assertEqual(block["kind"], "application_block_diagram")
        self.assertIn("「工作节点」", block["prompt"])
        self.assertIn("Arrow 「指标采集」 → 「资源画像聚合」", block["prompt"])
        self.assertEqual(flow["text_verbatim"], ["步骤一，采集节点指标", "步骤二，计算各节点匹配分"])
        self.assertTrue(flow["post"]["out"].endswith("图2.png"))
        self.assertTrue(flow["post"]["abstract_out"].endswith("摘要附图.png"))
        self.assertEqual(flow["fallback"]["args"][-2:], ["--only", "2"])


class LineartJobsTests(FigureJobsTestBase):
    def test_structure_job_with_callout_and_refs(self) -> None:
        ref = self.case / "photo.png"
        ref.write_bytes(b"x")
        assist = self.case / "lineart_assist"
        assist.mkdir()
        (self.case / "structure_callout_anchors.yaml").write_text(
            "views:\n  - view_name: 主视图\n    callouts:\n      - {id: '1', name: 壳体, anchor: [0.5, 0.5], label: [0.9, 0.5]}\n",
            encoding="utf-8",
        )
        payload = {"jobs": [
            {"view_name": "主视图", "reference_images": [str(ref), str(self.case / "missing.png")],
             "callouts": [{"id": "1", "name": "壳体"}, {"id": "2", "name": "端盖"}], "callout_mode": "overlay",
             "gen_prompt": "Black-and-white patent-style STRUCTURE line art", "output_path": "lineart_assist/主视图_structure_lineart.png",
             "callout_output_path": "lineart_assist/主视图_structure_lineart_callouts.png"},
            {"view_name": "主视图", "part_id": "2", "name": "端盖", "image_path": "lineart_assist/parts/主视图_2.png",
             "reference_images": [str(ref)], "gen_prompt": "ONE isolated part"},
        ]}
        jobs_path = assist / "structure_lineart_jobs.json"
        jobs_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-lineart-jobs", str(jobs_path), "--with-callouts"])
        jobs = {j["fig_id"]: j for j in self.jobs()}
        self.assertEqual(set(jobs), {"lineart_主视图", "callout_主视图", "part_主视图_2"})
        contour = jobs["lineart_主视图"]
        self.assertEqual([i["path"] for i in contour["input_images"]], [str(ref)])
        self.assertTrue(contour["out"].endswith("主视图_structure_lineart.png"))
        callout = jobs["callout_主视图"]
        self.assertEqual(callout["input_images"][0]["path"], contour["out"])
        self.assertEqual(callout["text_verbatim"], ["1", "2"])
        self.assertIn("x=0.5, y=0.5", callout["prompt"])
        self.assertIn("structure_callout_overlay.py", callout["fallback"]["tool"])
        self.assertEqual(jobs["part_主视图_2"]["kind"], "structure_part")

    def test_design_job(self) -> None:
        jobs_path = self.case / "design_lineart_jobs.json"
        jobs_path.write_text(json.dumps({"jobs": [{"view_name": "主视图", "gen_prompt": "line art",
                                                   "output_path": "lineart_assist/主视图_lineart.png"}]}),
                             encoding="utf-8")
        quiet(fj.main, ["prepare", "--case-dir", str(self.case), "--from-lineart-jobs", str(jobs_path)])
        job = self.jobs()[0]
        self.assertEqual((job["fig_id"], job["kind"]), ("design_主视图", "design_lineart"))
        self.assertIn("No dimension lines", job["prompt"])


class TemplateTests(unittest.TestCase):
    def test_every_kind_has_valid_size(self) -> None:
        import image_api

        data = fj.load_templates()
        for kind, spec in data["kinds"].items():
            with self.subTest(kind=kind):
                image_api._validate_size(str(spec["size"]), "gpt-image-2.5-flare")
                self.assertIn(spec["quality"], image_api.ALLOWED_QUALITIES)


if __name__ == "__main__":
    unittest.main()
