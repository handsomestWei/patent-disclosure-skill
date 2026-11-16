#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专利附图出图后端：探测、确认与记录（案件级 ``figure_backend.json``）。

后端三选一，确认后本案固定不变（迭代不再重复询问）：

- ``builtin``：宿主内置生图工具（例如 Codex ``image_gen``、OpenClaw ``image_generate``）。
  脚本无法探测宿主工具，由 Agent 自查后 ``--set builtin``。
- ``cli``：``image_api.py``（GPT Image；配置见 ``image_runtime.py``）。
- ``local``：上游原有本地渲染（mermaid / 手写 SVG / overlay），行为与未引入本功能时一致。

环境开关 ``PATENT_SKILL_FIGURE_BACKEND=auto|builtin|cli|local``，默认 ``auto``。

  python tools/figure_backend.py --case-dir outputs/case
  python tools/figure_backend.py --case-dir outputs/case --set cli --confirmed
  python tools/figure_backend.py --case-dir outputs/case --sample figure_jobs_out/fig_01.png --sample-fig fig_01 --accept

stdout 为 JSON；stderr 摘要前缀 ``FIGURE_BACKEND:``。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import image_runtime  # noqa: E402
from stdio_utf8 import ensure_utf8_stdio  # noqa: E402

SWITCH_ENV = "PATENT_SKILL_FIGURE_BACKEND"
SWITCH_VALUES = ("auto", "builtin", "cli", "local")
BACKENDS = ("builtin", "cli", "local")
STATE_FILE = "figure_backend.json"
PREFIX = "FIGURE_BACKEND:"


def switch_value() -> str:
    raw = os.environ.get(SWITCH_ENV, "").strip().lower()
    return raw if raw in SWITCH_VALUES else "auto"


def state_path(case_dir: Path) -> Path:
    return case_dir / STATE_FILE


def load_state(case_dir: Path) -> dict[str, Any]:
    path = state_path(case_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(case_dir: Path, state: dict[str, Any]) -> Path:
    case_dir.mkdir(parents=True, exist_ok=True)
    path = state_path(case_dir)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def cli_status() -> tuple[bool, str]:
    """CLI backend is usable when the openai SDK imports and an API key is configured."""
    if not image_runtime.deps_ok():
        return False, "deps_missing"
    values = image_runtime.load_env_values()
    if not values.get(image_runtime.API_KEY_ENV):
        return False, "api_key_unset"
    return True, "ready"


def confirmed_backend(case_dir: Path) -> str | None:
    """Backend fixed for this case, or ``None`` before confirmation.

    ``PATENT_SKILL_FIGURE_BACKEND=local`` always wins so users can force upstream behaviour.
    """
    if switch_value() == "local":
        return "local"
    state = load_state(case_dir)
    backend = state.get("backend")
    if state.get("confirmed") and backend in BACKENDS:
        return str(backend)
    return None


def probe(case_dir: Path) -> dict[str, Any]:
    switch = switch_value()
    state = load_state(case_dir)
    ready, reason = cli_status()
    fixed = confirmed_backend(case_dir)
    if fixed:
        candidates = [fixed]
    elif switch in ("builtin", "cli"):
        candidates = [switch, "local"]
    else:
        candidates = ["builtin", "cli", "local"] if ready else ["builtin", "local"]
    model = image_runtime.load_env_values().get(image_runtime.MODEL_ENV) or image_runtime.DEFAULT_MODEL
    return {
        "case_dir": str(case_dir),
        "switch": switch,
        "backend": fixed,
        "ask_user": fixed is None,
        "candidates": candidates,
        "cli_ready": ready,
        "cli_reason": reason,
        "cli_model": model,
        "sample": state.get("sample"),
        "state_file": str(state_path(case_dir)),
        "hint": (
            "已确认，直接按该后端出图" if fixed else
            "先自查宿主是否可调内置生图工具；向用户说明查了什么、准备用哪个后端、为何需要或不需要 CLI，"
            "确认后 --set <backend> --confirmed"
        ),
    }


def set_backend(case_dir: Path, backend: str, *, confirmed: bool, tool_hint: str | None, model: str | None) -> dict[str, Any]:
    state = load_state(case_dir)
    state.update(
        {
            "backend": backend,
            "confirmed": bool(confirmed),
            "confirmed_at": datetime.now().isoformat(timespec="seconds") if confirmed else None,
        }
    )
    if tool_hint:
        state["tool_hint"] = tool_hint
    if backend == "cli":
        state["model"] = model or image_runtime.load_env_values().get(image_runtime.MODEL_ENV) or image_runtime.DEFAULT_MODEL
    elif model:
        state["model"] = model
    save_state(case_dir, state)
    return state


def record_sample(case_dir: Path, path: str, fig_id: str | None, accepted: bool) -> dict[str, Any]:
    state = load_state(case_dir)
    state["sample"] = {
        "fig_id": fig_id,
        "path": path,
        "accepted": bool(accepted),
        "backend": state.get("backend"),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(case_dir, state)
    return state


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="专利附图出图后端：探测 / 确认 / 记录样图")
    ap.add_argument("--case-dir", required=True, type=Path)
    ap.add_argument("--set", dest="set_backend", choices=BACKENDS)
    ap.add_argument("--confirmed", action="store_true", help="用户已确认该后端")
    ap.add_argument("--tool-hint", help="内置工具名，仅作记录，例如 image_gen")
    ap.add_argument("--model")
    ap.add_argument("--sample", help="样图路径")
    ap.add_argument("--sample-fig", help="样图对应 fig_id")
    ap.add_argument("--accept", action="store_true", help="用户已认可样图")
    args = ap.parse_args(argv)

    case_dir = args.case_dir
    if args.set_backend == "cli" and not cli_status()[0]:
        print(f"{PREFIX} WARN cli 尚未就绪（{cli_status()[1]}）；先 image_runtime.py config / 安装 requirements-image.txt", file=sys.stderr)
    if args.set_backend:
        set_backend(case_dir, args.set_backend, confirmed=args.confirmed, tool_hint=args.tool_hint, model=args.model)
    if args.sample:
        record_sample(case_dir, args.sample, args.sample_fig, args.accept)
    result = probe(case_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sample = result.get("sample") or {}
    print(
        f"{PREFIX} backend={result['backend'] or 'unconfirmed'} switch={result['switch']} "
        f"cli_ready={int(result['cli_ready'])} sample_accepted={int(bool(sample.get('accepted')))}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
