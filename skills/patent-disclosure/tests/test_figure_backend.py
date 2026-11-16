# -*- coding: utf-8 -*-
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

import figure_backend as fb  # noqa: E402


class FigureBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / "case"
        self.home = Path(self.tmp.name) / "home"
        self.env = patch.dict(os.environ, {"PATENT_SKILL_HOME": str(self.home)}, clear=True)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_unconfirmed_asks_user(self) -> None:
        with patch.object(fb.image_runtime, "deps_ok", return_value=True):
            result = fb.probe(self.case)
        self.assertTrue(result["ask_user"])
        self.assertIsNone(result["backend"])
        self.assertFalse(result["cli_ready"])
        self.assertEqual(result["cli_reason"], "api_key_unset")
        self.assertEqual(result["candidates"], ["builtin", "local"])

    def test_cli_ready_with_key(self) -> None:
        with patch.dict(os.environ, {"PATENT_SKILL_IMAGE_API_KEY": "sk"}), \
                patch.object(fb.image_runtime, "deps_ok", return_value=True):
            result = fb.probe(self.case)
        self.assertTrue(result["cli_ready"])
        self.assertEqual(result["candidates"], ["builtin", "cli", "local"])

    def test_confirmed_backend_is_fixed(self) -> None:
        fb.set_backend(self.case, "builtin", confirmed=True, tool_hint="image_gen", model=None)
        self.assertEqual(fb.confirmed_backend(self.case), "builtin")
        result = fb.probe(self.case)
        self.assertFalse(result["ask_user"])
        self.assertEqual(result["candidates"], ["builtin"])

    def test_unconfirmed_set_is_not_fixed(self) -> None:
        fb.set_backend(self.case, "cli", confirmed=False, tool_hint=None, model=None)
        self.assertIsNone(fb.confirmed_backend(self.case))

    def test_local_switch_overrides_state(self) -> None:
        fb.set_backend(self.case, "cli", confirmed=True, tool_hint=None, model=None)
        with patch.dict(os.environ, {fb.SWITCH_ENV: "local"}):
            self.assertEqual(fb.confirmed_backend(self.case), "local")

    def test_sample_record_and_cli(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fb.main(["--case-dir", str(self.case), "--set", "local", "--confirmed",
                     "--sample", "ai_figures/mmd_01.png", "--sample-fig", "mmd_01", "--accept"])
        state = fb.load_state(self.case)
        self.assertEqual(state["backend"], "local")
        self.assertTrue(state["sample"]["accepted"])
        self.assertEqual(state["sample"]["fig_id"], "mmd_01")


if __name__ == "__main__":
    unittest.main()
