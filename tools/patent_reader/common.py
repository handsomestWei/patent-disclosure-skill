"""专利解读工具共享配置与路径解析。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DEP_PATTERNS = (
    "根据权利要求",
    "如权利要求",
    "按照权利要求",
    "按权利要求",
    "依据权利要求",
    "according to claim",
    "of claim",
)


def optional_path(value: str | None) -> Path | None:
    """argparse 用：空字符串 → None，避免 default='' + type=Path 变成 Path('.')."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return Path(s)


def persisted_vault_config_path() -> Path:
    """用户级持久化：Obsidian 库路径（不强制依赖系统环境变量）。"""
    home = Path.home()
    return home / ".patent-disclosure-skill" / "obsidian_vault.txt"


def read_persisted_vault() -> str:
    path = persisted_vault_config_path()
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip().strip('"').strip("'")
    except OSError:
        return ""


def write_persisted_vault(vault: str | Path) -> Path:
    path = persisted_vault_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(Path(vault).expanduser().resolve())
    path.write_text(resolved + "\n", encoding="utf-8")
    return path


def _looks_like_vault(path: Path) -> bool:
    if not path.is_dir():
        return False
    # 已打开过的库通常有 .obsidian；新建空目录也允许用户指定
    if (path / ".obsidian").is_dir():
        return True
    # 常见：目录存在且非系统盘根
    return path.exists() and path.name not in ("", "/", "\\")


def _obsidian_appdata_dirs() -> list[Path]:
    dirs: list[Path] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if appdata:
            dirs.append(Path(appdata) / "obsidian")
        if local:
            dirs.append(Path(local) / "Obsidian")
    elif sys.platform == "darwin":
        home = Path.home()
        dirs.append(home / "Library" / "Application Support" / "obsidian")
    else:
        home = Path.home()
        dirs.append(home / ".config" / "obsidian")
    return dirs


def detect_obsidian_installed() -> dict:
    """探测本机是否安装 / 使用过 Obsidian。"""
    evidence: list[str] = []
    installed = False

    for d in _obsidian_appdata_dirs():
        cfg = d / "obsidian.json"
        if cfg.is_file():
            installed = True
            evidence.append(str(cfg))
        if d.is_dir():
            try:
                if any(d.iterdir()):
                    installed = True
                    evidence.append(str(d))
            except OSError:
                pass

    if sys.platform == "win32":
        for cand in (
            Path(os.environ.get("LOCALAPPDATA", "")) / "Obsidian" / "Obsidian.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Obsidian" / "Obsidian.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Obsidian"
            / "Obsidian.exe",
        ):
            if cand.is_file():
                installed = True
                evidence.append(str(cand))
    elif sys.platform == "darwin":
        app = Path("/Applications/Obsidian.app")
        if app.is_dir():
            installed = True
            evidence.append(str(app))
    else:
        # Linux：桌面入口或 PATH
        for name in ("obsidian", "Obsidian"):
            for p in os.environ.get("PATH", "").split(os.pathsep):
                exe = Path(p) / name
                if exe.is_file():
                    installed = True
                    evidence.append(str(exe))
                    break

    return {
        "installed": installed,
        "evidence": list(dict.fromkeys(evidence)),
    }


def _parse_obsidian_json_vaults(cfg_path: Path) -> list[dict]:
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    vaults_raw = data.get("vaults") or {}
    out: list[dict] = []
    if isinstance(vaults_raw, dict):
        for vid, meta in vaults_raw.items():
            if not isinstance(meta, dict):
                continue
            p = (meta.get("path") or "").strip()
            if not p:
                continue
            path = Path(p)
            out.append(
                {
                    "id": str(vid),
                    "path": str(path),
                    "exists": path.is_dir(),
                    "open": bool(meta.get("open")),
                    "ts": meta.get("ts") or 0,
                    "source": "obsidian.json",
                }
            )
    out.sort(key=lambda v: (not v.get("open"), -(v.get("ts") or 0)))
    return out


def candidate_default_vault_paths() -> list[Path]:
    """常见默认库路径（含用户举例的 Documents\\Obsidian Vault）。"""
    home = Path.home()
    docs = home / "Documents"
    # Windows 可能用「文档」
    docs_zh = home / "文档"
    cands = [
        docs / "Obsidian Vault",
        docs_zh / "Obsidian Vault",
        home / "Obsidian" / "Vault",
        home / "ObsidianVault",
        home / "obsidian",
        docs / "Obsidian",
        docs_zh / "Obsidian",
    ]
    return cands


def detect_obsidian_vaults() -> list[dict]:
    """汇总：obsidian.json 登记库 + 常见默认路径中已存在的目录。"""
    found: list[dict] = []
    seen: set[str] = set()

    for d in _obsidian_appdata_dirs():
        cfg = d / "obsidian.json"
        if cfg.is_file():
            for v in _parse_obsidian_json_vaults(cfg):
                key = v["path"].lower()
                if key in seen:
                    continue
                seen.add(key)
                found.append(v)

    for p in candidate_default_vault_paths():
        key = str(p).lower()
        if key in seen:
            continue
        if p.is_dir() and ((p / ".obsidian").is_dir() or any(p.iterdir())):
            seen.add(key)
            found.append(
                {
                    "id": "",
                    "path": str(p.resolve()),
                    "exists": True,
                    "open": False,
                    "ts": 0,
                    "source": "common_path",
                }
            )
    return found


def resolve_obsidian_vault(
    *,
    prefer_env: bool = True,
    prefer_persisted: bool = True,
    prefer_detect: bool = True,
) -> dict:
    """
    解析入库用库路径（不强制 Obsidian）。

    优先级：环境变量 → 持久化文件 → 自动探测（open 库 / 唯一库 / 常见默认路径）

    若环境变量键存在但值为空，视为「本会话不要 Obsidian」（不回退到自动探测）。
    """
    if prefer_env:
        for key in (
            "PATENT_READER_OBSIDIAN_VAULT",
            "PATENT_DISCLOSURE_OBSIDIAN_VAULT",
        ):
            if key not in os.environ:
                continue
            env_vault = os.environ.get(key, "").strip()
            if not env_vault:
                return {
                    "vault": "",
                    "source": "env_disabled",
                    "exists": False,
                    "needs_user_input": False,
                    "message": "环境变量已清空：本会话不使用 Obsidian 库，写入 outputs/。",
                }
            p = Path(env_vault).expanduser()
            return {
                "vault": str(p.resolve()) if p.exists() else str(p),
                "source": "env",
                "exists": p.is_dir(),
                "needs_user_input": False,
            }

    if prefer_persisted:
        persisted = read_persisted_vault()
        if persisted:
            p = Path(persisted).expanduser()
            return {
                "vault": str(p.resolve()) if p.exists() else str(p),
                "source": "persisted",
                "exists": p.is_dir(),
                "needs_user_input": False,
            }

    install = detect_obsidian_installed()
    vaults = detect_obsidian_vaults() if prefer_detect else []
    existing = [v for v in vaults if v.get("exists")]

    chosen = None
    reason = ""
    if prefer_detect and existing:
        open_ones = [v for v in existing if v.get("open")]
        if len(open_ones) == 1:
            chosen = open_ones[0]
            reason = "obsidian_open_vault"
        elif len(existing) == 1:
            chosen = existing[0]
            reason = "single_vault"
        elif open_ones:
            chosen = open_ones[0]
            reason = "obsidian_open_vault_first"
        else:
            return {
                "vault": "",
                "source": "",
                "exists": False,
                "needs_user_input": True,
                "obsidian_installed": install["installed"],
                "candidates": existing,
                "message": "检测到多个 Obsidian 库，请指定要用的库路径。",
            }

    if chosen:
        return {
            "vault": chosen["path"],
            "source": reason,
            "exists": True,
            "needs_user_input": False,
            "obsidian_installed": install["installed"],
            "candidates": existing,
        }

    return {
        "vault": "",
        "source": "",
        "exists": False,
        "needs_user_input": True,
        "obsidian_installed": install["installed"],
        "candidates": existing,
        "suggested_defaults": [str(p) for p in candidate_default_vault_paths()[:3]],
        "message": (
            "未检测到可用的 Obsidian 库路径。解读仍可写入 outputs/；"
            "若希望入库（索引/Canvas/术语网），请提供库根目录。"
        ),
    }


def probe_obsidian_environment() -> dict:
    """阅读模式对话开始前调用：完整探测报告。"""
    install = detect_obsidian_installed()
    vaults = detect_obsidian_vaults()
    resolved = resolve_obsidian_vault()
    status = "ready" if resolved.get("vault") and not resolved.get("needs_user_input") else "need_vault_path"
    if not install["installed"] and not resolved.get("vault"):
        status = "obsidian_optional_missing"

    return {
        "status": status,
        "obsidian_required": False,
        "obsidian_installed": install["installed"],
        "install_evidence": install["evidence"],
        "vaults": vaults,
        "resolved": resolved,
        "env_var": "PATENT_READER_OBSIDIAN_VAULT",
        "persisted_config": str(persisted_vault_config_path()),
        "hint_powershell": (
            '$env:PATENT_READER_OBSIDIAN_VAULT = "你的库路径"\n'
            "python tools/patent_reader/check_obsidian_env.py --set \"你的库路径\""
        ),
        "hint_bash": (
            'export PATENT_READER_OBSIDIAN_VAULT="你的库路径"\n'
            'python tools/patent_reader/check_obsidian_env.py --set "你的库路径"'
        ),
    }


def runtime_config() -> dict[str, str]:
    resolved = resolve_obsidian_vault()
    vault = (resolved.get("vault") or "").strip()
    # 仅当目录存在时采用自动探测结果，避免脏路径
    if vault and not Path(vault).is_dir():
        # 环境变量显式指定时仍保留（用户可能稍后创建）
        if resolved.get("source") != "env":
            vault = ""

    papers_dir = os.environ.get("PATENT_READER_PAPERS_DIR", "Research/Patents").strip(
        "/\\"
    ) or "Research/Patents"
    glossary_dir = os.environ.get("PATENT_READER_GLOSSARY_DIR", "Research/术语").strip(
        "/\\"
    ) or "Research/术语"
    output_dir = os.environ.get(
        "PATENT_READER_OUTPUT_DIR", "outputs/patent_reader"
    ).strip()
    return {
        "obsidian_vault": vault,
        "papers_dir": papers_dir,
        "glossary_dir": glossary_dir,
        "output_dir": output_dir,
        "vault_source": str(resolved.get("source") or ""),
    }


def slugify_term(term: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", term.strip(), flags=re.UNICODE)
    return s.strip("_")[:60] or "term"


def slugify_pub(pub: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", pub.strip(), flags=re.UNICODE)
    return s.strip("_") or "patent"


def guess_independent(claim_text: str) -> bool:
    body = re.sub(r"^\s*\d+\s*[.\．、]\s*", "", claim_text.strip())
    if re.match(r"^(一种|一種|a |an )", body, re.I):
        return True
    low = body.lower()
    return not any(p.lower() in low for p in DEP_PATTERNS)


def parent_claim_numbers(claim_text: str) -> list[int]:
    """解析从属权引用的全部权号（含「权1或2」「claims 1-3」）。"""
    text = claim_text or ""
    nums: list[int] = []

    def _extend_chunk(chunk: str) -> None:
        for n in re.findall(r"\d+", chunk or ""):
            try:
                nums.append(int(n))
            except ValueError:
                continue

    for m in re.finditer(
        r"(?:根据|如|按照|按|依据)(?:前述)?权利要求\s*"
        r"([\d或与以及至到、,，\s与和及\-–—]+)",
        text,
    ):
        _extend_chunk(m.group(1))
    for m in re.finditer(
        r"according to claims?\s*([\d\s,orand\-–—]+)",
        text,
        re.I,
    ):
        _extend_chunk(m.group(1))
    for m in re.finditer(
        r"权利要求?\s*(\d+)\s*或\s*(?:权利要求?\s*)?(\d+)",
        text,
    ):
        nums.extend([int(m.group(1)), int(m.group(2))])
    # 去重保序
    return list(dict.fromkeys(n for n in nums if n > 0))


def parent_claim_number(claim_text: str) -> int | None:
    """启发式单父号：取引用列表首个（多选一时由 Agent 校对 claim_tree）。"""
    nums = parent_claim_numbers(claim_text)
    return nums[0] if nums else None


def normalize_claim_tree(tree: dict | None) -> dict:
    """规范化权项树：独立权清 parent、重建 roots、修正悬空父号。"""
    if not isinstance(tree, dict):
        return {"roots": [], "nodes": []}
    nodes_in = list(tree.get("nodes") or [])
    nodes: list[dict] = []
    seen: set[int] = set()
    for raw in nodes_in:
        if not isinstance(raw, dict):
            continue
        try:
            num = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        if num <= 0 or num in seen:
            continue
        seen.add(num)
        node = dict(raw)
        node["number"] = num
        indep = bool(node.get("is_independent"))
        node["is_independent"] = indep
        parent = node.get("parent")
        try:
            parent_i = int(parent) if parent is not None else None
        except (TypeError, ValueError):
            parent_i = None
        if indep:
            parent_i = None
        elif parent_i is not None and parent_i == num:
            parent_i = None
        node["parent"] = parent_i
        # 保留多引用候选供 Agent/展示
        cands = node.get("parent_candidates")
        if isinstance(cands, list):
            cleaned = []
            for x in cands:
                try:
                    xi = int(x)
                except (TypeError, ValueError):
                    continue
                if xi > 0 and xi != num:
                    cleaned.append(xi)
            node["parent_candidates"] = list(dict.fromkeys(cleaned))
        nodes.append(node)

    by_num = {n["number"]: n for n in nodes}
    # 悬空父号 → 挂到最近的更小编号独立权，否则前一条
    for n in nodes:
        if n["is_independent"]:
            n["parent"] = None
            continue
        p = n.get("parent")
        if p in by_num and p != n["number"]:
            continue
        cands = [c for c in (n.get("parent_candidates") or []) if c in by_num]
        if cands:
            n["parent"] = cands[0]
            continue
        fallback = next(
            (
                x["number"]
                for x in reversed(nodes)
                if x["number"] < n["number"] and x.get("is_independent")
            ),
            None,
        )
        if fallback is None:
            fallback = next(
                (x["number"] for x in reversed(nodes) if x["number"] < n["number"]),
                None,
            )
        n["parent"] = fallback

    # 断环：若沿 parent 走回自身，改为挂最近独立权
    for n in nodes:
        if n["is_independent"]:
            continue
        seen_path: set[int] = set()
        cur: int | None = n["number"]
        guard = 0
        while cur is not None and guard < 64:
            if cur in seen_path:
                n["parent"] = next(
                    (
                        x["number"]
                        for x in reversed(nodes)
                        if x["number"] < n["number"] and x.get("is_independent")
                    ),
                    None,
                )
                break
            seen_path.add(cur)
            cur = (by_num.get(cur) or {}).get("parent")
            guard += 1

    roots = [n["number"] for n in nodes if n.get("is_independent")]
    out = {**tree, "roots": roots, "nodes": nodes}
    return out


def validate_claim_tree(tree: dict | None) -> dict:
    """校验权项树；返回 passed/issues/warnings/count。"""
    issues: list[str] = []
    warnings: list[str] = []
    norm = normalize_claim_tree(tree)
    nodes = norm.get("nodes") or []
    if not nodes:
        warnings.append("empty_claim_tree")
        return {
            "passed": True,
            "issues": issues,
            "warnings": warnings,
            "count": 0,
            "tree": norm,
        }
    by_num = {n["number"]: n for n in nodes}
    for n in nodes:
        num = n["number"]
        if n.get("is_independent"):
            if n.get("parent") is not None:
                issues.append(f"claim[{num}]:independent_has_parent")
        else:
            p = n.get("parent")
            if p is None:
                issues.append(f"claim[{num}]:dependent_missing_parent")
            elif p not in by_num:
                issues.append(f"claim[{num}]:parent_not_found:{p}")
            elif p == num:
                issues.append(f"claim[{num}]:parent_self")
        cands = n.get("parent_candidates") or []
        if isinstance(cands, list) and len(cands) >= 2:
            warnings.append(f"claim[{num}]:multi_parent_candidates:{cands}")
            if n.get("parent") not in cands and n.get("parent") is not None:
                warnings.append(
                    f"claim[{num}]:parent_not_in_candidates:{n.get('parent')}"
                )

    # 环检测
    for n in nodes:
        if n.get("is_independent"):
            continue
        seen_path: set[int] = set()
        cur: int | None = n["number"]
        guard = 0
        while cur is not None and guard < 64:
            if cur in seen_path:
                issues.append(f"claim[{n['number']}]:cycle_via:{cur}")
                break
            seen_path.add(cur)
            cur = (by_num.get(cur) or {}).get("parent")
            guard += 1

    declared_roots = list(norm.get("roots") or [])
    expected = [n["number"] for n in nodes if n.get("is_independent")]
    if declared_roots != expected:
        warnings.append(f"roots_mismatch:declared={declared_roots}:expected={expected}")

    review = (tree or {}).get("review") if isinstance(tree, dict) else None
    if not (isinstance(review, dict) and str(review.get("by") or "").lower() in ("agent", "human")):
        warnings.append("not_agent_reviewed")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "count": len(nodes),
        "tree": norm,
    }


def load_domain_rules() -> list[dict]:
    path = ROOT / "references" / "patent_domain_rules.yaml"
    if not path.is_file():
        return [{"label": "未分类", "ipc_prefixes": [], "keywords": []}]
    domains: list[dict] = []
    current: dict | None = None
    mode: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- label:"):
            if current:
                domains.append(current)
            current = {
                "label": stripped.split(":", 1)[1].strip(),
                "ipc_prefixes": [],
                "keywords": [],
            }
            mode = None
        elif stripped.startswith("ipc_prefixes:"):
            mode = "ipc"
        elif stripped.startswith("keywords:"):
            mode = "kw"
        elif stripped.startswith("- ") and current is not None and mode:
            val = stripped[2:].strip().strip('"')
            if mode == "ipc":
                current["ipc_prefixes"].append(val)
            else:
                current["keywords"].append(val)
    if current:
        domains.append(current)
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


def _parse_inline_yaml_list(raw: str) -> list[str] | None:
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        return None
    inner = raw[1:-1].strip()
    if not inner:
        return []
    return [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]


def _parse_yaml_list_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """解析 YAML 列表；遇到新 hint（- ipc_prefix:）或其它映射键则停止。"""
    items: list[str] = []
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if stripped.startswith("- ipc_prefix:"):
            break
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip('"').strip("'"))
            i += 1
            continue
        # 同级或更外层的 key: value
        if re.match(r"^[a-zA-Z_][\w]*:", stripped):
            break
        break
    return items, i


def load_ipc_application_hints() -> list[dict]:
    path = ROOT / "references" / "ipc_application_hints.yaml"
    if not path.is_file():
        return []
    # 优先 PyYAML（若已安装）
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        hints = data.get("hints") or []
        out: list[dict] = []
        for h in hints:
            if not isinstance(h, dict):
                continue
            out.append(
                {
                    "ipc_prefix": str(h.get("ipc_prefix") or "").strip(),
                    "keywords": list(h.get("keywords") or []),
                    "industry": str(h.get("industry") or "").strip(),
                    "typical_modules": list(h.get("typical_modules") or []),
                    "user_scenarios": list(h.get("user_scenarios") or []),
                    "search_hints": list(h.get("search_hints") or []),
                }
            )
        if out:
            return out
    except Exception:
        pass

    hints: list[dict] = []
    current: dict | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    list_fields = ("keywords", "typical_modules", "user_scenarios", "search_hints")
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("- ipc_prefix:"):
            if current:
                hints.append(current)
            current = {
                "ipc_prefix": stripped.split(":", 1)[1].strip(),
                "keywords": [],
                "industry": "",
                "typical_modules": [],
                "user_scenarios": [],
                "search_hints": [],
            }
            i += 1
            continue
        if current is None:
            i += 1
            continue
        matched_list = False
        for field in list_fields:
            if stripped.startswith(f"{field}:"):
                rest = stripped.split(":", 1)[1].strip()
                inline = _parse_inline_yaml_list(rest)
                if inline is not None:
                    current[field] = inline
                    i += 1
                else:
                    i += 1
                    items, i = _parse_yaml_list_block(lines, i)
                    current[field] = items
                matched_list = True
                break
        if matched_list:
            continue
        if stripped.startswith("industry:"):
            current["industry"] = stripped.split(":", 1)[1].strip()
        i += 1
    if current:
        hints.append(current)
    return hints


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


def extract_assignees(text: str) -> list[str]:
    """从专利文本启发式抽取申请人/专利权人。"""
    assignees: list[str] = []
    patterns = [
        r"(?:申请(?:人|单位)|专利权人|申请人)\s*[:：]\s*([^\n；;]{2,80})",
        r"(?:Applicant|Assignee)\s*[:：]\s*([^\n;]{2,80})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            name = m.group(1).strip().strip("；;，,")
            if name and name not in assignees:
                assignees.append(name)
    return assignees[:5]


def extract_ipc_codes(text: str) -> list[str]:
    codes = re.findall(r"\b([A-H]\d{2}[A-Z]\d+/\d+)\b", text, re.I)
    seen: list[str] = []
    for c in codes:
        up = c.upper()
        if up not in seen:
            seen.append(up)
    return seen[:10]
