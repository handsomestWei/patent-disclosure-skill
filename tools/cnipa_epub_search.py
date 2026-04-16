# -*- coding: utf-8 -*-
"""
国知局公布站「检索 + 解析」一步完成：内存中持有结果页 HTML，**默认不落盘**。

内部调用 ``cnipa_epub_crawler.search_epub_keyword``（等同先 ``fetch_epub_result_html`` 再
``parse_search_result_html``）。

**输出约定**（便于 Agent 抓取且不触发误判降级）：

- **stdout**：**仅一行** ``EPUB_HITS_JSON:`` + JSON 数组（UTF-8，含中文标题与 ``abstract``）。
- **stderr**：``EPUB_MERGE:`` / ``EPUB_NOTE:`` / ``EPUB_HINT:`` 等说明性文字；启动时尽量将标准流
  设为 **UTF-8**（``reconfigure``），减轻 Windows 终端默认编码导致的乱码。

**检索词拆分**：命令行中所有参数会按 **Python 空白规则**（`str.split()`，连续空格等与一次空格相同）
拆成多个词；**一词一查**，结果按公开号去重合并。若只需要**单次**向公布站提交整句（站内 AND），请
写成**不含空白的一个参数**（例如无空格的连续关键词），或改用 ``cnipa_epub_crawler.py`` 单传一句。

需已安装：pip install -r tools/requirements-cnipa.txt && python -m playwright install chromium

用法：

  python tools/cnipa_epub_search.py 词1
  python tools/cnipa_epub_search.py "短语 含 空格"
  python tools/cnipa_epub_search.py 词甲 词乙 词丙

**必须**至少有一个非空检索词；**不设默认**。

若需将结果页 HTML 保存到磁盘，请改用 ``cnipa_epub_crawler.py``；若只对已有 HTML 文件做解析，
请用 ``cnipa_epub_parse.py``。

环境变量：与 ``cnipa_epub_crawler.py`` 相同（如 ``EPUB_WAF_MAX_WAIT_SEC``、``PLAYWRIGHT_HEADED``）。
"""
from __future__ import annotations

import json
import os
import sys

_MAX_TERMS = 8


def _ensure_utf8_stdio() -> None:
    """在 Windows 等环境下将 stdout/stderr 设为 UTF-8，避免中文 JSON 在终端乱码导致误判检索失败。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, TypeError):
            pass


def _terms_from_argv(argv: list[str]) -> list[str]:
    """从所有 argv 片段中按空白拆分（等价 str.split，连续空格视为一次分隔）。"""
    terms: list[str] = []
    for a in argv:
        for part in (a or "").split():
            p = part.strip()
            if p:
                terms.append(p)
    return terms


def _dedupe_hits(hits_lists: list) -> list:
    from cnipa_epub_parse import EpubSearchHit

    seen: set[str] = set()
    out: list[EpubSearchHit] = []
    for hits in hits_lists:
        for h in hits:
            key = h.pub_number or h.link or (h.title or "")[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append(h)
    return out


def _usage() -> None:
    print("用法: python tools/cnipa_epub_search.py <检索词> [更多词…]", file=sys.stderr)
    print("说明: 参数中凡遇空白（含连续空格）即拆成多个词；一词一查，结果按公开号去重合并。", file=sys.stderr)
    print('示例: python tools/cnipa_epub_search.py "批任务 调度 异构"', file=sys.stderr)
    print("  或: python tools/cnipa_epub_search.py 批任务 调度 异构", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    argv = argv if argv is not None else sys.argv[1:]
    terms = _terms_from_argv(argv)
    if not terms:
        _usage()
        return 2
    if len(terms) > _MAX_TERMS:
        print(
            "错误: 拆分后检索词超过 %d 个，请缩短或合并检索式。" % _MAX_TERMS,
            file=sys.stderr,
        )
        return 2

    os.environ.setdefault("EPUB_WAF_MAX_WAIT_SEC", "180")

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("请先安装: pip install -r tools/requirements-cnipa.txt", file=sys.stderr)
        return 1

    from cnipa_epub_crawler import search_epub_keyword
    from cnipa_epub_parse import hits_to_jsonable

    multi = len(terms) > 1
    last_html = ""
    all_batches: list = []

    try:
        for kw in terms:
            html, hits = search_epub_keyword(kw)
            last_html = html
            all_batches.append(hits)
    except Exception as e:
        print("CNIPA_EPUB_ERROR:", e, file=sys.stderr)
        return 1

    if multi:
        hits = _dedupe_hits(all_batches)
        print(
            "EPUB_MERGE: 按空白拆成 %d 个词分别检索，合并去重后 %d 条"
            % (len(terms), len(hits)),
            file=sys.stderr,
            flush=True,
        )
    else:
        hits = all_batches[0]

    if not hits and last_html and len(last_html) < 20_000:
        if multi:
            print(
                "EPUB_HINT: 拆分多词检索后仍 0 条。可换更通用词，或按 prior_art_search 使用 WebSearch。",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "EPUB_HINT: 本次解析为 0 条。若检索式较长，可在命令行中增加空格拆成多词以扩大召回。",
                file=sys.stderr,
                flush=True,
            )

    print(
        "EPUB_NOTE: 结果页 HTML 未写入磁盘（仅内存）；末次子页字节数 %d" % len(last_html),
        file=sys.stderr,
        flush=True,
    )
    # 仅此一行写入 stdout，供管道/Agent 稳定解析（勿混入多行文本，避免误判未命中）
    print(
        "EPUB_HITS_JSON:",
        json.dumps(hits_to_jsonable(hits), ensure_ascii=False),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
