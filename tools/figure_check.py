#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.MULTILINE)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
FIGURE_RE = re.compile(r"图(?:示)?\s*0*(\d+)")


@dataclass(frozen=True)
class Section:
    title: str
    level: int
    start: int
    end: int


@dataclass(frozen=True)
class FigureImage:
    number: str
    alt: str
    path: str
    line_index: int


def normalize_figure(match_text: str) -> str:
    found = FIGURE_RE.search(match_text)
    if not found:
        return ""
    return f"图{int(found.group(1))}"


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def find_sections(text: str) -> list[Section]:
    matches = list(HEADING_RE.finditer(text))
    sections: list[Section] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        end = len(text)
        for next_match in matches[i + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        sections.append(Section(title=match.group(2).strip(), level=level, start=match.start(), end=end))
    return sections


def find_section_by_number(text: str, number: int, keyword: str) -> Section | None:
    for section in find_sections(text):
        title = re.sub(r"\s+", "", section.title)
        pattern = rf"({number}|{_chinese_num(number)})[.、．]?"
        if re.match(pattern, title) and keyword in title:
            return section
    return None


def _chinese_num(n: int) -> str:
    mapping = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七",
               8: "八", 9: "九", 10: "十", 11: "十一", 12: "十二", 13: "十三",
               14: "十四", 15: "十五"}
    return mapping.get(n, str(n))


def find_chapter_5(text: str) -> Section | None:
    return find_section_by_number(text, 5, "代表")


def find_chapter_13(text: str) -> Section | None:
    return find_section_by_number(text, 13, "附图")


def extract_images(section_text: str, base_line: int = 1) -> list[FigureImage]:
    images: list[FigureImage] = []
    for match in IMAGE_RE.finditer(section_text):
        alt, path = match.group(1).strip(), match.group(2).strip()
        number = normalize_figure(alt) or normalize_figure(path)
        images.append(
            FigureImage(
                number=number,
                alt=alt,
                path=path,
                line_index=base_line + line_number(section_text, match.start()) - 1,
            )
        )
    return images


def extract_figure_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for match in FIGURE_RE.finditer(text):
        prefix = text[max(0, match.start() - 3) : match.start()]
        if "第" in prefix:
            continue
        refs.add(f"图{int(match.group(1))}")
    return refs


def extract_captioned_figures(chapter_13: str) -> set[str]:
    captioned: set[str] = set()
    for match in re.finditer(r"图示\s*0*(\d+)\s*[：:]", chapter_13):
        captioned.add(f"图{int(match.group(1))}")
    return captioned


def extract_key_marker_figures(chapter_13: str) -> set[str]:
    marked: set[str] = set()
    for match in re.finditer(r"图中关键附图标记", chapter_13):
        preceding = chapter_13[: match.start()]
        prev_caption = re.findall(r"图示\s*0*(\d+)\s*[：:]", preceding)
        if prev_caption:
            marked.add(f"图{int(prev_caption[-1])}")
    return marked


def caption_exists_for(chapter_13: str, image: FigureImage, chapter_base_line: int) -> bool:
    lines = chapter_13.splitlines()
    idx = max(0, image.line_index - chapter_base_line)
    for line in lines[idx + 1 : idx + 5]:
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        return normalize_figure(stripped) == image.number and ("：" in stripped or ":" in stripped)
    return False


def is_external_path(path: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", path))


def check_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    chapter_13_section = find_chapter_13(text)
    errors: list[str] = []

    if chapter_13_section is None:
        return ["missing chapter 13 figures section"]

    chapter_13 = text[chapter_13_section.start : chapter_13_section.end]
    outside = text[: chapter_13_section.start] + "\n" + text[chapter_13_section.end :]

    chapter_5_section = find_chapter_5(text)
    ch5_images = extract_images(text[chapter_5_section.start : chapter_5_section.end],
                                base_line=line_number(text, chapter_5_section.start)) if chapter_5_section else []
    # Representative figure in chapter 5 must match one in chapter 13
    ch13_paths = {img.path for img in extract_images(chapter_13)}

    chapter_base_line = line_number(text, chapter_13_section.start)
    chapter_images = extract_images(chapter_13, base_line=chapter_base_line)
    if not chapter_images:
        errors.append("chapter 13 has no markdown image references")

    defined_by_images = {image.number for image in chapter_images if image.number}
    captioned_figures = extract_captioned_figures(chapter_13)
    key_marker_figures = extract_key_marker_figures(chapter_13)
    external_refs = extract_figure_refs(outside)

    # Image outside chapter 13 — only chapter 5 representative figure (same path as ch13) is allowed
    outside_images = extract_images(outside)
    ch5_start = line_number(text, chapter_5_section.start) if chapter_5_section else -1
    ch5_end = line_number(text, chapter_5_section.end) if chapter_5_section else -1
    for image in outside_images:
        in_ch5 = ch5_start <= image.line_index <= ch5_end
        if in_ch5 and image.path in ch13_paths:
            continue  # Allowed: representative figure in chapter 5
        errors.append(f"outside chapter 13 image reference at line {image.line_index}: {image.path}")

    # Each chapter 5 representative figure must have a chapter 13 counterpart
    for image in ch5_images:
        if image.path not in ch13_paths:
            errors.append(f"chapter 5 representative figure has no chapter 13 match: {image.path}")

    # Check: all external figure references must have a corresponding image in chapter 13
    for ref in sorted(external_refs - defined_by_images):
        errors.append(f"undefined external figure reference: {ref}")

    for image in chapter_images:
        if not image.number:
            errors.append(f"image lacks figure number at line {image.line_index}: {image.path}")
            continue
        if not caption_exists_for(chapter_13, image, chapter_base_line):
            errors.append(f"missing caption for {image.number} (expect 图示{image.number[-1]}：...)")
        if image.number not in captioned_figures:
            errors.append(f"{image.number} missing 图示{image.number[-1]} caption line")
        if image.number not in key_marker_figures:
            errors.append(f"{image.number} missing 图中关键附图标记 section")
        if not is_external_path(image.path):
            image_path = (path.parent / image.path).resolve()
            if not image_path.exists():
                errors.append(f"missing image file for {image.number}: {image.path}")

    for figure in sorted(captioned_figures - defined_by_images):
        errors.append(f"{figure} has 图示 caption but no image file reference")

    # No legacy 附图说明 or 附图标记表 tables
    if "附图说明" in chapter_13 and "|" in chapter_13:
        idx = chapter_13.find("附图说明")
        nearby = chapter_13[idx : idx + 300] if idx != -1 else ""
        if "|---" in nearby or "| 图号" in nearby:
            errors.append("legacy 附图说明 table found — use per-image captions (图示N：...) instead")
    if "附图标记表" in chapter_13:
        idx = chapter_13.find("附图标记表")
        nearby = chapter_13[idx : idx + 300] if idx != -1 else ""
        if "|---" in nearby or "| 附图标记" in nearby:
            errors.append("legacy 附图标记表 table found — use per-image 图中关键附图标记 instead")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check chapter 13 figure references in a patent disclosure Markdown file.")
    parser.add_argument("markdown", type=Path, help="Disclosure Markdown file to check")
    args = parser.parse_args(argv)

    errors = check_markdown(args.markdown)
    if errors:
        print("FIGURE_CHECK_FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("FIGURE_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
