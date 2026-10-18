#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专利附图生图 jobs：一图一 job、结构化 prompt、结果登记（对齐 codex-ppt 的 slide jobs）。

来源（``prepare`` 三选一）：

- ``--from-md``：交底 md 的 mermaid 围栏（3.2 框图 / 3.4 流程图）。按围栏源码 sha1 建 job，
  ``mermaid_render.py --ai-figures`` 按同一 sha1 引用已登记的生成图，未命中回退本地渲染。
- ``--from-invention-yaml``：申请包 ``figures/invention_figures.yaml``（block_diagram / flowchart）。
  登记时自动 ``bw_normalize`` 成 ``图N.png`` + ``图N.svg``（及 ``摘要附图.png``）。
- ``--from-lineart-jobs``：交底包线稿门禁 jobs（design / structure / 单件 compose）。
  ``--with-callouts`` 另为结构线稿建件号引出 job（以轮廓图为 edit 输入）。

  python tools/figure_jobs.py prepare --case-dir outputs/case --from-md outputs/case/draft.md
  python tools/figure_jobs.py record  --case-dir outputs/case --fig mmd_01 [--image 生成图.png] [--qa-note ...]
  python tools/figure_jobs.py block   --case-dir outputs/case --fig mmd_02 --reason "标签错字两轮未修好"
  python tools/figure_jobs.py fallback --case-dir outputs/case --fig mmd_02 --reason "已用 mermaid_render 本地渲染"
  python tools/figure_jobs.py status  --case-dir outputs/case

单个 job 写在 ``{case}/figure_jobs/{fig_id}.json``（``image_api.py job --job`` 可直接执行）；
总表 ``{case}/figure_jobs.json``。状态：pending / recorded / blocked / fallback_local。
stderr 摘要前缀 ``FIGURE_JOB:``。``status`` 有 pending / blocked 时退出码 2。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
from stdio_utf8 import ensure_utf8_stdio  # noqa: E402

PREFIX = "FIGURE_JOB:"
MANIFEST = "figure_jobs.json"
JOBS_DIR = "figure_jobs"
AI_DIR = "ai_figures"
TEMPLATES = _TOOLS.parent / "references" / "figure_prompt_templates.yaml"
DONE = ("recorded", "fallback_local")
STATUSES = ("pending", "recorded", "blocked", "fallback_local")

_MMD_START = re.compile(r"^```mermaid\s*$", re.IGNORECASE)
_MMD_END = re.compile(r"^```\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
_NODE_LABEL = re.compile(
    r"\b[A-Za-z_][\w-]*\s*(?:\(\(|\[\[|\[\(|\(\[|\{\{|\[|\(|\{|>)\s*"
    r"(?:\"(?P<q>[^\"]*)\"|'(?P<s>[^']*)'|(?P<u>[^\]\)\}\"']+?))\s*"
    r"(?:\)\)|\]\]|\)\]|\]\)|\}\}|\]|\)|\})"
)
_EDGE_LABEL = re.compile(r"\|\s*\"?([^|\"]+?)\"?\s*\|")
_SUBGRAPH = re.compile(r"^\s*subgraph\s+(?:[\w-]+\s*\[\s*\"?(?P<t>[^\"\]]+)\"?\s*\]|\"?(?P<n>[^\"\[]+?)\"?)\s*$")
_SKIP_LINE = re.compile(r"^\s*(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|end\s*$|direction\b)")


# ---------------------------------------------------------------- utilities

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _die(message: str, code: int = 1) -> None:
    print(f"{PREFIX} ERROR {message}", file=sys.stderr)
    raise SystemExit(code)


def mermaid_sha(src: str) -> str:
    """Stable key for one mermaid block (after step-id label fix, newline-normalised)."""
    text = src.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _sha_obj(obj: Any) -> str:
    return _sha_text(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        item = " ".join(str(raw).replace("<br/>", " ").replace("<br>", " ").split())
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _safe(token: str, default: str = "x") -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(token))[:60]
    return safe or default


def load_templates(path: Path = TEMPLATES) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data.get("kinds"), dict):
        raise ValueError(f"{path} 缺少 kinds")
    return data


def build_prompt(kind: str, primary: str, *, subject: str = "", text_verbatim: list[str] | None = None,
                 extra_constraints: list[str] | None = None, templates: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble a codex-ppt style structured prompt from the template of ``kind``."""
    from image_api import _augment_prompt_fields

    templates = templates or load_templates()
    common = templates.get("common") or {}
    spec = templates["kinds"].get(kind)
    if spec is None:
        raise KeyError(f"未知 kind：{kind}")
    constraints = list(common.get("constraints") or []) + list(spec.get("constraints") or []) + list(extra_constraints or [])
    verbatim = _dedupe(text_verbatim or [])
    fields = {
        "use_case": spec.get("use_case"),
        "subject": subject or None,
        "style": spec.get("style"),
        "composition": spec.get("composition"),
        "text": " / ".join(verbatim) if verbatim else None,
        "constraints": " ".join(constraints) if constraints else None,
        "negative": common.get("negative"),
    }
    return {
        "prompt": _augment_prompt_fields(True, primary.strip(), fields),
        "size": str(spec.get("size") or "1536x2048"),
        "quality": str(spec.get("quality") or "high"),
        "background": str(spec.get("background") or common.get("background") or "opaque"),
        "text_verbatim": verbatim,
    }


# ---------------------------------------------------------------- manifest

def manifest_path(case_dir: Path) -> Path:
    return case_dir / MANIFEST


def load_manifest(case_dir: Path) -> dict[str, Any]:
    path = manifest_path(case_dir)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("jobs"), list):
                return data
        except json.JSONDecodeError:
            pass
    return {"version": 1, "jobs": []}


def save_manifest(case_dir: Path, manifest: dict[str, Any]) -> Path:
    case_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(case_dir)
    manifest["updated_at"] = _now()
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _job_file(case_dir: Path, fig_id: str) -> Path:
    return case_dir / JOBS_DIR / f"{fig_id}.json"


def _write_job(case_dir: Path, job: dict[str, Any]) -> None:
    path = _job_file(case_dir, job["fig_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_jobs(case_dir: Path, new_jobs: list[dict[str, Any]], *, source_path: str) -> list[dict[str, Any]]:
    """Replace jobs from ``source_path``; keep done status (and output) for unchanged sources."""
    manifest = load_manifest(case_dir)
    old = [j for j in manifest["jobs"] if j.get("source", {}).get("path") == source_path]
    by_sha = {j.get("source", {}).get("sha"): j for j in old if j.get("status") in DONE}
    keep = [j for j in manifest["jobs"] if j.get("source", {}).get("path") != source_path]
    merged: list[dict[str, Any]] = []
    for job in new_jobs:
        prev = by_sha.get(job["source"]["sha"])
        if prev and Path(prev.get("out", "")).is_file():
            if Path(prev["out"]).resolve() != Path(job["out"]).resolve():
                Path(job["out"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(prev["out"], job["out"])
            for key in ("status", "backend", "qa_note", "recorded_at", "reason", "post_result"):
                if key in prev:
                    job[key] = prev[key]
        _write_job(case_dir, job)
        merged.append(job)
    manifest["jobs"] = keep + merged
    save_manifest(case_dir, manifest)
    return merged


def find_job(manifest: dict[str, Any], fig_id: str) -> dict[str, Any]:
    for job in manifest["jobs"]:
        if job.get("fig_id") == fig_id:
            return job
    _die(f"总表里没有 {fig_id}；先 prepare")
    return {}


def recorded_image_for_mermaid(manifest_file: Path, src: str) -> Path | None:
    """Used by ``mermaid_render.py --ai-figures``: recorded image for this block, else ``None``."""
    if not manifest_file.is_file():
        return None
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    sha = mermaid_sha(src)
    for job in data.get("jobs") or []:
        source = job.get("source") or {}
        if source.get("type") == "mermaid" and source.get("sha") == sha and job.get("status") == "recorded":
            out = Path(str(job.get("out") or ""))
            if not out.is_absolute():
                out = (manifest_file.parent / out).resolve()
            if out.is_file():
                return out
    return None


# ---------------------------------------------------------------- mermaid source

def extract_mermaid_labels(src: str) -> list[str]:
    labels: list[str] = []
    for line in src.splitlines():
        m = _SUBGRAPH.match(line)
        if m:
            labels.append(m.group("t") or m.group("n") or "")
            continue
        if _SKIP_LINE.match(line) or re.match(r"^\s*(?:flowchart|graph)\b", line):
            continue
        for nm in _NODE_LABEL.finditer(line):
            labels.append(nm.group("q") or nm.group("s") or nm.group("u") or "")
        labels.extend(_EDGE_LABEL.findall(line))
    return _dedupe(labels)


def _mermaid_kind(src: str, heading: str) -> str:
    if "流程" in heading:
        return "flowchart"
    if any(k in heading for k in ("框图", "架构", "系统", "模块", "结构")):
        return "block_diagram"
    if re.search(r"\b[Ss]\d+\s*[\[\(\{]", src) or "{" in src:
        return "flowchart"
    return "block_diagram"


def iter_mermaid_blocks(md_text: str) -> Iterable[tuple[str, str]]:
    """Yield ``(fixed_source, nearest_heading)`` per mermaid fence, same normalisation as mermaid_render."""
    try:
        from mermaid_render import ensure_step_ids_in_visible_labels
    except ImportError:
        _die("本包没有 mermaid_render.py；--from-md 只在交底包 tools/ 下可用")

    lines = md_text.splitlines(keepends=True)
    heading = ""
    i = 0
    while i < len(lines):
        hm = _HEADING.match(lines[i])
        if hm:
            heading = hm.group(1)
        if _MMD_START.match(lines[i]):
            i += 1
            body: list[str] = []
            while i < len(lines) and not _MMD_END.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            joined = "".join(body)
            fixed, n_fix = ensure_step_ids_in_visible_labels(joined)
            if n_fix and joined.endswith("\n") and not fixed.endswith("\n"):
                fixed += "\n"
            yield fixed, heading
            continue
        i += 1


def jobs_from_md(md_path: Path, case_dir: Path, templates: dict[str, Any]) -> list[dict[str, Any]]:
    md_text = md_path.read_text(encoding="utf-8", errors="replace")
    jobs: list[dict[str, Any]] = []
    for idx, (src, heading) in enumerate(iter_mermaid_blocks(md_text), start=1):
        kind = _mermaid_kind(src, heading)
        labels = extract_mermaid_labels(src)
        fig_id = f"mmd_{idx:02d}"
        primary = (
            "Redraw the following Mermaid diagram as a clean black-and-white patent drawing. "
            "Keep exactly the same nodes, groups, edges, edge directions and label texts; "
            "do not add, drop, merge or rename anything.\n"
            f"Section: {heading or 'n/a'}\n"
            f"```mermaid\n{src.strip()}\n```"
        )
        built = build_prompt(kind, primary, subject=f"{'流程图' if kind == 'flowchart' else '系统框图'}：{heading}",
                             text_verbatim=labels, templates=templates)
        jobs.append(
            {
                "fig_id": fig_id,
                "kind": kind,
                "title": heading,
                "source": {"type": "mermaid", "path": str(md_path), "index": idx, "sha": mermaid_sha(src)},
                **built,
                "input_images": [],
                "out": str((case_dir / AI_DIR / f"{fig_id}.png").resolve()),
                "fallback": {"tool": "tools/mermaid_render.py", "note": "未登记的围栏由 mermaid_render 本地渲染"},
                "status": "pending",
            }
        )
    return jobs


# ---------------------------------------------------------------- invention_figures.yaml

def _block_subject(fig: dict[str, Any]) -> tuple[str, list[str]]:
    labels: list[str] = []
    names: dict[str, str] = {}
    lines: list[str] = []
    for col in fig.get("columns") or []:
        nodes = [n for n in col.get("nodes") or [] if isinstance(n, dict)]
        for n in nodes:
            names[str(n.get("id"))] = str(n.get("label") or "")
        labels.append(str(col.get("label") or ""))
        labels.extend(str(n.get("label") or "") for n in nodes)
        lines.append(f"- Column (dashed group) 「{col.get('label')}」: " + "、".join(f"「{n.get('label')}」" for n in nodes))
    for ex in fig.get("extras") or []:
        nodes = [n for n in ex.get("nodes") or [] if isinstance(n, dict)]
        for n in nodes:
            names[str(n.get("id"))] = str(n.get("label") or "")
        labels.append(str(ex.get("label") or ""))
        labels.extend(str(n.get("label") or "") for n in nodes)
        lines.append(f"- Group above 「{ex.get('above')}」 (dashed) 「{ex.get('label')}」: "
                     + "、".join(f"「{n.get('label')}」" for n in nodes))
    for e in fig.get("edges") or []:
        a, b = names.get(str(e.get("from")), e.get("from")), names.get(str(e.get("to")), e.get("to"))
        lines.append(f"- Arrow 「{a}」 → 「{b}」" + (f" labelled 「{e['label']}」" if e.get("label") else ""))
    return "\n".join(lines), labels


def _flow_subject(fig: dict[str, Any]) -> tuple[str, list[str]]:
    nodes = [n for n in fig.get("nodes") or [] if isinstance(n, dict)]
    nodes.sort(key=lambda n: (int(n.get("row") or 0), int(n.get("col") or 0)))
    names = {str(n.get("id")): str(n.get("label") or "") for n in nodes}
    labels = [names[str(n.get("id"))] for n in nodes]
    lines = [
        f"- {n.get('shape') or 'rect'} at row {n.get('row')}, column {n.get('col', 0)}: 「{n.get('label')}」"
        for n in nodes
    ]
    for e in fig.get("edges") or []:
        a, b = names.get(str(e.get("from")), e.get("from")), names.get(str(e.get("to")), e.get("to"))
        extra = []
        if e.get("label"):
            extra.append(f"labelled 「{e['label']}」")
            labels.append(str(e["label"]))
        if e.get("route"):
            extra.append(f"routed along the {e['route']} side")
        lines.append(f"- Arrow 「{a}」 → 「{b}」" + (" " + ", ".join(extra) if extra else ""))
    return "\n".join(lines), labels


def jobs_from_invention_yaml(plan_path: Path, case_dir: Path, templates: dict[str, Any]) -> list[dict[str, Any]]:
    import yaml

    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    figures_dir = plan_path.parent
    jobs: list[dict[str, Any]] = []
    for fig in plan.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        kind = str(fig.get("kind") or "")
        if kind not in ("block_diagram", "flowchart"):
            continue
        no = int(fig.get("fig") or 0)
        if kind == "block_diagram":
            subject, labels = _block_subject(fig)
        else:
            subject, labels = _flow_subject(fig)
        primary = (
            f"Draw this patent application figure exactly as specified (caption for reference only, do not draw it: "
            f"「{fig.get('caption') or ''}」):\n{subject}"
        )
        built = build_prompt(f"application_{kind}", primary, subject=str(fig.get("caption") or ""),
                             text_verbatim=labels, templates=templates)
        post = {
            "tool": "bw_normalize",
            "out": str((figures_dir / f"图{no}.png").resolve()),
            "svg": str((figures_dir / f"图{no}.svg").resolve()),
        }
        if fig.get("abstract") is True:
            post["abstract_out"] = str((figures_dir / "摘要附图.png").resolve())
        jobs.append(
            {
                "fig_id": f"fig_{no}",
                "kind": f"application_{kind}",
                "title": str(fig.get("caption") or ""),
                "source": {"type": "invention_figures", "path": str(plan_path), "fig": no, "sha": _sha_obj(fig)},
                **built,
                "input_images": [],
                "out": str((figures_dir / "ai" / f"图{no}_raw.png").resolve()),
                "post": post,
                "fallback": {
                    "tool": "tools/render_invention_figures.py",
                    "args": ["--plan", str(plan_path), "--out-dir", str(figures_dir), "--only", str(no)],
                },
                "status": "pending",
            }
        )
    return jobs


# ---------------------------------------------------------------- lineart gate jobs

def _anchors_for_view(case_dir: Path, view: str) -> dict[str, Any]:
    path = case_dir / "structure_callout_anchors.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    for v in data.get("views") or []:
        if isinstance(v, dict) and str(v.get("view_name")) == view:
            return {str(c.get("id")): c for c in v.get("callouts") or [] if isinstance(c, dict)}
    return {}


def _refs(paths: Iterable[str], role: str) -> list[dict[str, str]]:
    return [{"path": str(p), "role": role, "fidelity": "high"} for p in paths if p and Path(str(p)).is_file()]


def _abs_out(case_dir: Path, job: dict[str, Any], key_abs: str, key_rel: str) -> str:
    if job.get(key_abs):
        return str(job[key_abs])
    return str((case_dir / str(job.get(key_rel) or "")).resolve())


def jobs_from_lineart(jobs_path: Path, case_dir: Path, templates: dict[str, Any], *, with_callouts: bool) -> list[dict[str, Any]]:
    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    src_jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    out_jobs: list[dict[str, Any]] = []
    for raw in src_jobs or []:
        if not isinstance(raw, dict):
            continue
        view = str(raw.get("view_name") or "view")
        refs = raw.get("reference_images") or raw.get("source_paths") or []
        if raw.get("part_id"):
            kind = "structure_part"
            fig_id = f"part_{_safe(view)}_{_safe(raw['part_id'])}"
            out = _abs_out(case_dir, raw, "absolute_output_path", "image_path")
            role = "assembly reference: draw only the named part as it appears here"
        elif "callouts" in raw:
            kind = "structure_lineart"
            fig_id = f"lineart_{_safe(view)}"
            out = _abs_out(case_dir, raw, "absolute_output_path", "output_path")
            role = "structure reference: preserve proportions and visible contours; ignore color, texture and background"
        else:
            kind = "design_lineart"
            fig_id = f"design_{_safe(view)}"
            out = _abs_out(case_dir, raw, "absolute_output_path", "output_path")
            role = "product reference: preserve proportions, openings and contours; ignore color, texture and background"
        built = build_prompt(kind, str(raw.get("gen_prompt") or ""), subject=f"{view}", templates=templates)
        sha = _sha_obj({k: raw.get(k) for k in ("view_name", "part_id", "gen_prompt", "reference_images", "callouts")})
        out_jobs.append(
            {
                "fig_id": fig_id,
                "kind": kind,
                "title": view,
                "source": {"type": "lineart_jobs", "path": str(jobs_path), "view": view, "sha": sha},
                **built,
                "input_images": _refs(refs, role),
                "gen_mode": raw.get("gen_mode"),
                "out": out,
                "fallback": {"note": "无本地等价物；后端不可用时按 image_gen.md 的 describe_then_txt2img 或记 uncertain"},
                "status": "pending",
            }
        )
        if kind == "structure_lineart" and with_callouts and raw.get("callout_mode", "overlay") == "overlay":
            out_jobs.append(_callout_job(raw, case_dir, jobs_path, out, templates))
    return out_jobs


def _callout_job(raw: dict[str, Any], case_dir: Path, jobs_path: Path, contour_out: str,
                 templates: dict[str, Any]) -> dict[str, Any]:
    view = str(raw.get("view_name") or "view")
    callouts = [c for c in raw.get("callouts") or [] if isinstance(c, dict) and c.get("id")]
    anchors = _anchors_for_view(case_dir, view)
    lines = []
    for c in callouts:
        a = anchors.get(str(c["id"])) or {}
        hint = ""
        if a.get("anchor") and a.get("label"):
            hint = f" — leader touches the part near (x={a['anchor'][0]}, y={a['anchor'][1]}), number placed near (x={a['label'][0]}, y={a['label'][1]}) in normalized canvas coordinates"
        lines.append(f"- {c['id']}: {c.get('name') or ''}{hint}")
    primary = (
        "Add part numbers with straight leader lines to the input patent drawing. "
        "Do not redraw or modify the existing contours in any way.\n"
        "Parts (number: name):\n" + "\n".join(lines)
    )
    built = build_prompt("structure_callout", primary, subject=view,
                         text_verbatim=[str(c["id"]) for c in callouts], templates=templates)
    out = _abs_out(case_dir, raw, "absolute_callout_output_path", "callout_output_path")
    return {
        "fig_id": f"callout_{_safe(view)}",
        "kind": "structure_callout",
        "title": view,
        "source": {"type": "lineart_jobs", "path": str(jobs_path), "view": view,
                   "sha": _sha_obj({"callouts": callouts, "anchors": anchors, "contour": contour_out})},
        **built,
        "input_images": [{"path": contour_out, "role": "drawing to annotate: keep every contour unchanged", "fidelity": "high"}],
        "requires": [f"lineart_{_safe(view)}"],
        "out": out,
        "fallback": {
            "tool": "tools/structure_callout_overlay.py",
            "note": "AI 件号未过 QA（错号/端点落错件/轮廓被改）时，按 structure_callout_anchors.yaml 走 overlay",
        },
        "status": "pending",
    }


# ---------------------------------------------------------------- record / status

def _post_process(job: dict[str, Any]) -> list[str]:
    from bw_normalize import flatten_alpha

    if flatten_alpha(Path(job["out"])):
        job["flattened_alpha"] = True
    post = job.get("post") or {}
    if post.get("tool") != "bw_normalize":
        return []
    from bw_normalize import normalize

    result = normalize(
        Path(job["out"]),
        Path(post["out"]),
        svg=Path(post["svg"]) if post.get("svg") else None,
        abstract_out=Path(post["abstract_out"]) if post.get("abstract_out") else None,
    )
    job["post_result"] = {k: result[k] for k in ("size_mm", "color_ratio", "gray_ratio")}
    return list(result["written"])


def _resolve_backend(case_dir: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    from figure_backend import confirmed_backend

    backend = confirmed_backend(case_dir)
    if backend is None:
        _die("出图后端尚未确认；先按 figure_generation.md 跑 figure_backend.py --set <backend> --confirmed")
    return str(backend)


def cmd_prepare(args: argparse.Namespace) -> int:
    case_dir = args.case_dir.resolve()
    templates = load_templates()
    sources = [s for s in (args.from_md, args.from_invention_yaml, args.from_lineart_jobs) if s]
    if len(sources) != 1:
        _die("prepare 须且只能指定一个来源：--from-md / --from-invention-yaml / --from-lineart-jobs")
    src = sources[0].resolve()
    if not src.is_file():
        _die(f"找不到来源 {src}")
    if args.from_md:
        jobs = jobs_from_md(src, case_dir, templates)
    elif args.from_invention_yaml:
        jobs = jobs_from_invention_yaml(src, case_dir, templates)
    else:
        jobs = jobs_from_lineart(src, case_dir, templates, with_callouts=args.with_callouts)
    merged = merge_jobs(case_dir, jobs, source_path=str(src))
    pending = [j["fig_id"] for j in merged if j["status"] == "pending"]
    print(json.dumps({"ok": True, "manifest": str(manifest_path(case_dir)),
                      "jobs": [{k: j[k] for k in ("fig_id", "kind", "status", "out")} for j in merged]},
                     ensure_ascii=False, indent=2))
    print(f"{PREFIX} prepared={len(merged)} pending={len(pending)} source={src.name}", file=sys.stderr)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    case_dir = args.case_dir.resolve()
    manifest = load_manifest(case_dir)
    job = find_job(manifest, args.fig)
    backend = _resolve_backend(case_dir, args.backend)
    out = Path(job["out"])
    if args.image:
        image = args.image.resolve()
        if not image.is_file():
            _die(f"找不到生成图 {image}")
        if image != out.resolve():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image, out)
    if not out.is_file():
        _die(f"{args.fig} 的输出 {out} 不存在；先出图或传 --image")
    job["backend"] = backend
    job["status"] = "recorded"
    job["recorded_at"] = _now()
    if args.qa_note:
        job["qa_note"] = args.qa_note
    job.pop("reason", None)
    try:
        written = _post_process(job)
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        _die(f"{args.fig} 后处理失败：{exc}")
    _write_job(case_dir, job)
    save_manifest(case_dir, manifest)
    print(json.dumps({"ok": True, "fig_id": job["fig_id"], "out": str(out), "written": written,
                      "post_result": job.get("post_result")}, ensure_ascii=False, indent=2))
    print(f"{PREFIX} recorded={job['fig_id']} backend={job['backend']}", file=sys.stderr)
    return 0


def _set_status(args: argparse.Namespace, status: str) -> int:
    case_dir = args.case_dir.resolve()
    manifest = load_manifest(case_dir)
    job = find_job(manifest, args.fig)
    job["status"] = status
    job["reason"] = args.reason
    job["updated_at"] = _now()
    if status == "fallback_local":
        job["backend"] = "local"
    _write_job(case_dir, job)
    save_manifest(case_dir, manifest)
    print(f"{PREFIX} {status}={job['fig_id']} reason={args.reason}", file=sys.stderr)
    return 0


def summarize(manifest: dict[str, Any]) -> dict[str, Any]:
    counts = {s: 0 for s in STATUSES}
    for job in manifest["jobs"]:
        counts[job.get("status", "pending")] = counts.get(job.get("status", "pending"), 0) + 1
    return {
        "counts": counts,
        "pending": [j["fig_id"] for j in manifest["jobs"] if j.get("status") == "pending"],
        "blocked": [{"fig_id": j["fig_id"], "reason": j.get("reason")} for j in manifest["jobs"] if j.get("status") == "blocked"],
        "fallback_local": [{"fig_id": j["fig_id"], "reason": j.get("reason")} for j in manifest["jobs"]
                           if j.get("status") == "fallback_local"],
    }


def cmd_status(args: argparse.Namespace) -> int:
    case_dir = args.case_dir.resolve()
    summary = summarize(load_manifest(case_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    c = summary["counts"]
    print(
        f"{PREFIX} recorded={c['recorded']} fallback_local={c['fallback_local']} "
        f"pending={c['pending']} blocked={c['blocked']}",
        file=sys.stderr,
    )
    return 2 if (c["pending"] or c["blocked"]) else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="专利附图生图 jobs：prepare / record / block / fallback / status")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="从来源建 job")
    p.add_argument("--case-dir", required=True, type=Path)
    p.add_argument("--from-md", type=Path)
    p.add_argument("--from-invention-yaml", type=Path)
    p.add_argument("--from-lineart-jobs", type=Path)
    p.add_argument("--with-callouts", action="store_true", help="结构线稿另建件号引出 job")
    p.set_defaults(func=cmd_prepare)

    r = sub.add_parser("record", help="读图 QA 通过后登记")
    r.add_argument("--case-dir", required=True, type=Path)
    r.add_argument("--fig", required=True)
    r.add_argument("--image", type=Path, help="生成图路径（内置工具出图时传；会复制到 job.out）")
    r.add_argument("--backend", choices=("builtin", "cli"))
    r.add_argument("--qa-note")
    r.set_defaults(func=cmd_record)

    for name, status, help_text in (
        ("block", "blocked", "两轮修复仍不过；交付前须改为 fallback"),
        ("fallback", "fallback_local", "已用本地渲染替代"),
    ):
        b = sub.add_parser(name, help=help_text)
        b.add_argument("--case-dir", required=True, type=Path)
        b.add_argument("--fig", required=True)
        b.add_argument("--reason", required=True)
        b.set_defaults(func=lambda a, s=status: _set_status(a, s))

    s = sub.add_parser("status", help="汇总；有 pending/blocked 退出码 2")
    s.add_argument("--case-dir", required=True, type=Path)
    s.set_defaults(func=cmd_status)
    return ap


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
