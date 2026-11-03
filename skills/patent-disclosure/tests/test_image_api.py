# -*- coding: utf-8 -*-
"""image_api.py（移植自 codex-ppt image_gen.py）离线回归：校验、dry-run、配置、provider 路由。"""
from __future__ import annotations

import base64
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

import image_api  # noqa: E402
import image_runtime  # noqa: E402
from image_providers import create_image_provider  # noqa: E402
from image_providers.atlascloud import AtlasCloudImageProvider  # noqa: E402
from image_providers.openai_compatible import OpenAICompatibleImageProvider  # noqa: E402


def run_cli(*args: str, env: dict[str, str] | None = None) -> dict:
    out = io.StringIO()
    with (
        patch.object(sys, "argv", ["image_api.py", *args]),
        patch.object(image_api, "_load_runtime_env"),
        patch.dict(os.environ, env or {}, clear=True),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        image_api.main()
    return json.loads(out.getvalue())


class ValidationTests(unittest.TestCase):
    def test_gpt_image_25_accepts_new_quality(self) -> None:
        for model in ("gpt-image-2.5-flare", "openai/gpt-image-2.5-sunburst/edit"):
            for quality in ("xhigh", "max"):
                image_api._validate_generate_payload({"model": model, "quality": quality, "size": "1536x2048"})

    def test_legacy_models_reject_new_quality(self) -> None:
        for model in ("gpt-image-2", "gpt-image-1.5"):
            with self.subTest(model=model), self.assertRaises(SystemExit):
                image_api._validate_quality("max", model)

    def test_size_constraints(self) -> None:
        image_api._validate_size("2048x1536", "gpt-image-2.5-flare")
        for size in ("4096x2160", "1025x1024", "3840x1024", "256x256"):
            with self.subTest(size=size), self.assertRaises(SystemExit):
                image_api._validate_size(size, "gpt-image-2.5-flare")

    def test_non_gpt_image_model_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            image_api._validate_model("dall-e-3")


class CliTests(unittest.TestCase):
    def test_patent_defaults(self) -> None:
        result = run_cli("generate", "--prompt", "flowchart", "--dry-run")
        self.assertEqual(result["model"], "gpt-image-2.5-flare")
        self.assertEqual(result["size"], "1536x2048")
        self.assertEqual(result["quality"], "high")
        self.assertEqual(result["endpoint"], "/v1/images/generations")

    def test_model_env_overrides_default(self) -> None:
        result = run_cli("generate", "--prompt", "x", "--dry-run", env={"PATENT_SKILL_IMAGE_MODEL": "gpt-image-2"})
        self.assertEqual(result["model"], "gpt-image-2")

    def test_codex_and_openai_env_are_ignored(self) -> None:
        env = {"CODEX_PPT_IMAGE_MODEL": "gpt-image-2", "OPENAI_BASE_URL": "https://api.atlascloud.ai/api/v1/model"}
        result = run_cli("generate", "--prompt", "x", "--dry-run", env=env)
        self.assertEqual(result["model"], "gpt-image-2.5-flare")
        self.assertEqual(result["endpoint"], "/v1/images/generations")

    def test_job_without_images_generates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "fig_01.json"
            job.write_text(json.dumps({"fig_id": "fig_01", "prompt": "Use case: x", "size": "2048x1536",
                                       "quality": "medium", "out": str(Path(tmp) / "a.png")}), encoding="utf-8")
            result = run_cli("job", "--job", str(job), "--dry-run")
        self.assertEqual(result["endpoint"], "/v1/images/generations")
        self.assertEqual(result["size"], "2048x1536")
        self.assertEqual(result["quality"], "medium")
        self.assertEqual(result["prompt"], "Use case: x")

    def test_job_with_images_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.png"
            ref.write_bytes(b"png")
            job = Path(tmp) / "j.json"
            job.write_text(json.dumps({"fig_id": "design_main", "prompt": "lineart", "out": str(Path(tmp) / "b.png"),
                                       "input_images": [{"path": str(ref), "role": "product reference"}]}),
                           encoding="utf-8")
            result = run_cli("job", "--job", str(job), "--dry-run")
        self.assertEqual(result["endpoint"], "/v1/images/edits")
        self.assertEqual(result["image"], [str(ref)])

    def test_missing_key_exits_with_config_hint(self) -> None:
        err = io.StringIO()
        with (
            patch.object(sys, "argv", ["image_api.py", "generate", "--prompt", "x"]),
            patch.object(image_api, "_load_runtime_env"),
            patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stderr(err),
            self.assertRaises(SystemExit) as ctx,
        ):
            image_api.main()
        self.assertEqual(ctx.exception.code, 3)
        self.assertIn("image_runtime.py", err.getvalue())

    def test_generate_writes_decoded_image(self) -> None:
        payload = base64.b64encode(b"PNGDATA").decode()

        class FakeProvider:
            def generate(self, request):
                self.request = request
                return [payload]

        fake = FakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "x.png"
            with (
                patch.object(sys, "argv", ["image_api.py", "generate", "--prompt", "x", "--out", str(out)]),
                patch.object(image_api, "_load_runtime_env"),
                patch.object(image_api, "create_image_provider", return_value=fake),
                patch.dict(os.environ, {"PATENT_SKILL_IMAGE_API_KEY": "sk-test"}, clear=True),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(image_api.main(), 0)
            self.assertEqual(out.read_bytes(), b"PNGDATA")
        self.assertEqual(fake.request["size"], "1536x2048")


class RuntimeEnvTests(unittest.TestCase):
    def test_env_file_loaded_and_process_env_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                "PATENT_SKILL_IMAGE_API_KEY=from-file\nPATENT_SKILL_IMAGE_MODEL=gpt-image-2\nOPENAI_API_KEY=ignored\n",
                encoding="utf-8",
            )
            env = {"PATENT_SKILL_HOME": tmp, "PATENT_SKILL_IMAGE_MODEL": "gpt-image-2.5-sunburst"}
            with patch.dict(os.environ, env, clear=True):
                image_api._load_runtime_env()
                self.assertEqual(os.environ["PATENT_SKILL_IMAGE_API_KEY"], "from-file")
                self.assertEqual(os.environ["PATENT_SKILL_IMAGE_MODEL"], "gpt-image-2.5-sunburst")
                self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_config_writes_masked_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"PATENT_SKILL_HOME": tmp}, clear=True):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                image_runtime.main(["config", "--api-key", "sk-1234567890", "--base-url", "https://x.example.com/v1"])
            values = image_runtime.parse_env_file(Path(tmp) / ".env")
        self.assertEqual(values["PATENT_SKILL_IMAGE_API_KEY"], "sk-1234567890")
        self.assertEqual(values["PATENT_SKILL_IMAGE_BASE_URL"], "https://x.example.com/v1")
        self.assertNotIn("sk-1234567890", out.getvalue())


class ProviderFactoryTests(unittest.TestCase):
    def test_routes_by_base_url(self) -> None:
        self.assertIsInstance(create_image_provider(api_key="k", base_url=None), OpenAICompatibleImageProvider)
        self.assertIsInstance(
            create_image_provider(api_key="k", base_url="https://proxy.example.com/v1"), OpenAICompatibleImageProvider
        )
        self.assertIsInstance(
            create_image_provider(api_key="k", base_url="https://api.atlascloud.ai/api/v1/model"),
            AtlasCloudImageProvider,
        )


if __name__ == "__main__":
    unittest.main()
