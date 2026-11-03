#!/usr/bin/env python
"""把 invention_figures.yaml 画成黑白申请附图（SVG，并尽量出 PNG）。

框图：虚线分组、框内模块名，不画件号引出线。流程图：框内「步骤一…」，直角折线。
图号写在说明书正文，不要画进图里。PNG 按 SVG 内容包围盒截取，不要整页 A4 留白。

用法：
  python tools/render_invention_figures.py --plan figures/invention_figures.yaml --out-dir figures
  python tools/render_invention_figures.py --plan figures/invention_figures.yaml --out-dir figures --only 2
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stdio_utf8 import ensure_utf8_stdio

PAGE_W = 210.0
PAGE_H = 297.0
M_TOP = 8.0
M_SIDE = 8.0
M_BOT = 8.0
CONTENT_PAD = 6.0
MARK_FS = 3.4
LABEL_FS = 3.6
STROKE = 0.5
GUTTER = 8.0


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml

        data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("plan 根须为 mapping")
    return data


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + w / 2, y + h / 2


def _rect(x: float, y: float, w: float, h: float, *, dash: bool = False) -> str:
    dash_attr = ' stroke-dasharray="2.2 1.4"' if dash else ""
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'fill="#fff" stroke="#000" stroke-width="{STROKE}"{dash_attr}/>'
    )


def _diamond(box: tuple[float, float, float, float]) -> str:
    x, y, w, h = box
    cx, cy = _center(box)
    pts = f"{cx:.2f},{y:.2f} {x+w:.2f},{cy:.2f} {cx:.2f},{y+h:.2f} {x:.2f},{cy:.2f}"
    return (
        f'<polygon points="{pts}" fill="#fff" stroke="#000" '
        f'stroke-width="{STROKE}" stroke-linejoin="bevel"/>'
    )


def _text(x: float, y: float, text: str, *, size: float, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="SimSun, Songti SC, serif" font-size="{size}" fill="#000">'
        f"{_esc(text)}</text>"
    )


def _wrap_label(raw: str, max_chars: int) -> list[str]:
    raw = str(raw).strip()
    if len(raw) <= max_chars:
        return [raw]
    if raw.startswith("步骤") and "，" in raw[:6]:
        a, b = raw.split("，", 1)
        if len(b) <= max_chars:
            return [a + "，", b]
        for sep in ("或", "并", "且", "；"):
            if sep in b:
                i = b.index(sep)
                left, right = b[: i + len(sep)], b[i + len(sep) :]
                if left and right:
                    return [a + "，", left, right] if len(left) <= max_chars else [a + "，", b[:max_chars], b[max_chars:]]
        mid = max(1, (len(b) + 1) // 2)
        return [a + "，", b[:mid], b[mid:]]
    if raw.startswith("S") and " " in raw[:4]:
        a, b = raw.split(" ", 1)
        if len(b) <= max_chars:
            return [a, b]
    mid = max(1, (len(raw) + 1) // 2)
    return [raw[:mid], raw[mid:]]


def _multiline_label(cx: float, cy: float, label: str, *, size: float, max_chars: int) -> str:
    lines = [ln for ln in _wrap_label(label, max_chars) if ln]
    gap = size * 1.2
    y0 = cy - gap * (len(lines) - 1) / 2 + size * 0.35
    return "".join(_text(cx, y0 + i * gap, line, size=size) for i, line in enumerate(lines))


def _defs() -> str:
    return (
        "<defs>"
        '<marker id="arr" markerWidth="3.6" markerHeight="3.6" refX="3.2" refY="1.8" orient="auto">'
        '<path d="M0,0 L3.6,1.8 L0,3.6 z" fill="#000"/>'
        "</marker>"
        "</defs>"
    )


def _union_bounds(
    boxes: list[tuple[float, float, float, float]],
    points: list[tuple[float, float]] | None = None,
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for x, y, w, h in boxes:
        xs.extend((x, x + w))
        ys.extend((y, y + h))
    for x, y in points or []:
        xs.append(x)
        ys.append(y)
    if not xs:
        return 0.0, 0.0, PAGE_W, 80.0
    return min(xs), min(ys), max(xs), max(ys)


def _content_wrap(
    inner: str,
    boxes: list[tuple[float, float, float, float]],
    points: list[tuple[float, float]] | None = None,
) -> str:
    x0, y0, x1, y1 = _union_bounds(boxes, points)
    pad = CONTENT_PAD
    vb_x, vb_y = x0 - pad, y0 - pad
    vb_w, vb_h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    body = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{vb_w:.2f}mm" height="{vb_h:.2f}mm" '
        f'viewBox="{vb_x:.2f} {vb_y:.2f} {vb_w:.2f} {vb_h:.2f}">'
        f"{_defs()}"
        f'<rect x="{vb_x:.2f}" y="{vb_y:.2f}" width="{vb_w:.2f}" height="{vb_h:.2f}" '
        f'fill="#fff" stroke="none"/>'
        f"{inner}"
        "</svg>"
    )
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def _page_wrap(inner: str, fig_label: str = "") -> str:
    del fig_label
    return _content_wrap(inner, [(0.0, 0.0, PAGE_W, PAGE_H)])


def _port(box: tuple[float, float, float, float], side: str) -> tuple[float, float]:
    x, y, w, h = box
    cx, cy = _center(box)
    return {
        "n": (cx, y),
        "s": (cx, y + h),
        "e": (x + w, cy),
        "w": (x, cy),
    }[side]


def _ortho_arrow(points: list[tuple[float, float]]) -> str:
    if len(points) < 2:
        return ""
    cleaned: list[tuple[float, float]] = [points[0]]
    for pt in points[1:]:
        prev = cleaned[-1]
        if abs(pt[0] - prev[0]) < 0.05 and abs(pt[1] - prev[1]) < 0.05:
            continue
        if len(cleaned) >= 2:
            a = cleaned[-2]
            b = cleaned[-1]
            # 去掉共线中间点
            if (abs(a[0] - b[0]) < 0.05 and abs(b[0] - pt[0]) < 0.05) or (
                abs(a[1] - b[1]) < 0.05 and abs(b[1] - pt[1]) < 0.05
            ):
                cleaned[-1] = pt
                continue
        cleaned.append(pt)
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in cleaned)
    return (
        f'<polyline class="flow" points="{pts}" fill="none" stroke="#000" '
        f'stroke-width="{STROKE}" stroke-linejoin="round" stroke-linecap="butt" '
        f'marker-end="url(#arr)"/>'
    )


def _h_callout(mark: str, box: tuple[float, float, float, float], side: str) -> str:
    """水平引出线：数字在框外，线与框边同一高度。"""
    x, y, w, h = box
    cy = y + h / 2
    if side == "left":
        nx = x - 11.0
        x1, x2 = nx + 2.4, x
        anchor = "end"
    else:
        nx = x + w + 11.0
        x1, x2 = nx - 2.4, x + w
        anchor = "start"
    return (
        f'<g class="callout" data-mark="{_esc(mark)}" data-side="{side}">'
        f'<line x1="{x1:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{cy:.2f}" '
        f'stroke="#000" stroke-width="{STROKE}"/>'
        f"{_text(nx, cy + MARK_FS * 0.35, mark, size=MARK_FS, anchor=anchor)}"
        "</g>"
    )


def _group_callout(mark: str, box: tuple[float, float, float, float], side: str) -> str:
    """组号对准虚线框标题行，指向该框左右边，避免落到内部模块上。"""
    x, y, w, _h = box
    return _h_callout(mark, (x, y + 1.5, w, 8.0), side)


def _segment_hits_box(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    box: tuple[float, float, float, float],
    *,
    pad: float = 1.2,
) -> bool:
    bx, by, bw, bh = box
    x_lo, x_hi = bx + pad, bx + bw - pad
    y_lo, y_hi = by + pad, by + bh - pad
    if abs(x1 - x2) < 0.05:
        x = x1
        lo, hi = (y1, y2) if y1 < y2 else (y2, y1)
        return x_lo < x < x_hi and hi > y_lo and lo < y_hi
    if abs(y1 - y2) < 0.05:
        y = y1
        lo, hi = (x1, x2) if x1 < x2 else (x2, x1)
        return y_lo < y < y_hi and hi > x_lo and lo < x_hi
    return False


def _vline_blocked(
    x: float,
    y1: float,
    y2: float,
    others: list[tuple[float, float, float, float]],
) -> bool:
    return any(_segment_hits_box(x, y1, x, y2, box) for box in others)


def layout_block(
    fig: dict[str, Any],
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, tuple[float, float, float, float]], dict[str, str]]:
    """返回 node_boxes, group_boxes, node_side。各列按自身模块数紧排，不跨列撑槽。"""
    columns = [c for c in (fig.get("columns") or []) if isinstance(c, dict)]
    extras = [e for e in (fig.get("extras") or []) if isinstance(e, dict)]
    node_boxes: dict[str, tuple[float, float, float, float]] = {}
    group_boxes: dict[str, tuple[float, float, float, float]] = {}
    node_side: dict[str, str] = {}

    inner_left = M_SIDE + GUTTER
    inner_right = PAGE_W - M_SIDE - GUTTER
    inner_w = inner_right - inner_left
    extra_h = 42.0 if extras else 0.0
    pad_y, pad_x = 16.0, 8.0
    box_h = 18.0
    step_y = 28.0
    y0 = M_TOP + 8 + extra_h
    n_col = max(1, len(columns))
    gap = 24.0 if n_col > 1 else 8.0
    col_w = (inner_w - gap * (n_col - 1)) / n_col

    for i, col in enumerate(columns):
        nodes = [n for n in (col.get("nodes") or []) if isinstance(n, dict)]
        n_nodes = max(len(nodes), 1)
        gx = inner_left + i * (col_w + gap)
        gy, gw = y0, col_w
        gh = pad_y * 2 + box_h + max(n_nodes - 1, 0) * step_y
        cid = str(col.get("id") or f"col{i}")
        group_boxes[cid] = (gx, gy, gw, gh)
        side = "left" if i == 0 and n_col > 1 else "right"
        box_w = gw - pad_x * 2
        for slot, node in enumerate(nodes):
            nid = str(node.get("id") or "")
            by = gy + pad_y + slot * step_y
            bx = gx + pad_x
            node_boxes[nid] = (bx, by, box_w, box_h)
            node_side[nid] = side

    for extra in extras:
        above = str(extra.get("above") or "")
        if above in group_boxes:
            gx, _gy, gw, _gh = group_boxes[above]
            ex, ey, ew, eh = gx, M_TOP + 4, gw, extra_h - 6
        else:
            ex, ey, ew, eh = inner_left + inner_w * 0.5, M_TOP + 4, col_w, extra_h - 6
        eid = str(extra.get("id") or "extra")
        group_boxes[eid] = (ex, ey, ew, eh)
        nodes = [n for n in (extra.get("nodes") or []) if isinstance(n, dict)]
        if nodes:
            nid = str(nodes[0].get("id") or "")
            node_boxes[nid] = (ex + 8, ey + 16, ew - 16, box_h)
            node_side[nid] = "right"
    return node_boxes, group_boxes, node_side


def _route_block_edge(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    others: list[tuple[float, float, float, float]] | None = None,
) -> list[tuple[float, float]]:
    acx, acy = _center(a)
    bcx, bcy = _center(b)
    others = others or []
    # 同列：上下相接；若竖线会穿过中间模块，从列左侧间隙绕行
    if abs(acx - bcx) < a[2] * 0.4:
        if acy < bcy:
            start, end = _port(a, "s"), _port(b, "n")
        else:
            start, end = _port(a, "n"), _port(b, "s")
        if not _vline_blocked(start[0], start[1], end[1], others):
            return [start, end]
        bus = min(a[0], b[0]) - 10.0
        enter = _port(b, "w")
        leave = _port(a, "w")
        return [leave, (bus, leave[1]), (bus, enter[1]), enter]
    # 同行：左右相接
    if abs(acy - bcy) < 4.0:
        if acx < bcx:
            return [_port(a, "e"), _port(b, "w")]
        return [_port(a, "w"), _port(b, "e")]
    # 跨列且不同行：先水平进间隙，再竖直，再水平
    if acx < bcx:
        bus = (a[0] + a[2] + b[0]) / 2
        return [_port(a, "e"), (bus, acy), (bus, bcy), _port(b, "w")]
    bus = (b[0] + b[2] + a[0]) / 2
    return [_port(a, "w"), (bus, acy), (bus, bcy), _port(b, "e")]


def render_block_diagram(fig: dict[str, Any]) -> str:
    node_boxes, group_boxes, node_side = layout_block(fig)
    parts: list[str] = []
    node_meta: dict[str, dict[str, Any]] = {}
    group_meta: dict[str, dict[str, Any]] = {}
    group_side: dict[str, str] = {}

    columns = [c for c in (fig.get("columns") or []) if isinstance(c, dict)]
    for i, col in enumerate(columns):
        gid = str(col.get("id") or "")
        group_meta[gid] = col
        group_side[gid] = "left" if i == 0 and len(columns) > 1 else "right"
        for node in col.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                node_meta[str(node["id"])] = node
    for extra in fig.get("extras") or []:
        if not isinstance(extra, dict):
            continue
        gid = str(extra.get("id") or "")
        group_meta[gid] = extra
        # 配置中心在调度器上方时，组号走左侧，避免与模块号 11 叠在右侧
        group_side[gid] = "left"
        for node in extra.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                node_meta[str(node["id"])] = node

    for gid, box in group_boxes.items():
        meta = group_meta.get(gid) or {}
        x, y, w, h = box
        parts.append(_rect(x, y, w, h, dash=True))
        parts.append(_text(x + 4, y + 6.2, str(meta.get("label") or ""), size=LABEL_FS, anchor="start"))

    all_node_boxes = list(node_boxes.values())
    for edge in fig.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        a = node_boxes.get(str(edge.get("from") or ""))
        b = node_boxes.get(str(edge.get("to") or ""))
        if not a or not b:
            continue
        others = [box for box in all_node_boxes if box not in (a, b)]
        parts.append(_ortho_arrow(_route_block_edge(a, b, others)))

    # 实线模块盖住可能穿过的连线
    for nid, box in node_boxes.items():
        meta = node_meta.get(nid) or {}
        x, y, w, h = box
        parts.append(_rect(x, y, w, h))
        parts.append(_multiline_label(*_center(box), str(meta.get("label") or nid), size=LABEL_FS, max_chars=9))

    return _content_wrap("".join(parts), list(group_boxes.values()) + list(node_boxes.values()))


def layout_flow(fig: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    nodes = [n for n in (fig.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    rows = sorted({int(n.get("row") or 0) for n in nodes})
    n_rows = max(1, len(rows))
    rect_h, diamond_h = 20.0, 28.0
    row_h = 36.0
    total_h = n_rows * row_h
    y0 = M_TOP
    cx = PAGE_W / 2
    has_side = any(int(n.get("col") or 0) != 0 for n in nodes)
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for node in nodes:
        row = int(node.get("row") or 0)
        col = int(node.get("col") or 0)
        shape = str(node.get("shape") or "rect")
        if shape == "diamond":
            w, h = (70.0, diamond_h)
        else:
            w, h = (90.0, rect_h) if not has_side else (48.0, rect_h)
        ry = rows.index(row) if row in rows else 0
        y = y0 + ry * row_h + (row_h - h) / 2
        x = cx - w / 2 + col * (56.0 if has_side else 0.0)
        boxes[str(node["id"])] = (x, y, w, h)
    return boxes


def _route_flow(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    route: str,
    from_shape: str,
    to_shape: str,
) -> list[tuple[float, float]]:
    if route == "right":
        rx = PAGE_W - M_SIDE - 4
        start = _port(a, "e")
        end = _port(b, "n")
        top = min(b[1] - 6, start[1])
        return [start, (rx, start[1]), (rx, top), (end[0], top), end]
    if route == "left":
        lx = M_SIDE + 4
        start = _port(a, "w")
        end = _port(b, "n")
        top = min(b[1] - 6, start[1])
        return [start, (lx, start[1]), (lx, top), (end[0], top), end]

    acx, acy = _center(a)
    bcx, bcy = _center(b)
    # 向下的主干
    if abs(acx - bcx) < 8 and bcy > acy:
        return [_port(a, "s"), _port(b, "n")]
    # 决策框左右分支：先水平离开菱形顶点，再向下落到目标顶边
    if from_shape == "diamond" and bcy > acy:
        if bcx < acx:
            start = _port(a, "w")
            return [start, (bcx, start[1]), _port(b, "n")]
        start = _port(a, "e")
        return [start, (bcx, start[1]), _port(b, "n")]
    # 左右汇入下方中列：从目标左右边进入，避免宽横梁围成梯形
    if bcy > acy:
        start = _port(a, "s")
        if acx < bcx:
            end = _port(b, "w")
        else:
            end = _port(b, "e")
        return [start, (start[0], end[1]), end]
    return [_port(a, "s"), _port(b, "n")]


def render_flowchart(fig: dict[str, Any]) -> str:
    nodes = [n for n in (fig.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    meta = {str(n["id"]): n for n in nodes}
    boxes = layout_flow(fig)
    parts: list[str] = ['<g class="flowchart">']
    edge_labels: list[str] = []
    edge_pts: list[tuple[float, float]] = []
    for edge in fig.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        fid = str(edge.get("from") or "")
        tid = str(edge.get("to") or "")
        a, b = boxes.get(fid), boxes.get(tid)
        if not a or not b:
            continue
        from_shape = str((meta.get(fid) or {}).get("shape") or "rect")
        to_shape = str((meta.get(tid) or {}).get("shape") or "rect")
        route = str(edge.get("route") or "")
        pts = _route_flow(a, b, route=route, from_shape=from_shape, to_shape=to_shape)
        edge_pts.extend(pts)
        parts.append(_ortho_arrow(pts))
        label = str(edge.get("label") or "")
        if label and len(pts) >= 2:
            x1, y1 = pts[0]
            x2, y2 = pts[1]
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2
            if abs(x2 - x1) >= abs(y2 - y1):
                ly -= 2.0
            else:
                lx += 3.0
            edge_labels.append(_text(lx, ly, label, size=2.5))

    for nid, box in boxes.items():
        node = meta.get(nid) or {}
        shape = str(node.get("shape") or "rect")
        parts.append(_diamond(box) if shape == "diamond" else _rect(*box))
        parts.append(
            _multiline_label(
                *_center(box),
                str(node.get("label") or nid),
                size=3.2,
                max_chars=14 if int((meta.get(nid) or {}).get("col") or 0) == 0 else 8,
            )
        )
    parts.extend(edge_labels)
    parts.append("</g>")
    return _content_wrap("".join(parts), list(boxes.values()), edge_pts)


def svg_to_png(svg_path: Path, png_path: Path) -> bool:
    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        "<style>html,body{margin:0;background:#fff;}svg{display:block;}</style></head><body>"
        + svg_path.read_text(encoding="utf-8")
        + "</body></html>"
    )
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as pw:
        for channel in ("chrome", "msedge", None):
            kwargs: dict[str, Any] = {"headless": True}
            if channel:
                kwargs["channel"] = channel
            try:
                browser = pw.chromium.launch(**kwargs)
            except Exception:
                continue
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1800}, device_scale_factor=2)
                page.set_content(html_doc, wait_until="load")
                loc = page.locator("svg")
                loc.first.wait_for(timeout=8000)
                page.evaluate(
                    """() => {
                      const svg = document.querySelector('svg');
                      if (!svg) return;
                      const bb = svg.getBBox();
                      const pad = 6;
                      const x = bb.x - pad, y = bb.y - pad;
                      const w = bb.width + pad * 2, h = bb.height + pad * 2;
                      svg.setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
                      svg.setAttribute('width', `${w}mm`);
                      svg.setAttribute('height', `${h}mm`);
                    }"""
                )
                loc.first.screenshot(path=str(png_path), type="png")
                return True
            except Exception:
                continue
            finally:
                browser.close()
    return False


def render_plan(
    plan: dict[str, Any],
    out_dir: Path,
    *,
    plan_dir: Path | None = None,
    only: set[int] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    png_ok = 0
    png_fail = 0
    plan_dir = plan_dir or out_dir
    for fig in plan.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        kind = str(fig.get("kind") or "")
        fig_no = int(fig.get("fig") or 0)
        if only is not None and fig_no not in only:
            continue
        if kind == "source_image":
            from compose_application_figure import compose_sheet

            raw = Path(str(fig.get("source") or ""))
            source = raw if raw.is_absolute() else (plan_dir / raw).resolve()
            try:
                result = compose_sheet(source, fig_no, out_dir, abstract=bool(fig.get("abstract")))
            except FileNotFoundError:
                png_fail += 1
                continue
            written.extend(result["written"])
            if result["png_ok"]:
                png_ok += 1
            else:
                png_fail += 1
            continue
        if kind == "block_diagram":
            svg = render_block_diagram(fig)
        elif kind == "flowchart":
            svg = render_flowchart(fig)
        else:
            continue
        svg_path = out_dir / f"图{fig_no}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        written.append(str(svg_path))
        png_path = out_dir / f"图{fig_no}.png"
        if svg_to_png(svg_path, png_path):
            png_ok += 1
            written.append(str(png_path))
            if fig.get("abstract") is True:
                abs_path = out_dir / "摘要附图.png"
                shutil.copyfile(png_path, abs_path)
                written.append(str(abs_path))
        else:
            png_fail += 1
    return {
        "svg": len([p for p in written if p.endswith(".svg")]),
        "png_ok": png_ok,
        "png_fail": png_fail,
        "written": written,
    }


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--only",
        type=int,
        action="append",
        metavar="N",
        help="只渲染图 N（可重复）；用于生图未过 QA 的图回退本地渲染",
    )
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    plan = _load(plan_path)
    result = render_plan(
        plan,
        args.out_dir.expanduser().resolve(),
        plan_dir=plan_path.parent,
        only=set(args.only) if args.only else None,
    )
    ok = result["svg"] > 0
    print(
        f"APPLICATION_FIG: ok={1 if ok else 0} svg={result['svg']} "
        f"png={result['png_ok']} png_fail={result['png_fail']}"
    )
    for path in result["written"]:
        print(path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
