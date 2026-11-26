# -*- coding: utf-8 -*-
"""国知局公布公告高级查询 CLI（通用著录检索，非交底查新）。

默认只翻 config.yaml 中的 max_pages（默认 3 页），不要一上来爬完全部分页。
对话里改阈值：改 config.yaml 或传 ``--max-pages``。仅当用户明确要求穷举时才加 ``--complete``。
第一页若读到「共 N 页」，``--complete`` 按总页数翻完；读不到才用 ``max_pages_hard``。
分页未完成时 ``complete=false``，禁止称为全部。采到总页数才能说「已翻完全部分页」或「还剩 x 页」。

示例：

  python skills/patent-search/tools/cnipa_search.py --inventor "姓名" --applicant "单位"
  python skills/patent-search/tools/cnipa_search.py --title "数据处理" --abstract "吸附 and 再生" --class B01J20 --max-pages 2
  python skills/patent-search/tools/cnipa_search.py --inventor "姓名" --complete
  python skills/patent-search/tools/cnipa_search.py --abstract "折叠 and 杯盖" --class 09-03 --type design --derived-from image --type-inferred

结果 Markdown 由 ``emit_search_report.py`` 写入 ``outputs/patent-search/``。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cnipa_parse import EpubSearchHit, application_number_for_epub_query
from derived_query import (
    DISCLAIMER,
    inferred_type_note,
    query_mode_for,
    normalize_derived_from,
    require_image_patent_type,
)
from emit_search_report import write_search_report
from patent_type import TYPE_ALL, normalize_patent_type
from search_config import load_search_config, resolve_max_pages
from stdio_utf8 import ensure_utf8_stdio


def normalize_identity(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", "", normalized).casefold()


def _matching_applicant(actual: str | None, aliases: list[str]) -> str | None:
    actual_key = normalize_identity(actual)
    if not actual_key:
        return None
    for alias in aliases:
        if normalize_identity(alias) in actual_key:
            return alias
    return None


def filter_hits(
    hits: list[EpubSearchHit],
    *,
    inventor: str | None = None,
    applicants: list[str] | None = None,
) -> list[dict]:
    """可选：按发明人著录与申请人别名过滤，并合并同一申请的多个公布公告。"""
    applicant_aliases = [value.strip() for value in (applicants or []) if value.strip()]
    inventor_key = normalize_identity(inventor) if inventor else ""
    rows: list[dict] = []
    row_by_application: dict[str, dict] = {}
    for hit in hits:
        inventor_verified = None
        if inventor_key and hit.inventors:
            inventor_verified = inventor_key in {
                normalize_identity(name) for name in hit.inventors
            }
            if not inventor_verified:
                continue
        elif inventor_key and hit.inventors is not None and not hit.inventors:
            continue

        matched_applicant = _matching_applicant(hit.applicant, applicant_aliases)
        if applicant_aliases and matched_applicant is None:
            continue

        if inventor_verified:
            identity_status = "verified_inventor_metadata"
        elif inventor_key and applicant_aliases:
            identity_status = "inventor_query_and_applicant"
        elif inventor_key:
            identity_status = "inventor_query_only_unverified_namesake"
        elif applicant_aliases:
            identity_status = "applicant_filter"
        else:
            identity_status = "unfiltered"

        row = asdict(hit)
        row.pop("raw_html", None)
        row["matched_applicant"] = matched_applicant
        row["identity_status"] = identity_status
        publication_record = {
            "pub_number": hit.pub_number,
            "publication_date": hit.publication_date,
            "link": hit.link,
        }
        row["publication_records"] = [publication_record]

        application_key = normalize_identity(hit.application_number)
        if application_key and application_key in row_by_application:
            existing = row_by_application[application_key]
            existing_numbers = {
                record.get("pub_number") for record in existing["publication_records"]
            }
            if publication_record["pub_number"] not in existing_numbers:
                existing["publication_records"].append(publication_record)
            continue
        rows.append(row)
        if application_key:
            row_by_application[application_key] = row
    return rows


filter_portfolio_hits = filter_hits


def completeness_note(
    *,
    complete: bool,
    total_pages: int | None,
    pages_scanned: int,
    page_budget: int | None,
    pages_remaining: int | None = None,
    has_next: bool | None = None,
) -> str:
    """门禁用总页数说话：没采到总页数时只谈「下页」，采到了才谈全部/剩余页。"""
    remaining = pages_remaining
    if remaining is None and total_pages is not None:
        remaining = max(0, int(total_pages) - int(pages_scanned))
    if complete:
        if total_pages is not None:
            return f"已翻完全部分页（共 {total_pages} 页）"
        return "已翻到末页（没有「下页」）"
    if total_pages is not None:
        leftover = remaining if remaining is not None else max(0, int(total_pages) - int(pages_scanned))
        if page_budget is not None and int(page_budget) < int(total_pages):
            return f"共 {total_pages} 页，本次上限 {page_budget}，还剩 {leftover} 页未翻"
        return f"共 {total_pages} 页，还剩 {leftover} 页未翻"
    if has_next is True:
        return "还能点「下页」，分页未完整遍历，不得将本次结果表述为完整清单"
    return "分页未完整遍历（以能否点「下页」为准），不得将本次结果表述为完整清单"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="公布站高级查询：发明人/申请人/分类号/名称/摘要等，默认少翻页"
    )
    parser.add_argument("--inventor", default="", help="发明人/设计人")
    parser.add_argument(
        "--applicant",
        action="append",
        default=[],
        help="申请人/单位；可重复",
    )
    parser.add_argument("--title", default="", help="名称")
    parser.add_argument(
        "--abstract",
        default="",
        help="摘要/简要说明；只用 and / or / not（运算符前后空格），不要用 ? / %%",
    )
    parser.add_argument("--class", dest="class_code", default="", help="分类号 IPC/LOC 前缀，不要两头加 %%")
    parser.add_argument("--application-number", default="", help="申请号")
    parser.add_argument("--publication-number", default="", help="公开号/公告号；填表时去掉 CN/ZL 前缀")
    parser.add_argument(
        "--type",
        default=TYPE_ALL,
        help="invention|utility_model|design|all（默认 all）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="覆盖 config.yaml 的 max_pages；普通检索仍受 max_pages_hard 限制",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="第一页读到「共 N 页」则按总页数翻完；读不到才用 max_pages_hard；未完成不得称全部",
    )
    parser.add_argument(
        "--derived-from",
        default="",
        help="image|claims：由单图或权要生成的名称/摘要检索式；写入报告，不改变填表",
    )
    parser.add_argument(
        "--derived-note",
        default="",
        help="派生检索的理解要点（产品/特征/权要主题），写入报告",
    )
    parser.add_argument(
        "--type-inferred",
        action="store_true",
        help="单图未口头指定类型、由看图推断时加上；报告写入推断说明",
    )
    return parser


def _query_fields(args: argparse.Namespace) -> dict[str, str]:
    application_number = application_number_for_epub_query(args.application_number) or (
        args.application_number or ""
    ).strip()
    fields = {
        "inventor": args.inventor,
        "applicant": args.applicant[0] if args.applicant else "",
        "title": args.title,
        "abstract": args.abstract,
        "class_code": args.class_code,
        "application_number": application_number,
        "publication_number": args.publication_number,
    }
    return {key: value.strip() for key, value in fields.items() if str(value).strip()}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = _build_parser().parse_args(argv)
    try:
        patent_type = normalize_patent_type(args.type, default=TYPE_ALL)
    except ValueError as exc:
        print(f"ERROR: 专利类型参数无效：{exc}", file=sys.stderr)
        return 2
    try:
        derived_from = normalize_derived_from(args.derived_from)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    derived_note = (args.derived_note or "").strip()
    fields = _query_fields(args)
    if not fields:
        print(
            "ERROR: 请至少提供一个检索字段（发明人/申请人/名称/摘要/分类号/申请号/公开号）",
            file=sys.stderr,
        )
        return 2
    if derived_from and not (fields.get("title") or fields.get("abstract")):
        print(
            "ERROR: 单图/权要检索须至少填写名称或摘要关键字",
            file=sys.stderr,
        )
        return 2
    try:
        require_image_patent_type(derived_from, patent_type)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    type_inferred = bool(args.type_inferred) and derived_from == "image"
    type_note = inferred_type_note(patent_type) if type_inferred else ""
    if args.max_pages is not None and args.max_pages < 1:
        print("ERROR: --max-pages 必须至少为 1", file=sys.stderr)
        return 2

    cfg = load_search_config()
    page_limit = resolve_max_pages(
        requested=args.max_pages,
        want_complete=args.complete,
        cfg=cfg,
    )

    if importlib.util.find_spec("playwright") is None:
        print(
            "ERROR: 请安装 skills/patent-search/tools/requirements-cnipa.txt 中的依赖和 Playwright",
            file=sys.stderr,
        )
        return 1

    from cnipa_crawler import search_advanced

    try:
        search = search_advanced(
            fields,
            patent_type=patent_type,
            max_pages=page_limit,
            want_complete=args.complete,
            cfg=cfg,
        )
    except Exception as exc:
        print(f"CNIPA_EPUB_ERROR: {exc}", file=sys.stderr)
        return 1

    matched = filter_hits(
        search.hits,
        inventor=args.inventor or None,
        applicants=args.applicant,
    )
    queried_at = datetime.now()
    payload = {
        "source": "http://epub.cnipa.gov.cn/Advanced",
        "scope": "published_records_only",
        "query_mode": query_mode_for(derived_from),
        "disclaimer": DISCLAIMER if derived_from else "",
        "queried_at": queried_at.strftime("%Y-%m-%d %H:%M:%S"),
        "query": {
            **fields,
            "applicants": args.applicant,
            "patent_type": patent_type,
            "max_pages": page_limit,
            "want_complete": bool(args.complete),
            "derived_from": derived_from,
            "derived_note": derived_note,
            "type_inferred": type_inferred,
            "type_note": type_note,
        },
        "complete": search.complete,
        "stop_reason": search.stop_reason,
        "pages_scanned": search.pages_scanned,
        "total_reported": search.total_reported,
        "total_pages": search.total_pages,
        "page_size_actual": search.page_size_actual,
        "first_page_hit_count": search.first_page_hit_count,
        "page_budget": search.page_budget,
        "pages_remaining": search.pages_remaining,
        "hit_count_estimate": search.hit_count_estimate,
        "completeness_note": completeness_note(
            complete=search.complete,
            total_pages=search.total_pages,
            pages_scanned=search.pages_scanned,
            page_budget=search.page_budget,
            pages_remaining=search.pages_remaining,
        ),
        "candidate_count": len(search.hits),
        "matched_count": len(matched),
        "matched_publication_count": sum(
            len(row["publication_records"]) for row in matched
        ),
        "hits": matched,
    }
    report_path = write_search_report(payload, queried_at=queried_at)
    print("EPUB_SEARCH_MD:", str(report_path), flush=True)
    print("EPUB_SEARCH_JSON:", json.dumps(payload, ensure_ascii=False), flush=True)
    print(
        "EPUB_SEARCH_NOTE: pages=%d candidates=%d matched=%d complete=%s stop=%s "
        "total_pages=%s page_size=%s page_budget=%s remaining=%s"
        % (
            search.pages_scanned,
            len(search.hits),
            len(matched),
            str(search.complete).lower(),
            search.stop_reason,
            search.total_pages if search.total_pages is not None else "-",
            search.page_size_actual if search.page_size_actual is not None else "-",
            search.page_budget if search.page_budget is not None else page_limit,
            search.pages_remaining if search.pages_remaining is not None else "-",
        ),
        file=sys.stderr,
        flush=True,
    )
    if not search.complete:
        print(
            "EPUB_SEARCH_INCOMPLETE: "
            + completeness_note(
                complete=False,
                total_pages=search.total_pages,
                pages_scanned=search.pages_scanned,
                page_budget=search.page_budget,
                pages_remaining=search.pages_remaining,
                has_next=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
