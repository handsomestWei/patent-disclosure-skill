#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专利附图 CLI 出图后端的运行时配置与自检。

只管本技能自己的配置目录 ``${PATENT_SKILL_HOME:-~/.patent-skill}``：

  python tools/image_runtime.py config --api-key "sk-..." [--base-url URL] [--model gpt-image-2.5-flare]
  python tools/image_runtime.py doctor [--check-api]

``.env`` 只写 PATENT_SKILL_IMAGE_API_KEY / PATENT_SKILL_IMAGE_BASE_URL /
PATENT_SKILL_IMAGE_MODEL，权限 0600；输出中 key 打码。依赖装在当前解释器
（``requirements-image.txt``），不另建 venv。stdout 前缀 ``IMAGE_RUNTIME:``。

Adapted from ningzimu/codex-ppt-skill ``scripts/codex_ppt_runtime.py`` (MIT License).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from typing import Dict, Iterable, Optional
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_RUNTIME_HOME = "~/.patent-skill"
DEFAULT_MODEL = "gpt-image-2.5-flare"
HOME_ENV = "PATENT_SKILL_HOME"
API_KEY_ENV = "PATENT_SKILL_IMAGE_API_KEY"
BASE_URL_ENV = "PATENT_SKILL_IMAGE_BASE_URL"
MODEL_ENV = "PATENT_SKILL_IMAGE_MODEL"
ENV_FIELDS = (API_KEY_ENV, BASE_URL_ENV, MODEL_ENV)
PREFIX = "IMAGE_RUNTIME:"


def runtime_home() -> Path:
    return Path(os.getenv(HOME_ENV, DEFAULT_RUNTIME_HOME)).expanduser()


def env_path(home: Optional[Path] = None) -> Path:
    return (home or runtime_home()) / ".env"


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _quote_env_value(value: str) -> str:
    if any(ch.isspace() for ch in value) or "#" in value or '"' in value:
        return json.dumps(value)
    return value


def write_env_file(path: Path, values: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# patent-disclosure-skill 图像后端配置（image_runtime.py config 写入）"]
    for key in ENV_FIELDS:
        value = values.get(key, "")
        if value:
            lines.append(f"{key}={_quote_env_value(value)}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def load_env_values(home: Optional[Path] = None) -> Dict[str, str]:
    """``.env`` values overlaid with process environment (process wins)."""
    values = parse_env_file(env_path(home))
    for key in ENV_FIELDS:
        if os.getenv(key):
            values[key] = os.environ[key]
    return values


def deps_ok() -> bool:
    return importlib.util.find_spec("openai") is not None


def _config(args: argparse.Namespace) -> int:
    path = env_path()
    values = parse_env_file(path)
    if args.api_key:
        values[API_KEY_ENV] = args.api_key.strip()
    if args.base_url is not None:
        values[BASE_URL_ENV] = args.base_url.strip()
    if args.clear_base_url:
        values.pop(BASE_URL_ENV, None)
    if args.model is not None:
        values[MODEL_ENV] = args.model.strip()
    write_env_file(path, values)
    print(f"{PREFIX} wrote={path}")
    for key in ENV_FIELDS:
        value = values.get(key, "")
        if key == API_KEY_ENV:
            value = mask_secret(value)
        print(f"{PREFIX} {key}={value or '<unset>'}")
    return 0


def _models_request(base_url: str, api_key: str, timeout: int) -> bool:
    endpoint = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            print(f"{PREFIX} models_endpoint=HTTP{resp.status}")
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        print(f"{PREFIX} models_endpoint=HTTP{exc.code}")
        body = exc.read(800).decode("utf-8", "replace")
        if body:
            print(body)
        return False
    except Exception as exc:  # noqa: BLE001 - doctor reports any network failure
        print(f"{PREFIX} models_endpoint={exc.__class__.__name__}: {exc}")
        return False


def _is_atlascloud(base_url: str) -> bool:
    return "atlascloud.ai" in (urllib.parse.urlparse(base_url).hostname or "").lower()


def _doctor(args: argparse.Namespace) -> int:
    home = runtime_home()
    print(f"{PREFIX} home={home}")
    print(f"{PREFIX} env_file={env_path(home)} exists={int(env_path(home).exists())}")
    ok = deps_ok()
    print(f"{PREFIX} deps={'ok' if ok else 'missing (pip install -r tools/requirements-image.txt)'}")

    values = load_env_values(home)
    api_key = values.get(API_KEY_ENV, "")
    base_url = values.get(BASE_URL_ENV, "") or "https://api.openai.com/v1"
    model = values.get(MODEL_ENV, "") or DEFAULT_MODEL
    print(f"{PREFIX} {API_KEY_ENV}={'set (' + mask_secret(api_key) + ')' if api_key else '<unset>'}")
    print(f"{PREFIX} {BASE_URL_ENV}={base_url}")
    print(f"{PREFIX} {MODEL_ENV}={model}")
    if "gpt-image-" not in model:
        print(f"{PREFIX} model_check=warn (model should contain 'gpt-image-')")
        ok = False
    if not api_key:
        ok = False
    if args.check_api:
        if not api_key:
            print(f"{PREFIX} api_check=skipped ({API_KEY_ENV} unset)")
        elif _is_atlascloud(base_url):
            print(f"{PREFIX} api_check=skipped (AtlasCloud has no /models probe)")
        else:
            ok = _models_request(base_url, api_key, args.timeout) and ok
    print(f"{PREFIX} ok={int(ok)}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="专利附图 CLI 出图后端：配置与自检")
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("config", help="写入或更新 ~/.patent-skill/.env")
    config.add_argument("--api-key")
    config.add_argument("--base-url")
    config.add_argument("--clear-base-url", action="store_true")
    config.add_argument("--model")
    config.set_defaults(func=_config)
    doctor = sub.add_parser("doctor", help="检查依赖、配置与可选 API 连通")
    doctor.add_argument("--check-api", action="store_true")
    doctor.add_argument("--timeout", type=int, default=30)
    doctor.set_defaults(func=_doctor)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from stdio_utf8 import ensure_utf8_stdio

    ensure_utf8_stdio()
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
