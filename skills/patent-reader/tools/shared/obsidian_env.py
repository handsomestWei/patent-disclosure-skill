"""Obsidian 安装与库路径探测、持久化库路径、解读运行配置（环境变量）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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
            "python skills/patent-reader/tools/vault/check_obsidian_env.py --set \"你的库路径\""
        ),
        "hint_bash": (
            'export PATENT_READER_OBSIDIAN_VAULT="你的库路径"\n'
            'python skills/patent-reader/tools/vault/check_obsidian_env.py --set "你的库路径"'
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
