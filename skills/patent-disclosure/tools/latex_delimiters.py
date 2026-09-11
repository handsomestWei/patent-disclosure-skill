#!/usr/bin/env python
"""扫 Markdown 里「普通括号包住 LaTeX」的行内公式（Word 不会当成公式）。

``md_to_docx.py`` 只认 ``\\(...\\)`` / ``$...$``。写成 ``(M_{\\mathrm{total}})`` 会原样进正文。
Markdown 预览常把 ``\\(`` 显示成 ``(``，写稿时不要据此删反斜杠。

围栏代码块与行内 `` `...` `` 不扫（避免文档反例、mermaid 源码误报）。

用法：
  python tools/latex_delimiters.py -i disclosure.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from stdio_utf8 import ensure_utf8_stdio

# 括号内出现这些命令，几乎可以断定是 LaTeX 而不是中文夹注。
_LATEX_CMD = (
    r"\\(?:mathrm|operatorname|mathbf|mathit|text|frac|sqrt|left|right"
    r"|leq|geq|leqslant|geqslant|le\b|ge\b|cdot|times"
    r"|alpha|beta|gamma|delta|lambda|mu|sigma|omega|varepsilon|varphi"
    r"|sum|prod|int|max|min|tag|quad|qquad|overline|underline"
    r"|,|;|!)"
)

# ``(M_{\mathrm{total}})`` / ``(m_{\mathrm{silica}}=60\,\mathrm{g})``
_BARE_PAREN_CMD = re.compile(
    rf"(?<!\\)\((?=([^()\n]{{0,200}}{_LATEX_CMD}))([^()\n]{{1,200}})\)"
)

# ``(M_{total})``：下标花括号、但还没写成 ``\(``
_BARE_PAREN_SUB = re.compile(r"(?<!\\)\([A-Za-z][A-Za-z0-9]*_\{[^()\n]{0,120}\)")

_INLINE_CODE = re.compile(r"`[^`]*`")
_FENCE_OPEN = re.compile(r"^(```|~~~)")

# 行内公式 \(...\) 内部允许合法 LaTeX 嵌套（含 \bigl( ... \bigr) 等），不扫。
# 逐行处理，\( 与最近的 \) 配对即可；非贪婪避免跨段匹配。
_INLINE_MATH = re.compile(r"\\\((?:[^\\]|\\.)*?\\\)")


@dataclass(frozen=True)
class BareParenHit:
    line: int
    snippet: str


def _mask_inline_code(line: str) -> str:
    return _INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


def _mask_inline_math(line: str) -> str:
    return _INLINE_MATH.sub(lambda m: " " * len(m.group(0)), line)


def find_bare_paren_latex(md: str) -> list[BareParenHit]:
    """返回普通括号包 LaTeX 的命中（1-based 行号）。"""
    hits: list[BareParenHit] = []
    in_fence = False
    for i, raw in enumerate((md or "").splitlines(), 1):
        stripped = raw.lstrip()
        if _FENCE_OPEN.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _mask_inline_code(_mask_inline_math(raw))
        seen: set[tuple[int, int]] = set()
        for cre in (_BARE_PAREN_CMD, _BARE_PAREN_SUB):
            for m in cre.finditer(line):
                span = m.span()
                if span in seen:
                    continue
                seen.add(span)
                snippet = m.group(0).strip()
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                hits.append(BareParenHit(line=i, snippet=snippet))
    return hits


def format_hits_report(hits: list[BareParenHit]) -> str:
    n = len(hits)
    lines = [f"LATEX_DELIM: hits={n}"]
    if n:
        lines.append(
            "行内公式须用 \\(...\\) 或 $...$，不要用普通括号包住 \\mathrm / \\, / _{ }。"
            " Markdown 预览里 \\( 看起来像 (，勿删反斜杠。"
            " 改正后须对**当次时间戳定稿 md**重跑 mermaid_render / md_to_docx，"
            " 禁止用未改正的 draft.md 出交付 Word。"
        )
        for h in hits[:20]:
            lines.append(f"  L{h.line}: {h.snippet}")
        if n > 20:
            lines.append(f"  … 另有 {n - 20} 处")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="检查 Markdown 是否把行内 LaTeX 写成了普通括号"
    )
    p.add_argument("-i", "--input", required=True, type=Path)
    args = p.parse_args(argv)
    path = args.input
    if not path.is_file():
        print(f"错误：找不到 {path}", file=sys.stderr)
        return 1
    try:
        md = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        md = path.read_text(encoding="utf-8", errors="replace")
    hits = find_bare_paren_latex(md)
    print(format_hits_report(hits), file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
