# -*- coding: utf-8 -*-
"""
查新编排器（P0）：按**质量序**运行多个数据源 provider，单点失败**自动回退**，结果按公开号
合并去重，统一输出。把"国知局单点爬站"升级为"多源、可回退、可扩展"的查新入口。

**输出约定**（与 ``cnipa_epub_search.py`` 风格一致，便于 Agent 稳定抓取）：

- **stdout**：**仅一行** ``PRIOR_ART_JSON:`` + JSON 数组（UTF-8）。每条含
  ``source`` / ``title`` / ``pub_number`` / ``link`` / ``abstract``；``source`` 标明数据源
  （如 ``cnipa_epub`` / ``google_patents``），便于在交底书 1.1 标注公开数据库名。
- **stderr**：``PA_PROVIDER:`` / ``PA_MERGE:`` / ``PA_HINT:`` 等诊断行，**ASCII**
  （减轻 PowerShell 把含中文 stderr 当成错误流）。

**模式**：

- ``--mode fallback``（默认）：按质量序逐个数据源尝试，**第一个返回非空命中即停**
  （P0：去单点、控时、控成本）。
- ``--mode federate``：所有可用数据源都跑并合并（**更高召回**，P1 起按需启用）。

**检索词**：所有参数按空白拆分（``str.split``）；一词一查、跨词跨源合并去重。
拆词责任在 Agent（语义块，见 ``prompts/prior_art_search.md``）。

用法::

  python tools/prior_art_search.py 调度
  python tools/prior_art_search.py --mode federate 知识库 检索增强
  python tools/prior_art_search.py --providers cnipa_epub,google_patents 异构调度
"""
from __future__ import annotations

import argparse
import json
import sys

from provider_base import Hit, Provider, merge_dedupe, to_jsonable
from provider_cnipa import CnipaEpubProvider
from provider_google_patents import GooglePatentsProvider

_MAX_TERMS = 8


def default_providers() -> list[Provider]:
    """按 ``quality_rank`` 升序（越小越优先）排列的内置数据源。"""
    return sorted(
        [CnipaEpubProvider(), GooglePatentsProvider()],
        key=lambda p: p.quality_rank,
    )


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, TypeError):
            pass


def _terms_from_argv(argv: list[str]) -> list[str]:
    terms: list[str] = []
    for a in argv:
        for part in (a or "").split():
            p = part.strip()
            if p:
                terms.append(p)
    return terms


def _note(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(
    terms: list[str],
    providers: list[Provider],
    mode: str = "fallback",
) -> list[Hit]:
    """
    跑编排：返回合并去重后的命中。``mode="fallback"`` 第一个有命中的数据源即停；
    ``mode="federate"`` 跑完所有可用数据源再合并。诊断写 stderr，不污染 stdout。
    """
    collected: list[list[Hit]] = []
    for p in providers:
        ok, reason = p.available()
        if not ok:
            _note("PA_PROVIDER: name=%s skipped reason=%s" % (p.name, reason or "n/a"))
            continue
        if len(terms) > 1 and getattr(p, "prefers_single_term", False):
            _note(
                "PA_WARN: name=%s prefers single term per call; running %d terms in one "
                "process may hit Playwright/site timeouts -- prefer one Bash call per term "
                "and merge by pub_number (see prior_art_search.md)" % (p.name, len(terms))
            )
        try:
            per_term = [p.search(t) for t in terms]
        except Exception as e:  # 单源异常不中断整条链路
            _note("PA_PROVIDER: name=%s error=%s" % (p.name, repr(str(e))[:300]))
            continue
        merged = merge_dedupe(per_term)
        _note(
            "PA_PROVIDER: name=%s terms=%d hits=%d" % (p.name, len(terms), len(merged))
        )
        collected.append(merged)
        if mode == "fallback" and merged:
            break

    result = merge_dedupe(collected)
    _note("PA_MERGE: mode=%s providers_used=%d hits=%d" % (mode, len(collected), len(result)))
    if not result:
        _note("PA_HINT: 0 hits; broaden terms, try --mode federate, or fall back to WebSearch")
    return result


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(add_help=True, description="多源查新编排器（P0）")
    parser.add_argument("terms", nargs="*", help="检索词（按空白拆分，一词一查）")
    parser.add_argument(
        "--mode",
        choices=("fallback", "federate"),
        default="fallback",
        help="fallback：第一个有命中的源即停（默认）；federate：所有可用源合并",
    )
    parser.add_argument(
        "--providers",
        default="",
        help="逗号分隔的数据源白名单（name），默认全部内置源",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    terms = _terms_from_argv(args.terms)
    if not terms:
        parser.print_usage(sys.stderr)
        _note("PA_HINT: need at least one search term")
        return 2
    if len(terms) > _MAX_TERMS:
        _note(
            "ERROR: too many terms after split (%d > %d); run in batches"
            % (len(terms), _MAX_TERMS)
        )
        return 2

    providers = default_providers()
    if args.providers.strip():
        wanted = {x.strip() for x in args.providers.split(",") if x.strip()}
        providers = [p for p in providers if p.name in wanted]
        if not providers:
            _note("ERROR: no known providers match --providers=%s" % args.providers)
            return 2

    hits = run(terms, providers, mode=args.mode)
    print("PRIOR_ART_JSON:", json.dumps(to_jsonable(hits), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
