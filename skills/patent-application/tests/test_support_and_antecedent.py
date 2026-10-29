# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
if str(PKG / "tools") not in sys.path:
    sys.path.insert(0, str(PKG / "tools"))

from audit_claims import audit, summarize
from check_support import audit_dir


class SaidAntecedentTests(unittest.TestCase):
    def test_said_without_first_mention_warns(self) -> None:
        text = (
            "1. 一种调度方法，其特征在于采集节点指标。\n"
            "2. 根据权利要求1所述的方法，其特征在于所述匹配分大于阈值。\n"
        )
        codes = [item.code for item in audit(text) if item.level == "WARNING"]
        self.assertIn("SAID_ANTECEDENT", codes)

    def test_said_after_introduce_passes(self) -> None:
        text = (
            "1. 一种调度方法，其特征在于计算匹配分。\n"
            "2. 根据权利要求1所述的方法，其特征在于所述匹配分大于阈值。\n"
        )
        codes = [item.code for item in audit(text) if item.code == "SAID_ANTECEDENT"]
        self.assertEqual(codes, [])


class SupportCheckTests(unittest.TestCase):
    def test_step_mismatch_and_abstract_length(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "figures").mkdir()
            (root / "权利要求书.md").write_text(
                "1. 一种方法，包括以下步骤：步骤一，采集；步骤二，打分。\n",
                encoding="utf-8",
            )
            (root / "说明书.md").write_text(
                "本发明涉及调度。图1为框图。图2为流程。采集模块用于采集。\n",
                encoding="utf-8",
            )
            (root / "说明书摘要.md").write_text("公开。" + "字" * 320, encoding="utf-8")
            (root / "figures" / "invention_figures.yaml").write_text(
                """
figures:
  - fig: 1
    kind: block_diagram
    columns:
      - id: a
        nodes:
          - {id: n1, label: 采集模块}
  - fig: 2
    kind: flowchart
    nodes:
      - {id: s1, label: "步骤一，采集"}
      - {id: s2, label: "步骤二，派发"}
""",
                encoding="utf-8",
            )
            findings = audit_dir(root)
            codes = {item.code for item in findings}
            self.assertIn("STEP_MISMATCH", codes)
            self.assertIn("ABSTRACT_TOO_LONG", codes)

    def test_aligned_steps_pass_step_check(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "figures").mkdir()
            (root / "权利要求书.md").write_text(
                "1. 一种方法，包括以下步骤：步骤一，采集；步骤二，打分。\n",
                encoding="utf-8",
            )
            (root / "说明书.md").write_text(
                "图1为框图。图2为流程。采集模块用于采集。\n",
                encoding="utf-8",
            )
            (root / "说明书摘要.md").write_text(
                "本发明涉及调度。现有按队列派发不足。本发明通过采集与打分完成派发。",
                encoding="utf-8",
            )
            (root / "figures" / "invention_figures.yaml").write_text(
                """
figures:
  - fig: 1
    kind: block_diagram
    columns:
      - id: a
        nodes:
          - {id: n1, label: 采集模块}
  - fig: 2
    kind: flowchart
    abstract: true
    nodes:
      - {id: s1, label: "步骤一，采集"}
      - {id: s2, label: "步骤二，打分"}
""",
                encoding="utf-8",
            )
            codes = {item.code for item in audit_dir(root)}
            self.assertNotIn("STEP_MISMATCH", codes)
            self.assertNotIn("ABSTRACT_TOO_LONG", codes)
            self.assertNotIn("MODULE_MISSING_SPEC", codes)


class ClaimStyleTests(unittest.TestCase):
    def _case(self, tmp: str, claim1: str, style: str | None) -> list[str]:
        import json as _json

        root = Path(tmp)
        (root / "figures").mkdir()
        (root / "权利要求书.md").write_text(claim1, encoding="utf-8")
        (root / "说明书.md").write_text("图1为流程示意。\n", encoding="utf-8")
        (root / "figures" / "invention_figures.yaml").write_text("figures: []\n", encoding="utf-8")
        (root / "说明书摘要.md").write_text("本发明涉及调度。不足。手段。效果。", encoding="utf-8")
        plan: dict = {"$schema": "application_plan", "version": 1}
        if style:
            plan["claim_style"] = style
        (root / "application_plan.json").write_text(_json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return [item.code for item in audit_dir(root)]

    def test_style_numbered_requires_step_labels(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codes = self._case(raw, "1. 一种方法，其特征在于包括采集；输出。\n", "numbered")
            self.assertIn("CLAIM_STYLE_MISMATCH", codes)

    def test_style_unnumbered_rejects_steps(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codes = self._case(raw, "1. 一种方法，其特征在于包括如下步骤：步骤1，采集。\n", "unnumbered")
            self.assertIn("CLAIM_STYLE_MISMATCH", codes)

    def test_style_numbered_with_steps_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codes = self._case(raw, "1. 一种方法，其特征在于包括如下步骤：步骤1，采集。\n", "numbered")
            self.assertNotIn("CLAIM_STYLE_MISMATCH", codes)

    def test_numbered_style_unnumbered_claim_and_flow_warns_without_style(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "figures").mkdir()
            (root / "权利要求书.md").write_text("1. 一种方法，其特征在于包括采集；输出。\n", encoding="utf-8")
            (root / "说明书.md").write_text("图1为流程示意。\n", encoding="utf-8")
            (root / "figures" / "invention_figures.yaml").write_text(
                "figures:\n  - fig: 1\n    kind: flowchart\n    nodes:\n      - {id: s1, label: \"步骤1，采集\"}\n",
                encoding="utf-8",
            )
            (root / "说明书摘要.md").write_text("本发明涉及调度。", encoding="utf-8")
            codes = [item.code for item in audit_dir(root)]
            self.assertIn("STEP_STYLE_UNVERIFIED", codes)


class CaseDirSchemaTests(unittest.TestCase):
    def test_case_dir_schema_cross_check_runs(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as raw_case:
            root = Path(raw)
            case = Path(raw_case)
            (root / "figures").mkdir()
            (root / "权利要求书.md").write_text(
                "1. 一种装置，其特征在于包括壳体（10）和端盖（20）。\n", encoding="utf-8"
            )
            (root / "说明书.md").write_text("壳体（10）连端盖（20）。\n", encoding="utf-8")
            (root / "说明书摘要.md").write_text("本实用新型涉及壳体。", encoding="utf-8")
            (root / "figures" / "invention_figures.yaml").write_text("figures: []\n", encoding="utf-8")
            (root / "件号登记表.yaml").write_text(
                "parts:\n  - {id: '10', name: 壳体, figures: []}\n  - {id: '20', name: 端盖, figures: []}\n",
                encoding="utf-8",
            )
            (case / "structure_schema.yaml").write_text(
                "parts:\n  - {id: '10', name: 壳体}\n  - {id: '30', name: 支架}\n",
                encoding="utf-8",
            )
            codes = [item.code for item in audit_dir(root, case_dir=case)]
            self.assertIn("SCHEMA_MISSING", codes)
            self.assertIn("REGISTER_EXTRA", codes)


if __name__ == "__main__":
    unittest.main()
