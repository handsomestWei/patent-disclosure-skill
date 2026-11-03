"""解读包根路径与通用小工具（命令行路径参数、公开号 / 术语文件名）。"""
from __future__ import annotations

import re
from pathlib import Path


def _package_root() -> Path:
    # tools/shared/paths.py → patent-reader/
    return Path(__file__).resolve().parents[2]


ROOT = _package_root()


def optional_path(value: str | None) -> Path | None:
    """argparse 用：空字符串 → None，避免 default='' + type=Path 变成 Path('.')."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return Path(s)


def slugify_term(term: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", term.strip(), flags=re.UNICODE)
    return s.strip("_")[:60] or "term"


def slugify_pub(pub: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", pub.strip(), flags=re.UNICODE)
    return s.strip("_") or "patent"
