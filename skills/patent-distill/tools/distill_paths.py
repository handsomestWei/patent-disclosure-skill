# -*- coding: utf-8 -*-
"""档案目录：工作区 outputs/patent-distill/{profile_id}/。"""
from __future__ import annotations

import os
import re
from pathlib import Path

ENV_OUTPUT_DIR = "PATENT_DISTILL_OUTPUT_DIR"
_BAD = re.compile(r'[\\/:*?"<>|\s]')


def normalize_profile_id(value: str) -> str:
    text = (value or "").strip()
    if not text or text in {".", ".."} or _BAD.search(text) or len(text) > 80:
        raise ValueError("profile_id 不能为空、不能含空格或路径符号，最长 80")
    return text


def default_output_root(start: Path | None = None) -> Path:
    env = (os.environ.get(ENV_OUTPUT_DIR) or "").strip()
    if env:
        return Path(env)
    here = (start or Path(__file__).resolve()).resolve()
    cursor = here if here.is_dir() else here.parent
    for parent in [cursor, *cursor.parents]:
        if (parent / ".git").exists() or (parent / "outputs").is_dir():
            return parent / "outputs" / "patent-distill"
    return Path.cwd() / "outputs" / "patent-distill"


def profile_dir_for(profile_id: str, *, root: Path | None = None) -> Path:
    return (root or default_output_root()) / normalize_profile_id(profile_id)
