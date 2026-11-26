# -*- coding: utf-8 -*-
"""读取 references/contract.yaml。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONTRACT = Path(__file__).resolve().parents[1] / "references" / "contract.yaml"


@lru_cache(maxsize=1)
def load_contract() -> dict[str, Any]:
    data = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("contract.yaml 须为对象")
    return data


def choice(name: str) -> set[str]:
    raw = load_contract()[name]
    if not isinstance(raw, list):
        raise ValueError(f"contract.{name} 须为列表")
    return {str(item) for item in raw}
