"""离线规则：领域路由（patent_domain_rules.yaml）与 IPC 行业提示（ipc_application_hints.yaml）。"""
from __future__ import annotations

import yaml

from .paths import ROOT


def _str_list(raw) -> list[str]:
    return [str(x).strip() for x in raw or [] if str(x).strip()]


def load_domain_rules() -> list[dict]:
    path = ROOT / "references" / "patent_domain_rules.yaml"
    if not path.is_file():
        return [{"label": "未分类", "ipc_prefixes": [], "keywords": []}]
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    domains = [
        {
            "label": str(d.get("label") or "").strip(),
            "ipc_prefixes": _str_list(d.get("ipc_prefixes")),
            "keywords": _str_list(d.get("keywords")),
        }
        for d in data.get("domains") or []
        if isinstance(d, dict)
    ]
    return domains or [{"label": "未分类", "ipc_prefixes": [], "keywords": []}]


def resolve_domain(text: str, ipc: str = "") -> str:
    low = (text or "").lower()
    ipc = (ipc or "").upper()
    for dom in load_domain_rules():
        label = dom.get("label") or "未分类"
        for prefix in dom.get("ipc_prefixes") or []:
            if ipc.startswith(prefix.upper()):
                return label
        for kw in dom.get("keywords") or []:
            if kw.lower() in low:
                return label
    return "未分类"


def load_ipc_application_hints() -> list[dict]:
    path = ROOT / "references" / "ipc_application_hints.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        {
            "ipc_prefix": str(h.get("ipc_prefix") or "").strip(),
            "keywords": _str_list(h.get("keywords")),
            "industry": str(h.get("industry") or "").strip(),
            "typical_modules": _str_list(h.get("typical_modules")),
            "user_scenarios": _str_list(h.get("user_scenarios")),
            "search_hints": _str_list(h.get("search_hints")),
        }
        for h in data.get("hints") or []
        if isinstance(h, dict)
    ]


def resolve_ipc_hints(text: str, ipc_codes: list[str] | None = None) -> dict:
    """按 IPC 前缀或关键词匹配离线应用场景提示。"""
    hints = load_ipc_application_hints()
    ipc_codes = [c.upper() for c in (ipc_codes or [])]
    low = (text or "").lower()

    for hint in hints:
        prefix = (hint.get("ipc_prefix") or "").upper()
        if prefix and prefix != "DEFAULT":
            for code in ipc_codes:
                if code.startswith(prefix):
                    return {**hint, "matched_by": f"ipc:{code}"}

    for hint in hints:
        if hint.get("ipc_prefix") == "DEFAULT":
            continue
        for kw in hint.get("keywords") or []:
            if kw.lower() in low:
                return {**hint, "matched_by": f"keyword:{kw}"}

    for hint in hints:
        if hint.get("ipc_prefix") == "DEFAULT":
            return {**hint, "matched_by": "default"}
    return {
        "ipc_prefix": "DEFAULT",
        "industry": "通用技术",
        "typical_modules": ["按权利要求中的功能模块理解"],
        "user_scenarios": ["结合说明书实施例与背景技术推断"],
        "search_hints": ["技术 解决方案"],
        "matched_by": "fallback",
    }
