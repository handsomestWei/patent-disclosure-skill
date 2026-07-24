"""专利附图抽取：图注锚定 + bbox 裁切 + 质量门。

能力：
  - 检测「图 N / FIG. N」等图注
  - 按 bbox（矢量+嵌入图并集）从页面 pixmap 裁切 PNG
  - 轻量质量门 usable / review / reject
  - 决策 insert | placeholder
  - 回退：无图注页时整页内容区裁切；仍保留 xref 抽图作补充
"""
from __future__ import annotations

import re
from pathlib import Path

FIGURE_RENDER_DPI = 200
MIN_FIGURE_HEIGHT_PT = 50
MIN_FIGURE_WIDTH_PT = 80

# 专利 / 中英图号（行首或【】内）
CAPTION_RE = re.compile(
    r"^(?:"
    r"【?\s*(?:图|附图)\s*([0-9]+[A-Za-z]?)\s*】?"
    r"|FIG(?:URE)?\.?\s*([0-9]+[A-Za-z]?)"
    r"|Fig\.?\s*([0-9]+[A-Za-z]?)"
    r")(?=$|[\s:：.。,\、|—–\-])",
    re.IGNORECASE,
)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _rect_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    return _rect_area((x0, y0, x1, y1))


def _clip_to_page(
    bbox: tuple[float, float, float, float],
    page_rect,
    *,
    padding: float = 4.0,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    x0 = max(page_rect.x0, x0 - padding)
    y0 = max(page_rect.y0, y0 - padding)
    x1 = min(page_rect.x1, x1 + padding)
    y1 = min(page_rect.y1, y1 + padding)
    return (x0, y0, x1, y1)


def _collect_xref_rects(page) -> list[tuple[float, float, float, float]]:
    import fitz  # type: ignore

    rects: list[tuple[float, float, float, float]] = []
    for img_info in page.get_images(full=True):
        xref = int(img_info[0])
        try:
            img_rects = page.get_image_rects(xref)
        except Exception:
            continue
        for r in img_rects:
            if r.is_empty or r.is_infinite:
                continue
            rects.append((r.x0, r.y0, r.x1, r.y1))
    return rects


def _collect_drawing_rects(page) -> list[tuple[float, float, float, float]]:
    import fitz  # type: ignore

    rects: list[tuple[float, float, float, float]] = []
    try:
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r is None:
                continue
            rect = fitz.Rect(r)
            if rect.is_empty or rect.is_infinite:
                continue
            if rect.width < 8 or rect.height < 8:
                continue
            rects.append((rect.x0, rect.y0, rect.x1, rect.y1))
    except Exception:
        pass
    return rects


def _visual_signal_for_bbox(page, bbox: tuple[float, float, float, float]) -> tuple[int, float]:
    crop_area = _rect_area(bbox)
    if crop_area <= 0:
        return 0, 0.0
    count = 0
    visual_area = 0.0
    for rect in _collect_xref_rects(page) + _collect_drawing_rects(page):
        area = _intersection_area(rect, bbox)
        if area <= 0:
            continue
        count += 1
        visual_area += area
    return count, min(1.0, visual_area / crop_area)


def _classify_visual_quality(
    *,
    page_coverage_ratio: float,
    visual_rect_count: int,
    visual_body_ratio: float,
    paragraph_text_chars: int,
) -> dict:
    reasons: list[str] = []
    if paragraph_text_chars >= 500 and visual_body_ratio < 0.12:
        reasons.append("large_text_block_suspected")
    if page_coverage_ratio >= 0.92 and paragraph_text_chars >= 200:
        reasons.append("oversized_page_crop")
    if visual_rect_count <= 0 and visual_body_ratio < 0.02:
        reasons.append("low_visual_body_ratio")

    if any(
        r in reasons
        for r in ("large_text_block_suspected", "oversized_page_crop", "low_visual_body_ratio")
    ):
        status = "reject"
    elif visual_rect_count == 0 or visual_body_ratio < 0.06:
        if "low_visual_body_ratio" not in reasons:
            reasons.append("low_visual_body_ratio")
        status = "review"
    else:
        status = "usable"
    return {"status": status, "reasons": reasons}


def _count_text_chars_in_bbox(page, bbox: tuple[float, float, float, float]) -> int:
    import fitz  # type: ignore

    chars = 0
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        bb = tuple(block["bbox"])
        if _intersection_area(bb, bbox) <= 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars += len(span.get("text", "") or "")
    return chars


def _find_caption_blocks(page) -> list[dict]:
    import fitz  # type: ignore

    anchors: list[dict] = []
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            line_text = "".join(s.get("text", "") for s in spans).strip()
            match = CAPTION_RE.match(line_text)
            if not match:
                # 行内「如图1所示」跳过；允许较长图注「图1 为…结构示意图」
                m2 = re.search(
                    r"(?:^|[\s　【])((?:图|附图)\s*[0-9]+[A-Za-z]?|FIG(?:URE)?\.?\s*[0-9]+[A-Za-z]?)\s*[:：]?",
                    line_text,
                    re.I,
                )
                if not m2:
                    continue
                # 过长且「如图」句式 → 正文引用非图注
                if "如图" in line_text[:4] or "如附图" in line_text[:5]:
                    continue
                if len(line_text) > 120 and not CAPTION_RE.match(line_text[:20]):
                    continue
                label_raw = m2.group(1)
                num = re.search(r"[0-9]+[A-Za-z]?", label_raw)
                label = f"图{num.group(0)}" if num else label_raw
            else:
                num = next(g for g in match.groups() if g)
                label = f"图{num}"
            bb = tuple(line["bbox"])
            anchors.append(
                {
                    "label": label,
                    "kind": "figure",
                    "bbox": bb,
                    "line_text": line_text,
                }
            )
    anchors.sort(key=lambda a: (a["bbox"][1], a["bbox"][0]))
    # 同页同图号保留多条（不同位置），避免只留最后一处
    return anchors


def _union_rects(
    rects: list[tuple[float, float, float, float]],
    caption_bbox: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    if not rects:
        return None
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    x0 = min(x0, caption_bbox[0])
    x1 = max(x1, caption_bbox[2])
    y1 = max(y1, caption_bbox[3])
    return (x0, y0, x1, y1)


def _estimate_bbox_near_caption(
    page,
    caption_anchor: dict,
    prev_anchor: dict | None,
    next_anchor: dict | None,
    page_rect,
) -> tuple[float, float, float, float] | None:
    """专利附图：图注上下均可；优先同栏矢量/位图；失败则取图注邻近内容带。"""
    cy0, cy1 = caption_anchor["bbox"][1], caption_anchor["bbox"][3]
    cx0, cx1 = caption_anchor["bbox"][0], caption_anchor["bbox"][2]
    cx_mid = (cx0 + cx1) / 2.0
    page_w = page_rect.x1 - page_rect.x0
    # 双栏：以图注中心 ±0.4 页宽为同栏窗口
    col_half = max(page_w * 0.4, (cx1 - cx0) + 36)
    col_x0 = max(page_rect.x0, cx_mid - col_half)
    col_x1 = min(page_rect.x1, cx_mid + col_half)

    upper = prev_anchor["bbox"][3] + 2.0 if prev_anchor else page_rect.y0 + 36
    lower = next_anchor["bbox"][1] - 2.0 if next_anchor else page_rect.y1 - 36

    all_rects = _collect_xref_rects(page) + _collect_drawing_rects(page)

    def _in_column(r: tuple[float, float, float, float]) -> bool:
        rm = (r[0] + r[2]) / 2.0
        return col_x0 <= rm <= col_x1

    above: list[tuple[float, float, float, float]] = []
    for r in all_rects:
        if not _in_column(r):
            continue
        mid = (r[1] + r[3]) / 2.0
        if upper <= mid <= cy0 + 8:
            above.append((r[0], r[1], r[2], min(r[3], cy0 - 1)))

    below: list[tuple[float, float, float, float]] = []
    for r in all_rects:
        if not _in_column(r):
            continue
        mid = (r[1] + r[3]) / 2.0
        if cy1 - 8 <= mid <= lower:
            below.append((r[0], max(r[1], cy1 + 1), r[2], r[3]))

    bbox = None
    above_u = _union_rects(above, caption_anchor["bbox"]) if above else None
    below_u = _union_rects(below, caption_anchor["bbox"]) if below else None
    if above_u and below_u:
        bbox = above_u if _rect_area(above_u) >= _rect_area(below_u) else below_u
    elif above_u:
        bbox = above_u
    elif below_u:
        bbox = below_u

    if bbox is None:
        # 自适应条带：默认 ±180pt，有邻近图注时收紧；上限 ±280pt
        band = 180.0
        if prev_anchor or next_anchor:
            band = 120.0
        y0 = max(upper, cy0 - min(280.0, band))
        y1 = min(lower, cy1 + min(280.0, band))
        bbox = (col_x0, y0, col_x1, y1)

    # 裁剪到栏宽，减少吃进邻栏正文
    x0, y0, x1, y1 = bbox
    bbox = (max(x0, col_x0 - 8), y0, min(x1, col_x1 + 8), y1)
    bbox = _clip_to_page(bbox, page_rect)
    if bbox[2] - bbox[0] < MIN_FIGURE_WIDTH_PT or bbox[3] - bbox[1] < MIN_FIGURE_HEIGHT_PT:
        return None
    return bbox


def _page_content_bbox(page_rect) -> tuple[float, float, float, float]:
    """无图注时：去掉大致页眉页脚的内容区。"""
    margin_x = 18
    margin_top = 40
    margin_bottom = 40
    return (
        page_rect.x0 + margin_x,
        page_rect.y0 + margin_top,
        page_rect.x1 - margin_x,
        page_rect.y1 - margin_bottom,
    )


def _render_crop(page, bbox: tuple[float, float, float, float], dpi: int) -> bytes:
    import fitz  # type: ignore

    clip = fitz.Rect(*bbox)
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    return pix.tobytes("png")


def _safe_filename(page_number: int, label: str, used: set[str]) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", label).strip("_") or "fig"
    base = f"page_{page_number:03d}_{safe}.png"
    if base not in used:
        used.add(base)
        return base
    i = 2
    while True:
        cand = f"page_{page_number:03d}_{safe}_{i}.png"
        if cand not in used:
            used.add(cand)
            return cand
        i += 1


def _decision_from_quality(status: str, *, include_review: bool = False) -> str:
    if status == "usable":
        return "insert"
    if include_review and status == "review":
        return "insert"
    return "placeholder"


def extract_figure_level(
    page,
    page_number: int,
    out_dir: Path,
    *,
    dpi: int = FIGURE_RENDER_DPI,
    include_review: bool = False,
) -> list[dict]:
    """图注锚定裁切；无图注且有明显矢量/位图时整页内容区一裁。"""
    page_rect = page.rect
    anchors = _find_caption_blocks(page)
    used: set[str] = set()
    assets: list[dict] = []

    if anchors:
        for idx, anchor in enumerate(anchors):
            prev_a = anchors[idx - 1] if idx else None
            next_a = anchors[idx + 1] if idx + 1 < len(anchors) else None
            bbox = _estimate_bbox_near_caption(page, anchor, prev_a, next_a, page_rect)
            if bbox is None:
                continue
            try:
                png = _render_crop(page, bbox, dpi)
            except Exception:
                continue
            fname = _safe_filename(page_number, anchor["label"], used)
            (out_dir / fname).write_bytes(png)
            vcount, vratio = _visual_signal_for_bbox(page, bbox)
            coverage = _rect_area(bbox) / max(_rect_area(
                (page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1)
            ), 1.0)
            text_chars = _count_text_chars_in_bbox(page, bbox)
            quality = _classify_visual_quality(
                page_coverage_ratio=coverage,
                visual_rect_count=vcount,
                visual_body_ratio=vratio,
                paragraph_text_chars=text_chars,
            )
            decision = _decision_from_quality(
                quality["status"], include_review=include_review
            )
            label = anchor["label"]
            assets.append(
                {
                    "id": f"fig_{label}_{page_number}_{idx}",
                    "page": page_number,
                    "label": label,
                    "caption_text": _normalize_ws(anchor["line_text"]),
                    "filename": fname,
                    "relative_path": f"images/{fname}",
                    "bytes": len(png),
                    "extraction_level": "figure",
                    "bbox_pt": list(bbox),
                    "quality_signals": quality,
                    "decision": decision,
                    "suggested_callout": _callout_for(label, page_number, fname, decision, quality),
                    "suggested_embed": f"![[images/{fname}]]\n*{label}（第 {page_number} 页）*",
                }
            )
        return assets

    # 无图注：若有足够矢量/位图，裁整页内容区
    rects = _collect_xref_rects(page) + _collect_drawing_rects(page)
    if len(rects) < 2:
        return []
    bbox = _page_content_bbox(page_rect)
    vcount, vratio = _visual_signal_for_bbox(page, bbox)
    if vcount < 2 or vratio < 0.04:
        return []
    try:
        png = _render_crop(page, bbox, dpi)
    except Exception:
        return []
    label = f"页{page_number}"
    fname = _safe_filename(page_number, label, used)
    (out_dir / fname).write_bytes(png)
    quality = _classify_visual_quality(
        page_coverage_ratio=0.85,
        visual_rect_count=vcount,
        visual_body_ratio=vratio,
        paragraph_text_chars=_count_text_chars_in_bbox(page, bbox),
    )
    # 无图号整页裁：默认 review/placeholder，避免误当正式附图
    if quality["status"] == "usable":
        quality = {"status": "review", "reasons": quality["reasons"] + ["no_caption_page_crop"]}
    decision = _decision_from_quality(quality["status"], include_review=include_review)
    assets.append(
        {
            "id": f"fig_page_{page_number}",
            "page": page_number,
            "label": label,
            "caption_text": "",
            "filename": fname,
            "relative_path": f"images/{fname}",
            "bytes": len(png),
            "extraction_level": "page",
            "bbox_pt": list(bbox),
            "quality_signals": quality,
            "decision": decision,
            "suggested_callout": _callout_for(label, page_number, fname, decision, quality),
            "suggested_embed": f"![[images/{fname}]]\n*第 {page_number} 页附图区域（无图号）*",
        }
    )
    return assets


def extract_xref_fallback(
    doc,
    page,
    page_number: int,
    out_dir: Path,
    *,
    min_bytes: int = 8000,
    max_per_page: int = 2,
) -> list[dict]:
    """Legacy xref 抽图，决策一律 placeholder（需人工核对）。"""
    items: list[dict] = []
    seen = 0
    for img_index, img in enumerate(page.get_images(full=True)):
        if seen >= max_per_page:
            break
        xref = img[0]
        try:
            base = doc.extract_image(xref)
        except Exception:
            continue
        data = base.get("image", b"")
        if len(data) < min_bytes:
            continue
        ext = base.get("ext", "png")
        fname = f"page_{page_number:03d}_xref_{img_index + 1:02d}.{ext}"
        (out_dir / fname).write_bytes(data)
        quality = {"status": "review", "reasons": ["xref_fragment"]}
        items.append(
            {
                "id": f"xref_p{page_number}_{img_index + 1}",
                "page": page_number,
                "label": f"嵌入图{img_index + 1}",
                "caption_text": "",
                "filename": fname,
                "relative_path": f"images/{fname}",
                "bytes": len(data),
                "extraction_level": "xref",
                "quality_signals": quality,
                "decision": "placeholder",
                "suggested_callout": _callout_for(
                    f"嵌入图{img_index + 1}", page_number, fname, "placeholder", quality
                ),
                "suggested_embed": "",
            }
        )
        seen += 1
    return items


def _callout_for(
    label: str,
    page: int,
    fname: str,
    decision: str,
    quality: dict,
) -> str:
    status = quality.get("status", "review")
    reasons = ", ".join(quality.get("reasons") or []) or "—"
    if decision == "insert":
        state = f"可插入；质量={status}"
    else:
        state = f"占位；质量={status}；原因={reasons}"
    return (
        f"> [!figure] {label}\n"
        f"> 建议位置：特征—附图对照\n"
        f"> 页码：{page}\n"
        f"> 当前状态：{state}；文件 `{fname}`"
    )


def extract_patent_pdf_figures(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = FIGURE_RENDER_DPI,
    min_xref_bytes: int = 8000,
    prefer_figure_level: bool = True,
    include_review: bool = False,
) -> dict:
    """主入口：返回 manifest dict。"""
    import fitz  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    figures: list[dict] = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        if prefer_figure_level:
            fig_assets = extract_figure_level(
                page, page_no, out_dir, dpi=dpi, include_review=include_review
            )
            figures.extend(fig_assets)
            if fig_assets:
                continue
        figures.extend(
            extract_xref_fallback(
                doc, page, page_no, out_dir, min_bytes=min_xref_bytes
            )
        )
    doc.close()

    insert_count = sum(1 for f in figures if f.get("decision") == "insert")
    return {
        "source_pdf": str(pdf_path),
        "count": len(figures),
        "insert_count": insert_count,
        "placeholder_count": len(figures) - insert_count,
        "include_review": include_review,
        "figures": figures,
    }
