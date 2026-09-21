#!/usr/bin/env python
"""
将 PDF（.pdf）按页导出为 Markdown，并抽取页面中的嵌入图片，便于 Step 2 扫描与 Agent Read。

依赖 pdfplumber（文本抽取）和 PyMuPDF（图片抽取）（见仓库根目录 requirements.txt）。

用法:
  python pdf_to_md.py --input document.pdf --output outputs/case/document.md
  python pdf_to_md.py -i a.pdf -o b/out.md --media-dir b/slide_images

默认图片目录：与输出 .md 同级的「{md 文件名}_media/」。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_mask import content_remove_sensitive


def _require_deps():
    try:
        import pdfplumber
    except ImportError:
        print(
            "缺少依赖 pdfplumber。请在技能根目录执行: pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        import fitz
    except ImportError:
        print(
            "缺少依赖 PyMuPDF。请在技能根目录执行: pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    return pdfplumber, fitz


def _rel_media_path(out_file: Path, media_file: Path) -> str:
    try:
        return media_file.relative_to(out_file.parent).as_posix()
    except ValueError:
        return media_file.as_posix()


def _run(input_pdf: Path, output_md: Path, media_dir: Path | None) -> int:
    pdfplumber, fitz = _require_deps()

    if not input_pdf.is_file():
        print(f"输入文件不存在: {input_pdf}", file=sys.stderr)
        return 2
    suf = input_pdf.suffix.lower()
    if suf != ".pdf":
        print("警告: 期望 .pdf 文件。", file=sys.stderr)

    output_md = output_md.resolve()
    output_md.parent.mkdir(parents=True, exist_ok=True)

    if media_dir is None:
        media_dir = output_md.parent / f"{output_md.stem}_media"
    else:
        media_dir = media_dir.resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"<!-- 由 pdf_to_md.py 自 {input_pdf.name} 转换，勿手改本行元信息 -->\n"
    ]
    img_counter = [0]

    try:
        with pdfplumber.open(input_pdf) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                lines.append(f"\n## 第 {page_num} 页\n")
                text = page.extract_text()
                if text:
                    lines.append(text)
                    lines.append("\n\n")
    except Exception as e:
        print(f"无法读取 PDF 文本: {e}", file=sys.stderr)

    try:
        doc = fitz.open(input_pdf)
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            image_list = page.get_images(full=True)
            for image in image_list:
                try:
                    xref = image[0]
                    base_image = doc.extract_image(xref)
                    ext = (base_image.get("ext") or "png").lower()
                    if ext == "jpeg":
                        ext = "jpg"
                    img_counter[0] += 1
                    fname = f"slide{page_idx + 1:02d}_img{img_counter[0]:04d}.{ext}"
                    out_img = media_dir / fname
                    out_img.write_bytes(base_image["image"])
                    rel = _rel_media_path(output_md, out_img)
                    lines.append(f"\n![]({rel})\n")
                except Exception as e:
                    print(f"警告: 第 {page_idx + 1} 页抽取图片失败: {e}", file=sys.stderr)
        doc.close()
    except Exception as e:
        print(f"无法读取 PDF 图片: {e}", file=sys.stderr)

    body = "".join(lines).rstrip() + "\n"
    body = content_remove_sensitive(body)
    output_md.write_text(body, encoding="utf-8")

    print(f"已写入: {output_md}")
    print(f"图片目录: {media_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="PDF → Markdown + 抽取图片")
    p.add_argument("-i", "--input", required=True, type=Path, help="输入 .pdf 路径")
    p.add_argument("-o", "--output", required=True, type=Path, help="输出 .md 路径")
    p.add_argument(
        "--media-dir",
        type=Path,
        default=None,
        help="图片输出目录（默认：与 .md 同级的 {md 主名}_media）",
    )
    args = p.parse_args()
    return _run(args.input, args.output, args.media_dir)


if __name__ == "__main__":
    raise SystemExit(main())