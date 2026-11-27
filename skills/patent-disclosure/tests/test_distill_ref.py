# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

PKG = Path(__file__).resolve().parents[1]
if str(PKG / "tools") not in sys.path:
    sys.path.insert(0, str(PKG / "tools"))

from distill_ref import ENV_OUTPUT_DIR, inspect_ref, main, resolve_ref


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _batch(root: Path, *, strength: str = "strong", patent_type: str = "invention") -> Path:
    batch = root / "demo"
    _dump(batch / "batch.yaml", {"batch_id": "demo", "style_dir": ".", "cases": [{"case_id": "c1", "dir": "cases/c1"}]})
    _dump(
        batch / "profile.yaml",
        {"profile_id": "demo", "patent_type": patent_type, "tracks": ["style"], "style": {"enabled": True, "status": "draft"}},
    )
    _write(batch / "style.md", "# 文风\n\n先结构后效果。\n")
    _write(batch / "sections" / "application.md", "# 章节\n\n权要短句。\n")
    case = batch / "cases" / "c1"
    _dump(
        case / "profile.yaml",
        {
            "profile_id": "c1",
            "patent_type": patent_type,
            "tracks": ["strategy"],
            "strategy": {"enabled": True, "strength": strength, "status": "draft"},
        },
    )
    if strength == "observe":
        _write(case / "策略观察.md", "# 策略观察\n\n## 5. 观察\n\n独权只卡步骤。\n")
    else:
        _dump(
            case / "playbook.yaml",
            {
                "claims": {
                    "independent_grain": "method_steps",
                    "dependent_layers": ["preferred_param", "branch"],
                    "never_in_independent": ["numeric_range"],
                },
                "spec": {"extra_embodiments": True},
                "disclosure": {"point_split": "necessary_vs_preferred"},
                "apply": {
                    "when_writing_disclosure": "第五章按删除测试切开。",
                    "when_writing_claims": "数值进从属。",
                    "when_writing_spec": "先走通独权步骤。",
                },
            },
        )
    return batch


class DistillRefTests(unittest.TestCase):
    def test_application_reads_style_and_playbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp))
            rows = inspect_ref(batch, patent_type="invention", stage="application")
            verdicts = {row["kind"]: row["verdict"] for row in rows}
            self.assertEqual(verdicts, {"style": "use", "case": "use"})
            case = next(row for row in rows if row["kind"] == "case")
            self.assertEqual(set(case["apply"]), {"when_writing_claims", "when_writing_spec"})
            self.assertTrue(any(line.startswith("claims ") for line in case["blocks"]))
            self.assertFalse(any(line.startswith("disclosure ") for line in case["blocks"]))

    def test_disclosure_skips_style_and_reads_disclosure_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp))
            rows = inspect_ref(batch, patent_type="invention", stage="disclosure")
            style = next(row for row in rows if row["kind"] == "style")
            case = next(row for row in rows if row["kind"] == "case")
            self.assertEqual(style["verdict"], "skip")
            self.assertEqual(case["verdict"], "use")
            self.assertEqual(set(case["apply"]), {"when_writing_disclosure"})
            self.assertIn("claims never_in_independent=numeric_range", case["blocks"])

    def test_type_mismatch_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp), patent_type="utility_model")
            rows = inspect_ref(batch, patent_type="invention", stage="application")
            self.assertTrue(all(row["verdict"] == "skip" for row in rows))

    def test_observe_case_reads_note_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp), strength="observe")
            rows = inspect_ref(batch, patent_type="invention", stage="application")
            case = next(row for row in rows if row["kind"] == "case")
            self.assertEqual(case["verdict"], "observe")
            self.assertEqual(case["files"][0].name, "策略观察.md")

    def test_publication_only_batch_reports_missing_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp), strength="observe")
            data = yaml.safe_load((batch / "batch.yaml").read_text(encoding="utf-8"))
            data["style_dir"] = ""
            _dump(batch / "batch.yaml", data)
            rows = inspect_ref(batch, patent_type="invention", stage="application")
            style = next(row for row in rows if row["kind"] == "style")
            self.assertEqual(style["verdict"], "skip")
            self.assertIn("没有文风", style["reason"])
            disclosure_rows = inspect_ref(batch, patent_type="invention", stage="disclosure")
            self.assertFalse(any(row["kind"] == "style" for row in disclosure_rows))

    def test_todo_playbook_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = _batch(Path(tmp))
            playbook = batch / "cases" / "c1" / "playbook.yaml"
            data = yaml.safe_load(playbook.read_text(encoding="utf-8"))
            data["apply"]["when_writing_claims"] = "TODO"
            _dump(playbook, data)
            rows = inspect_ref(batch, patent_type="invention", stage="application")
            case = next(row for row in rows if row["kind"] == "case")
            self.assertEqual(case["verdict"], "skip")

    def test_resolve_by_id_and_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = _batch(root)
            self.assertEqual(resolve_ref("demo", root), batch)
            self.assertEqual(resolve_ref("c1", root), batch / "cases" / "c1")
            self.assertEqual(resolve_ref(str(batch / "style.md"), root), batch)
            self.assertIsNone(resolve_ref("missing", root))

    def test_cli_missing_ref_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get(ENV_OUTPUT_DIR)
            os.environ[ENV_OUTPUT_DIR] = tmp
            try:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    code = main(["--ref", "missing", "--type", "invention", "--stage", "application"])
            finally:
                if old is None:
                    os.environ.pop(ENV_OUTPUT_DIR, None)
                else:
                    os.environ[ENV_OUTPUT_DIR] = old
            self.assertEqual(code, 0)
            self.assertIn("DISTILL_REF_SKIP: missing", buffer.getvalue())
            self.assertIn("DISTILL_REF_SUMMARY: use=0 observe=0 skip=1", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
