#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生图后处理：转真黑白、按内容裁切、写 DPI，可选写 SVG 包装与摘要附图副本。

只做后处理，不绘制任何内容（地位同 codex-ppt 的 chroma-key 去底）。用于
AI 生成的申请附图 / 线稿入文前统一成"白底纯黑线、无整页留白"的版式。

  python tools/bw_normalize.py --input ai/图1_raw.png --out figures/图1.png --svg figures/图1.svg
  python tools/bw_normalize.py --input a.png --out a.jpg --dpi 300      # 外观视图：JPEG
  python tools/bw_normalize.py --input a.png --out 图2.png --abstract-out figures/摘要附图.png

stdout 前缀 ``BW_NORMALIZE:``；报告 ``color_ratio`` / ``gray_ratio`` 供读图 QA 参考
（原图彩色或大面积灰阶说明模型没守住黑白约束，应重出而不是硬转）。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

PREFIX = "BW_NORMALIZE:"
DEFAULT_THRESHOLD = 200
DEFAULT_MARGIN = 24
DEFAULT_DPI = 300
SATURATION_FLOOR = 60
GRAY_BAND = (60, 200)


def _load_pillow():
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError(
            "bw_normalize 需要 Pillow；征得用户同意后 "
            "`python -m pip install -r tools/requirements-image.txt`"
        ) from exc
    return Image, ImageOps


def _ratio(hist: list[int], lo: int, hi: int) -> float:
    total = sum(hist) or 1
    return sum(hist[lo:hi]) / total


def _to_white_rgb(img):
    """RGB on white: transparent pixels become white (models may return RGBA with dark RGB under alpha=0)."""
    Image, _ = _load_pillow()
    if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return img.convert("RGB")


def flatten_alpha(path: Path) -> bool:
    """Flatten a transparent image onto white in place. Returns True when the file changed.

    Best-effort: without Pillow, or for a file Pillow cannot read, nothing is changed.
    """
    try:
        Image, _ = _load_pillow()
    except RuntimeError:
        return False
    path = Path(path)
    try:
        img = Image.open(path)
        img.load()
    except (OSError, Image.UnidentifiedImageError):
        return False
    with img:
        has_alpha = img.mode in ("RGBA", "LA", "P") or "transparency" in img.info
        if not has_alpha:
            return False
        fmt = img.format or "PNG"
        rgb = _to_white_rgb(img)
    rgb.save(path, format=fmt)
    return True


def wrapper_svg(image_href: str, width_mm: float, height_mm: float) -> str:
    href = html.escape(quote(image_href), quote=True)
    w = f"{width_mm:.2f}"
    h = f"{height_mm:.2f}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">'
        f'<image x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" '
        f'xlink:href="{href}"/></svg>\n'
    )


def normalize(
    src: Path,
    out: Path,
    *,
    threshold: int = DEFAULT_THRESHOLD,
    margin: int = DEFAULT_MARGIN,
    dpi: int = DEFAULT_DPI,
    svg: Path | None = None,
    abstract_out: Path | None = None,
) -> dict[str, Any]:
    Image, ImageOps = _load_pillow()
    src = Path(src)
    out = Path(out)
    if not src.is_file():
        raise FileNotFoundError(src)
    with Image.open(src) as img:
        img.load()
        rgb = _to_white_rgb(img)
    sat_hist = rgb.convert("HSV").getchannel("S").histogram()
    gray = rgb.convert("L")
    color_ratio = _ratio(sat_hist, SATURATION_FLOOR, 256)
    gray_ratio = _ratio(gray.histogram(), GRAY_BAND[0], GRAY_BAND[1])

    bw = gray.point(lambda v: 255 if v >= threshold else 0, mode="L")
    bbox = ImageOps.invert(bw).getbbox()
    if bbox is None:
        raise ValueError(f"{src} 二值化后没有墨线（全白），检查生图结果或调低 --threshold")
    left, top, right, bottom = bbox
    w, h = bw.size
    crop = (max(0, left - margin), max(0, top - margin), min(w, right + margin), min(h, bottom + margin))
    bw = bw.crop(crop)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        bw.save(out, format="JPEG", quality=95, dpi=(dpi, dpi))
    else:
        bw.convert("1").save(out, format="PNG", dpi=(dpi, dpi))

    width_mm = bw.size[0] / dpi * 25.4
    height_mm = bw.size[1] / dpi * 25.4
    written = [str(out)]
    if svg is not None:
        svg = Path(svg)
        svg.parent.mkdir(parents=True, exist_ok=True)
        href = Path(os.path.relpath(out, svg.parent)).as_posix()
        svg.write_text(wrapper_svg(href, width_mm, height_mm), encoding="utf-8")
        written.append(str(svg))
    if abstract_out is not None:
        abstract_out = Path(abstract_out)
        abstract_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, abstract_out)
        written.append(str(abstract_out))
    return {
        "ok": True,
        "input": str(src),
        "output": str(out),
        "size_px": list(bw.size),
        "size_mm": [round(width_mm, 1), round(height_mm, 1)],
        "dpi": dpi,
        "color_ratio": round(color_ratio, 4),
        "gray_ratio": round(gray_ratio, 4),
        "written": written,
    }


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from stdio_utf8 import ensure_utf8_stdio

    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="生图后处理：真黑白 + 按内容裁切 + DPI")
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path, help=".png 存 1-bit；.jpg 存灰度 JPEG")
    ap.add_argument("--svg", type=Path, help="另写内嵌该 PNG 的 SVG 包装")
    ap.add_argument("--abstract-out", type=Path, help="另存一份（如 摘要附图.png）")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--margin", type=int, default=DEFAULT_MARGIN)
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = ap.parse_args(argv)
    if not 1 <= args.threshold <= 254:
        ap.error("--threshold 须在 1..254")
    if not 72 <= args.dpi <= 1200:
        ap.error("--dpi 须在 72..1200")
    try:
        result = normalize(
            args.input,
            args.out,
            threshold=args.threshold,
            margin=max(0, args.margin),
            dpi=args.dpi,
            svg=args.svg,
            abstract_out=args.abstract_out,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"{PREFIX} ok=0 error={exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"{PREFIX} ok=1 out={result['output']} color_ratio={result['color_ratio']} "
        f"gray_ratio={result['gray_ratio']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
