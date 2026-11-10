#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专利附图 CLI 出图后端：GPT Image 文生图 / 图生图（edit）。

宿主没有内置生图工具、内置工具缺必需能力、或用户点名 API/CLI 时使用。
流程纪律见 ``prompts/figure_generation.md``；后端选择见 ``figure_backend.py``。

配置只读本技能自己的运行时（与其它技能互不影响）：
  ``${PATENT_SKILL_HOME:-~/.patent-skill}/.env`` 中的
  PATENT_SKILL_IMAGE_API_KEY / PATENT_SKILL_IMAGE_BASE_URL / PATENT_SKILL_IMAGE_MODEL。
进程环境变量优先于 .env。写配置用 ``image_runtime.py config``。

  python tools/image_api.py job --job outputs/case/figure_jobs/fig_01.json
  python tools/image_api.py generate --prompt-file p.txt --out a.png
  python tools/image_api.py edit --image ref.png --prompt-file p.txt --out b.png

stdout 机读前缀 ``IMAGE_API:``。

Adapted from ningzimu/codex-ppt-skill ``scripts/image_gen.py`` (MIT License).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from image_providers import create_image_provider
from image_providers.atlascloud import atlascloud_model_for_operation
from stdio_utf8 import ensure_utf8_stdio  # noqa: E402

DEFAULT_MODEL = "gpt-image-2.5-flare"
# 专利附图多为竖版（A4 版心），3:4 且为 16 的倍数
DEFAULT_SIZE = "1536x2048"
DEFAULT_QUALITY = "high"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_CONCURRENCY = 5
DEFAULT_DOWNSCALE_SUFFIX = "-web"
DEFAULT_OUTPUT_PATH = "outputs/figures/output.png"
GPT_IMAGE_MODEL_PREFIX = "gpt-image-"

ALLOWED_LEGACY_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
ALLOWED_QUALITIES = {"low", "medium", "high", "xhigh", "max", "auto"}
ALLOWED_BACKGROUNDS = {"transparent", "opaque", "auto", None}
ALLOWED_INPUT_FIDELITIES = {"low", "high", None}

GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_RATIO = 3.0

MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_BATCH_JOBS = 500
DEFAULT_RUNTIME_HOME = "~/.patent-skill"
HOME_ENV = "PATENT_SKILL_HOME"
API_KEY_ENV = "PATENT_SKILL_IMAGE_API_KEY"
BASE_URL_ENV = "PATENT_SKILL_IMAGE_BASE_URL"
MODEL_ENV = "PATENT_SKILL_IMAGE_MODEL"
ENV_FIELDS = (API_KEY_ENV, BASE_URL_ENV, MODEL_ENV)


def _die(message: str, code: int = 1) -> None:
    print(f"IMAGE_API: ERROR {message}", file=sys.stderr)
    raise SystemExit(code)


def _warn(message: str) -> None:
    print(f"IMAGE_API: WARN {message}", file=sys.stderr)


def _runtime_home() -> Path:
    return Path(os.getenv(HOME_ENV, DEFAULT_RUNTIME_HOME)).expanduser()


def _runtime_env_path() -> Path:
    return _runtime_home() / ".env"


def _load_runtime_env() -> None:
    path = _runtime_env_path()
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ENV_FIELDS or os.getenv(key):
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def _default_model() -> str:
    return os.getenv(MODEL_ENV) or DEFAULT_MODEL


def _api_key() -> Optional[str]:
    return os.getenv(API_KEY_ENV) or None


def _api_base_url() -> Optional[str]:
    return os.getenv(BASE_URL_ENV) or None


def _api_target_label() -> str:
    base_url = _api_base_url()
    if base_url:
        if _is_atlascloud_base_url(base_url):
            return f"AtlasCloud provider adapter ({BASE_URL_ENV}={base_url})"
        return f"third-party image API or OpenAI-compatible proxy ({BASE_URL_ENV}={base_url})"
    return f"official OpenAI API ({BASE_URL_ENV} unset)"


def _is_atlascloud_base_url(base_url: str) -> bool:
    hostname = urlparse(base_url).hostname or ""
    return "atlascloud.ai" in hostname.lower()


def _preview_endpoint(kind: str) -> str:
    base_url = _api_base_url()
    if base_url and _is_atlascloud_base_url(base_url):
        return "/api/v1/model/generateImage"
    if kind == "edit":
        return "/v1/images/edits"
    return "/v1/images/generations"


def _preview_model(model: str, kind: str) -> str:
    base_url = _api_base_url()
    if base_url and _is_atlascloud_base_url(base_url):
        operation = "edit" if kind == "edit" else "text-to-image"
        return atlascloud_model_for_operation(model, operation)
    return model


def _dependency_hint(package: str, *, upgrade: bool = False) -> str:
    package_arg = f"-U {package}" if upgrade else package
    requirements = _TOOLS / "requirements-image.txt"
    return (
        "征得用户同意后安装出图依赖："
        f"`python -m pip install -r {requirements}`，或单装 `python -m pip install {package_arg}`。"
    )


def _ensure_api_key(dry_run: bool) -> None:
    if _api_key():
        print(f"IMAGE_API: key=set target={_api_target_label()}", file=sys.stderr)
        return
    if dry_run:
        _warn(f"{API_KEY_ENV} is not set; dry-run only. API target: {_api_target_label()}.")
        return
    runtime_script = _TOOLS / "image_runtime.py"
    base_url = _api_base_url()
    model = _default_model()
    if base_url:
        command = (
            f'python {runtime_script} config --api-key "your-api-key" '
            f'--base-url "{base_url}" --model {model}'
        )
    else:
        command = f'python {runtime_script} config --api-key "your-api-key" --model {model}'
    _die(
        f"{API_KEY_ENV} 未配置，CLI 出图后端不可用。\n"
        "宿主有内置生图工具时优先用内置工具；否则请用户配置一次（只写本技能运行时）：\n"
        f"  {command}\n"
        f"第三方 OpenAI 兼容代理另传 --base-url（写入 {BASE_URL_ENV}）。\n"
        "仍不可用时按 prompts/figure_generation.md 回退本地渲染。",
        code=3,
    )


def _read_prompt(prompt: Optional[str], prompt_file: Optional[str]) -> str:
    if prompt and prompt_file:
        _die("Use --prompt or --prompt-file, not both.")
    if prompt_file:
        if prompt_file == "-":
            return sys.stdin.read().strip()
        path = Path(prompt_file)
        if not path.exists():
            _die(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
    if prompt:
        return prompt.strip()
    _die("Missing prompt. Use --prompt or --prompt-file.")
    return ""  # unreachable


def _check_image_paths(paths: Iterable[str]) -> List[Path]:
    resolved: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            _die(f"Image file not found: {path}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Image exceeds 50MB limit: {path}")
        resolved.append(path)
    return resolved


def _normalize_output_format(fmt: Optional[str]) -> str:
    if not fmt:
        return DEFAULT_OUTPUT_FORMAT
    fmt = fmt.lower()
    if fmt not in {"png", "jpeg", "jpg", "webp"}:
        _die("output-format must be png, jpeg, jpg, or webp.")
    return "jpeg" if fmt == "jpg" else fmt


def _parse_size(size: str) -> Optional[Tuple[int, int]]:
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", size)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _validate_gpt_image_2_size(size: str) -> None:
    if size == "auto":
        return

    parsed = _parse_size(size)
    if parsed is None:
        _die("size must be auto or WIDTHxHEIGHT, for example 1024x1024.")

    width, height = parsed
    max_edge = max(width, height)
    min_edge = min(width, height)
    total_pixels = width * height

    if max_edge > GPT_IMAGE_2_MAX_EDGE:
        _die("GPT Image 2 / 2.5 size maximum edge length must be less than or equal to 3840px.")
    if width % 16 != 0 or height % 16 != 0:
        _die("GPT Image 2 / 2.5 size width and height must be multiples of 16px.")
    if max_edge / min_edge > GPT_IMAGE_2_MAX_RATIO:
        _die("GPT Image 2 / 2.5 size long edge to short edge ratio must not exceed 3:1.")
    if total_pixels < GPT_IMAGE_2_MIN_PIXELS or total_pixels > GPT_IMAGE_2_MAX_PIXELS:
        _die(
            "GPT Image 2 / 2.5 size total pixels must be at least 655,360 and no more than 8,294,400."
        )


def _validate_size(size: str, model: str) -> None:
    if _is_gpt_image_2_model(model) or _is_gpt_image_2_5_model(model):
        _validate_gpt_image_2_size(size)
        return

    if size not in ALLOWED_LEGACY_SIZES:
        _die(
            "size must be one of 1024x1024, 1536x1024, 1024x1536, or auto for this GPT Image model."
        )


def _validate_quality(quality: str, model: str) -> None:
    if quality not in ALLOWED_QUALITIES:
        _die("quality must be one of low, medium, high, xhigh, max, or auto.")
    if quality in {"xhigh", "max"} and not _is_gpt_image_2_5_model(model):
        _die("xhigh and max quality require gpt-image-2.5-flare or gpt-image-2.5-sunburst.")


def _validate_background(background: Optional[str]) -> None:
    if background not in ALLOWED_BACKGROUNDS:
        _die("background must be one of transparent, opaque, or auto.")


def _validate_input_fidelity(input_fidelity: Optional[str]) -> None:
    if input_fidelity not in ALLOWED_INPUT_FIDELITIES:
        _die("input-fidelity must be one of low or high.")


def _validate_model(model: str) -> None:
    if GPT_IMAGE_MODEL_PREFIX not in model:
        _die(
            "model must be a GPT Image model name containing 'gpt-image-' "
            "(for example gpt-image-2.5-flare, gpt-image-2.5-sunburst, gpt-image-2, "
            "gpt-image-1, or gpt-image-1-mini)."
        )


def _is_gpt_image_2_model(model: str) -> bool:
    return bool(re.search(r"(?:^|/)gpt-image-2(?:-\d{4}-\d{2}-\d{2})?(?:/|$)", model))


def _is_gpt_image_2_5_model(model: str) -> bool:
    return bool(re.search(
        r"(?:^|/)gpt-image-2\.5-(?:flare|sunburst)(?:-\d{4}-\d{2}-\d{2})?(?:/|$)",
        model,
    ))


def _validate_transparency(background: Optional[str], output_format: str) -> None:
    if background == "transparent" and output_format not in {"png", "webp"}:
        _die("transparent background requires output-format png or webp.")


def _validate_model_specific_options(
    *,
    model: str,
    background: Optional[str],
    input_fidelity: Optional[str] = None,
) -> None:
    if not _is_gpt_image_2_model(model):
        return
    if background == "transparent":
        _die(
            "transparent backgrounds are not supported in gpt-image-2. "
            "Use --model gpt-image-2.5-flare --background transparent --output-format png instead."
        )
    if input_fidelity is not None:
        _die(
            "input_fidelity is not supported in gpt-image-2 because image inputs always use high fidelity for this model."
        )


def _validate_generate_payload(payload: Dict[str, Any]) -> None:
    model = str(payload.get("model", DEFAULT_MODEL))
    _validate_model(model)
    n = int(payload.get("n", 1))
    if n < 1 or n > 10:
        _die("n must be between 1 and 10")
    size = str(payload.get("size", DEFAULT_SIZE))
    quality = str(payload.get("quality", DEFAULT_QUALITY))
    background = payload.get("background")
    _validate_size(size, model)
    _validate_quality(quality, model)
    _validate_background(background)
    _validate_model_specific_options(model=model, background=background)
    oc = payload.get("output_compression")
    if oc is not None and not (0 <= int(oc) <= 100):
        _die("output_compression must be between 0 and 100")


def _build_output_paths(
    out: str,
    output_format: str,
    count: int,
    out_dir: Optional[str],
) -> List[Path]:
    ext = "." + output_format

    if out_dir:
        out_base = Path(out_dir)
        out_base.mkdir(parents=True, exist_ok=True)
        return [out_base / f"image_{i}{ext}" for i in range(1, count + 1)]

    out_path = Path(out)
    if out_path.exists() and out_path.is_dir():
        out_path.mkdir(parents=True, exist_ok=True)
        return [out_path / f"image_{i}{ext}" for i in range(1, count + 1)]

    if out_path.suffix == "":
        out_path = out_path.with_suffix(ext)
    elif output_format and out_path.suffix.lstrip(".").lower() != output_format:
        _warn(
            f"Output extension {out_path.suffix} does not match output-format {output_format}."
        )

    if count == 1:
        return [out_path]

    return [
        out_path.with_name(f"{out_path.stem}-{i}{out_path.suffix}")
        for i in range(1, count + 1)
    ]


def _augment_prompt(args: argparse.Namespace, prompt: str) -> str:
    fields = _fields_from_args(args)
    return _augment_prompt_fields(args.augment, prompt, fields)


def _augment_prompt_fields(augment: bool, prompt: str, fields: Dict[str, Optional[str]]) -> str:
    if not augment:
        return prompt

    sections: List[str] = []
    if fields.get("use_case"):
        sections.append(f"Use case: {fields['use_case']}")
    sections.append(f"Primary request: {prompt}")
    if fields.get("scene"):
        sections.append(f"Scene/background: {fields['scene']}")
    if fields.get("subject"):
        sections.append(f"Subject: {fields['subject']}")
    if fields.get("style"):
        sections.append(f"Style/medium: {fields['style']}")
    if fields.get("composition"):
        sections.append(f"Composition/framing: {fields['composition']}")
    if fields.get("lighting"):
        sections.append(f"Lighting/mood: {fields['lighting']}")
    if fields.get("palette"):
        sections.append(f"Color palette: {fields['palette']}")
    if fields.get("materials"):
        sections.append(f"Materials/textures: {fields['materials']}")
    if fields.get("text"):
        sections.append(f"Text (verbatim): \"{fields['text']}\"")
    if fields.get("constraints"):
        sections.append(f"Constraints: {fields['constraints']}")
    if fields.get("negative"):
        sections.append(f"Avoid: {fields['negative']}")

    return "\n".join(sections)


def _fields_from_args(args: argparse.Namespace) -> Dict[str, Optional[str]]:
    return {
        "use_case": getattr(args, "use_case", None),
        "scene": getattr(args, "scene", None),
        "subject": getattr(args, "subject", None),
        "style": getattr(args, "style", None),
        "composition": getattr(args, "composition", None),
        "lighting": getattr(args, "lighting", None),
        "palette": getattr(args, "palette", None),
        "materials": getattr(args, "materials", None),
        "text": getattr(args, "text", None),
        "constraints": getattr(args, "constraints", None),
        "negative": getattr(args, "negative", None),
    }


def _print_request(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _decode_and_write(images: List[str], outputs: List[Path], force: bool) -> None:
    for idx, image_b64 in enumerate(images):
        if idx >= len(outputs):
            break
        out_path = outputs[idx]
        if out_path.exists() and not force:
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(image_b64))
        print(f"IMAGE_API: wrote={out_path}")


def _derive_downscale_path(path: Path, suffix: str) -> Path:
    if suffix and not suffix.startswith("-") and not suffix.startswith("_"):
        suffix = "-" + suffix
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def _downscale_image_bytes(image_bytes: bytes, *, max_dim: int, output_format: str) -> bytes:
    try:
        from PIL import Image
    except Exception:
        _die(f"Downscaling requires Pillow. {_dependency_hint('pillow')}")

    if max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    with Image.open(BytesIO(image_bytes)) as img:
        img.load()
        w, h = img.size
        scale = min(1.0, float(max_dim) / float(max(w, h)))
        target = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))

        resized = img if target == (w, h) else img.resize(target, Image.Resampling.LANCZOS)

        fmt = output_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"

        if fmt == "jpeg":
            if resized.mode in ("RGBA", "LA") or ("transparency" in getattr(resized, "info", {})):
                bg = Image.new("RGB", resized.size, (255, 255, 255))
                bg.paste(resized.convert("RGBA"), mask=resized.convert("RGBA").split()[-1])
                resized = bg
            else:
                resized = resized.convert("RGB")

        out = BytesIO()
        resized.save(out, format=fmt.upper())
        return out.getvalue()


def _decode_write_and_downscale(
    images: List[str],
    outputs: List[Path],
    *,
    force: bool,
    downscale_max_dim: Optional[int],
    downscale_suffix: str,
    output_format: str,
) -> None:
    for idx, image_b64 in enumerate(images):
        if idx >= len(outputs):
            break
        out_path = outputs[idx]
        if out_path.exists() and not force:
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        raw = base64.b64decode(image_b64)
        out_path.write_bytes(raw)
        print(f"IMAGE_API: wrote={out_path}")

        if downscale_max_dim is None:
            continue

        derived = _derive_downscale_path(out_path, downscale_suffix)
        if derived.exists() and not force:
            _die(f"Output already exists: {derived} (use --force to overwrite)")
        derived.parent.mkdir(parents=True, exist_ok=True)
        resized = _downscale_image_bytes(raw, max_dim=downscale_max_dim, output_format=output_format)
        derived.write_bytes(resized)
        print(f"IMAGE_API: wrote={derived}")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:60] if value else "job"


def _normalize_job(job: Any, idx: int) -> Dict[str, Any]:
    if isinstance(job, str):
        prompt = job.strip()
        if not prompt:
            _die(f"Empty prompt at job {idx}")
        return {"prompt": prompt}
    if isinstance(job, dict):
        if "prompt" not in job or not str(job["prompt"]).strip():
            _die(f"Missing prompt for job {idx}")
        return job
    _die(f"Invalid job at index {idx}: expected string or object.")
    return {}  # unreachable


def _read_jobs_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        _die(f"Input file not found: {p}")
    jobs: List[Dict[str, Any]] = []
    for line_no, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item: Any
            if line.startswith("{"):
                item = json.loads(line)
            else:
                item = line
            jobs.append(_normalize_job(item, idx=line_no))
        except json.JSONDecodeError as exc:
            _die(f"Invalid JSON on line {line_no}: {exc}")
    if not jobs:
        _die("No jobs found in input file.")
    if len(jobs) > MAX_BATCH_JOBS:
        _die(f"Too many jobs ({len(jobs)}). Max is {MAX_BATCH_JOBS}.")
    return jobs


def _merge_non_null(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(dst)
    for k, v in src.items():
        if v is not None:
            merged[k] = v
    return merged


def _job_output_paths(
    *,
    out_dir: Path,
    output_format: str,
    idx: int,
    prompt: str,
    n: int,
    explicit_out: Optional[str],
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "." + output_format

    if explicit_out:
        base = Path(explicit_out)
        if base.suffix == "":
            base = base.with_suffix(ext)
        elif base.suffix.lstrip(".").lower() != output_format:
            _warn(
                f"Job {idx}: output extension {base.suffix} does not match output-format {output_format}."
            )
        base = out_dir / base.name
    else:
        slug = _slugify(prompt[:80])
        base = out_dir / f"{idx:03d}-{slug}{ext}"

    if n == 1:
        return [base]
    return [
        base.with_name(f"{base.stem}-{i}{base.suffix}")
        for i in range(1, n + 1)
    ]


async def _run_generate_batch(args: argparse.Namespace) -> int:
    jobs = _read_jobs_jsonl(args.input)
    out_dir = Path(args.out_dir)

    base_fields = _fields_from_args(args)
    base_payload = {
        "model": args.model,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }

    if args.dry_run:
        for i, job in enumerate(jobs, start=1):
            prompt = str(job["prompt"]).strip()
            fields = _merge_non_null(base_fields, job.get("fields", {}))
            # Allow flat job keys as well (use_case, scene, etc.)
            fields = _merge_non_null(fields, {k: job.get(k) for k in base_fields.keys()})
            augmented = _augment_prompt_fields(args.augment, prompt, fields)

            job_payload = dict(base_payload)
            job_payload["prompt"] = augmented
            job_payload = _merge_non_null(job_payload, {k: job.get(k) for k in base_payload.keys()})
            job_payload = {k: v for k, v in job_payload.items() if v is not None}

            _validate_generate_payload(job_payload)
            effective_output_format = _normalize_output_format(job_payload.get("output_format"))
            _validate_transparency(job_payload.get("background"), effective_output_format)
            job_payload["output_format"] = effective_output_format

            n = int(job_payload.get("n", 1))
            outputs = _job_output_paths(
                out_dir=out_dir,
                output_format=effective_output_format,
                idx=i,
                prompt=prompt,
                n=n,
                explicit_out=job.get("out"),
            )
            downscaled = None
            if args.downscale_max_dim is not None:
                downscaled = [
                    str(_derive_downscale_path(p, args.downscale_suffix)) for p in outputs
                ]
            _print_request(
                {
                    "endpoint": _preview_endpoint("generate"),
                    "job": i,
                    "outputs": [str(p) for p in outputs],
                    "outputs_downscaled": downscaled,
                    **{
                        **job_payload,
                        "model": _preview_model(str(job_payload["model"]), "generate"),
                    },
                }
            )
        return 0

    provider = create_image_provider(api_key=_api_key(), base_url=_api_base_url())
    sem = asyncio.Semaphore(args.concurrency)

    any_failed = False

    async def run_job(i: int, job: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        nonlocal any_failed
        prompt = str(job["prompt"]).strip()
        job_label = f"[job {i}/{len(jobs)}]"

        fields = _merge_non_null(base_fields, job.get("fields", {}))
        fields = _merge_non_null(fields, {k: job.get(k) for k in base_fields.keys()})
        augmented = _augment_prompt_fields(args.augment, prompt, fields)

        payload = dict(base_payload)
        payload["prompt"] = augmented
        payload = _merge_non_null(payload, {k: job.get(k) for k in base_payload.keys()})
        payload = {k: v for k, v in payload.items() if v is not None}

        n = int(payload.get("n", 1))
        _validate_generate_payload(payload)
        effective_output_format = _normalize_output_format(payload.get("output_format"))
        _validate_transparency(payload.get("background"), effective_output_format)
        payload["output_format"] = effective_output_format
        outputs = _job_output_paths(
            out_dir=out_dir,
            output_format=effective_output_format,
            idx=i,
            prompt=prompt,
            n=n,
            explicit_out=job.get("out"),
        )
        try:
            async with sem:
                print(f"{job_label} starting", file=sys.stderr)
                started = time.time()
                images = await provider.generate_batch(
                    payload,
                    attempts=args.max_attempts,
                    job_label=job_label,
                )
                elapsed = time.time() - started
                print(f"{job_label} completed in {elapsed:.1f}s", file=sys.stderr)
            _decode_write_and_downscale(
                images,
                outputs,
                force=args.force,
                downscale_max_dim=args.downscale_max_dim,
                downscale_suffix=args.downscale_suffix,
                output_format=effective_output_format,
            )
            return i, None
        except Exception as exc:
            any_failed = True
            print(f"{job_label} failed: {exc}", file=sys.stderr)
            if args.fail_fast:
                raise
            return i, str(exc)

    tasks = [asyncio.create_task(run_job(i, job)) for i, job in enumerate(jobs, start=1)]

    try:
        await asyncio.gather(*tasks)
    except Exception:
        for t in tasks:
            if not t.done():
                t.cancel()
        raise

    return 1 if any_failed else 0


def _generate_batch(args: argparse.Namespace) -> None:
    exit_code = asyncio.run(_run_generate_batch(args))
    if exit_code:
        raise SystemExit(exit_code)


def _generate(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        _print_request(
            {
                "endpoint": _preview_endpoint("generate"),
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **{
                    **payload,
                    "model": _preview_model(str(payload["model"]), "generate"),
                },
            }
        )
        return

    print(
        "Calling Image API (generation). This can take up to a couple of minutes.",
        file=sys.stderr,
    )
    started = time.time()
    provider = create_image_provider(api_key=_api_key(), base_url=_api_base_url())
    images = provider.generate(payload)
    elapsed = time.time() - started
    print(f"Generation completed in {elapsed:.1f}s.", file=sys.stderr)

    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
    )


def _edit(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    image_paths = _check_image_paths(args.image)
    mask_path = Path(args.mask) if args.mask else None
    if mask_path:
        if not mask_path.exists():
            _die(f"Mask file not found: {mask_path}")
        if mask_path.suffix.lower() != ".png":
            _warn(f"Mask should be a PNG with an alpha channel: {mask_path}")
        if mask_path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Mask exceeds 50MB limit: {mask_path}")

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "input_fidelity": args.input_fidelity,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    _validate_input_fidelity(args.input_fidelity)
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        payload_preview = dict(payload)
        payload_preview["image"] = [str(p) for p in image_paths]
        if mask_path:
            payload_preview["mask"] = str(mask_path)
        _print_request(
            {
                "endpoint": _preview_endpoint("edit"),
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **{
                    **payload_preview,
                    "model": _preview_model(str(payload_preview["model"]), "edit"),
                },
            }
        )
        return

    print(
        f"Calling Image API (edit) with {len(image_paths)} image(s).",
        file=sys.stderr,
    )
    started = time.time()
    provider = create_image_provider(api_key=_api_key(), base_url=_api_base_url())
    images = provider.edit(payload, image_paths, mask_path)

    elapsed = time.time() - started
    print(f"Edit completed in {elapsed:.1f}s.", file=sys.stderr)
    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
    )



def _load_job(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        _die(f"Job file not found: {p}")
    try:
        job = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _die(f"Invalid job JSON {p}: {exc}")
    if not isinstance(job, dict) or not str(job.get("prompt", "")).strip():
        _die(f"Job {p} has no prompt.")
    if not job.get("out"):
        _die(f"Job {p} has no out path.")
    return job


def _job(args: argparse.Namespace) -> None:
    """Run one ``figure_jobs.py`` job: edit when it has input images, else generate."""
    job = _load_job(args.job)
    images = [str(item["path"] if isinstance(item, dict) else item) for item in job.get("input_images") or []]
    args.prompt = str(job["prompt"]).strip()
    args.prompt_file = None
    args.augment = False
    args.size = str(job.get("size") or args.size)
    args.quality = str(job.get("quality") or args.quality)
    args.background = job.get("background", args.background)
    args.output_format = job.get("output_format", args.output_format)
    args.out = str(job["out"])
    args.out_dir = None
    args.n = 1
    _validate_size(args.size, args.model)
    _validate_quality(args.quality, args.model)
    _validate_background(args.background)
    _validate_model_specific_options(model=args.model, background=args.background)
    print(
        f"IMAGE_API: job={job.get('fig_id', args.job)} op={'edit' if images else 'generate'} out={args.out}",
        file=sys.stderr,
    )
    if images:
        args.image = images
        args.mask = None
        args.input_fidelity = job.get("input_fidelity")
        _edit(args)
    else:
        _generate(args)


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=_default_model())
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--background")
    parser.add_argument("--output-format")
    parser.add_argument("--output-compression", type=int)
    parser.add_argument("--moderation")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--out-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--augment", dest="augment", action="store_true")
    parser.add_argument("--no-augment", dest="augment", action="store_false")
    parser.set_defaults(augment=True)

    # Prompt augmentation hints
    parser.add_argument("--use-case")
    parser.add_argument("--scene")
    parser.add_argument("--subject")
    parser.add_argument("--style")
    parser.add_argument("--composition")
    parser.add_argument("--lighting")
    parser.add_argument("--palette")
    parser.add_argument("--materials")
    parser.add_argument("--text")
    parser.add_argument("--constraints")
    parser.add_argument("--negative")

    # Post-processing (optional): generate an additional downscaled copy for fast web loading.
    parser.add_argument("--downscale-max-dim", type=int)
    parser.add_argument("--downscale-suffix", default=DEFAULT_DOWNSCALE_SUFFIX)


def main() -> int:
    ensure_utf8_stdio()
    _load_runtime_env()
    parser = argparse.ArgumentParser(
        description="专利附图 CLI 出图后端（GPT Image 文生图 / 图生图）"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_parser = subparsers.add_parser("generate", help="Create a new image")
    _add_shared_args(gen_parser)
    gen_parser.set_defaults(func=_generate)

    batch_parser = subparsers.add_parser(
        "generate-batch",
        help="Generate multiple prompts concurrently (JSONL input)",
    )
    _add_shared_args(batch_parser)
    batch_parser.add_argument("--input", required=True, help="Path to JSONL file (one job per line)")
    batch_parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    batch_parser.add_argument("--max-attempts", type=int, default=3)
    batch_parser.add_argument("--fail-fast", action="store_true")
    batch_parser.set_defaults(func=_generate_batch)

    edit_parser = subparsers.add_parser("edit", help="Edit an existing image")
    _add_shared_args(edit_parser)
    edit_parser.add_argument("--image", action="append", required=True)
    edit_parser.add_argument("--mask")
    edit_parser.add_argument("--input-fidelity")
    edit_parser.set_defaults(func=_edit)

    job_parser = subparsers.add_parser(
        "job",
        help="Run one figure job JSON (figure_jobs.py prepare); edit if input_images else generate",
    )
    _add_shared_args(job_parser)
    job_parser.add_argument("--job", required=True, help="figure_jobs/fig_XX.json")
    job_parser.set_defaults(func=_job)

    args = parser.parse_args()
    if args.n < 1 or args.n > 10:
        _die("--n must be between 1 and 10")
    if getattr(args, "concurrency", 1) < 1 or getattr(args, "concurrency", 1) > 25:
        _die("--concurrency must be between 1 and 25")
    if getattr(args, "max_attempts", 3) < 1 or getattr(args, "max_attempts", 3) > 10:
        _die("--max-attempts must be between 1 and 10")
    if args.output_compression is not None and not (0 <= args.output_compression <= 100):
        _die("--output-compression must be between 0 and 100")
    if args.command == "generate-batch" and not args.out_dir:
        _die("generate-batch requires --out-dir")
    if getattr(args, "downscale_max_dim", None) is not None and args.downscale_max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    _validate_model(args.model)
    _validate_size(args.size, args.model)
    _validate_quality(args.quality, args.model)
    _validate_background(args.background)
    _validate_model_specific_options(
        model=args.model,
        background=args.background,
        input_fidelity=getattr(args, "input_fidelity", None),
    )
    _ensure_api_key(args.dry_run)

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
