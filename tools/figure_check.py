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


def find_chapter_13(text: str) -> Section | None:
    for section in find_sections(text):
        title = re.sub(r"\s+", "", section.title)
        if re.match(r"(13|十三)[.、．]?", title) and "附图" in title:
            return section
    return None


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


def extract_figure_table_numbers(chapter_13: str) -> set[str]:
    if "附图说明" not in chapter_13:
        return set()
    start = chapter_13.find("附图说明")
    end = chapter_13.find("附图标记表", start)
    table_text = chapter_13[start : end if end != -1 else len(chapter_13)]
    return extract_figure_refs(table_text)


def caption_exists_for(chapter_13: str, image: FigureImage, chapter_base_line: int) -> bool:
    lines = chapter_13.splitlines()
    idx = max(0, image.line_index - chapter_base_line)
    for line in lines[idx + 1 : idx + 5]:
        stripped = line.strip()
        if not stripped:
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

    outside_images = extract_images(outside)
    for image in outside_images:
        errors.append(f"outside chapter 13 image reference at line {image.line_index}: {image.path}")

    chapter_base_line = line_number(text, chapter_13_section.start)
    chapter_images = extract_images(chapter_13, base_line=chapter_base_line)
    if not chapter_images:
        errors.append("chapter 13 has no markdown image references")

    defined_by_images = {image.number for image in chapter_images if image.number}
    described_figures = extract_figure_table_numbers(chapter_13)
    external_refs = extract_figure_refs(outside)

    for ref in sorted(external_refs - defined_by_images - described_figures):
        errors.append(f"undefined external figure reference: {ref}")

    for image in chapter_images:
        if not image.number:
            errors.append(f"image lacks figure number at line {image.line_index}: {image.path}")
            continue
        if not caption_exists_for(chapter_13, image, chapter_base_line):
            errors.append(f"missing caption for {image.number}")
        if image.number not in described_figures:
            errors.append(f"{image.number} missing from 附图说明")
        if not is_external_path(image.path):
            image_path = (path.parent / image.path).resolve()
            if not image_path.exists():
                errors.append(f"missing image file for {image.number}: {image.path}")

    for figure in sorted(described_figures - defined_by_images):
        errors.append(f"{figure} appears in 附图说明 but has no image")

    if "附图标记表" not in chapter_13:
        errors.append("missing 附图标记表")

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
