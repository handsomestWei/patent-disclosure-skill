# -*- coding: utf-8 -*-
"""公布站高级查询爬虫（patent-search 独立实现，不 import 交底 crawl）。

分页策略：
1. 提交查询后解析**当前结果页**，不要用 AJAX POST 再要第 1 页。
2. 第一页采「共 N 页」与真实每页条数，再排程；翻页仍点「下页」，不要做「到第 N 页」。
3. 回退 fetch 时**保留** ``#searchAfter``（清空会导致公布站 HTTP 400）。
4. 400 退避重试，仍失败则 ``complete=false`` 停止，禁止死循环。

-------------------------------------------------------------------------------
站点防护特征（实测，改站时请重新验证）
分析 by Claude Opus 5 Extra High
-------------------------------------------------------------------------------
站点为**瑞数类动态 cookie 防护**：首访返回挑战 JS 并**自跳转一次**，由 JS 计算后种下
动态 cookie 才放行真实 DOM。cookie 名随机成对（形如 ``NOh8RTWx6K2dS`` / ``…T``），
**不可硬编码**。由此有三条硬约束：

- **UA 用本机浏览器自己的**（见 ``_new_context`` → ``browser.browser_user_agent``），只把
  ``HeadlessChrome`` 换成 ``Chrome``。带 ``HeadlessChrome`` 时首页 DOM 仅 39 字节、检索框不出现；
  写死旧版本号（如内核 154 却报 Chrome/120）时页面能打开，**表单提交却回 400**（6 字节正文，
  页面变成 39 字节空白），等满超时才报错。
- **gate 轮询必须吞掉** ``Execution context was destroyed``：自跳转会销毁执行上下文。
- **纯 HTTP 直连不可行**：把浏览器 cookie 搬进 requests 并配齐请求头，实测只回 202 挑战页；
  该 cookie 需页面内 JS 持续参与。故必须在浏览器上下文内发请求（本模块翻页回退即如此）。

gate 用 ``wait_until="commit"`` + 短轮询，且**直接打开 /Advanced**：实测无需先过首页。
先首页再高级页、并用 ``load`` + 3 秒步进轮询的老写法实测 23.9 秒，改后 3.4 秒。

限流绑定**会话**而非 IP：连续无间隔提交约第 3 次即被拒，且同 context 内不可恢复
（重新 gate 实测 41.5 秒仍过不去），换新 context 才行。本模块是「单次查询 + 翻 1–3 页」，
页间已有 ``page_delay_ms``；若将来改成多查询循环，需按会话级限流重新设计节流。

提交结果按查询文档（POST ``/Dxb/…``）的状态码分三类（``EpubSubmitError.reason``）：

- ``waf_rejected``：非 200 且非 5xx，防护拒绝。冷却后换新会话重试一次。
- ``submit_not_sent``：点击后 20 秒内没发出查询就重点一次，仍不发再换新会话。

检索框一出现就提交（零点几秒内）会被回 400；等页面 ``load`` 完成再静置 2 秒才提交，
同一 IP、同一轻查询实测 200（0.6–1.3 秒返回）。
- ``backend_error``：5xx。宽条件（如只填 ``B25J`` 这类大类）后端可能 300 秒后回 504，不重试。
- ``backend_timeout``：限时内没有回文档，同样不重试，提示缩窄条件。

gate 超时（放行耗时多在 6–15 秒，偶有超过 45 秒的长尾）也换新会话重试一次。
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from browser import browser_user_agent, launch_chromium
from cnipa_parse import (
    EpubSearchHit,
    application_number_for_epub_query,
    publication_number_for_epub_query,
    parse_reported_page_size,
    parse_reported_total,
    parse_reported_total_pages,
    parse_search_result_html,
)
from patent_type import TYPE_ALL, epub_checkbox_states, normalize_patent_type
from search_config import load_search_config, resolve_max_pages, resolve_page_budget

EPUB_BASE = "http://epub.cnipa.gov.cn/"
EPUB_ADVANCED = EPUB_BASE.rstrip("/") + "/Advanced"
EPUB_ADVANCED_CHECKBOX = {
    "fmgb": "isFmgb",
    "fmsq": "isFmsq",
    "xxsq": "isXx",
    "wgsq": "isWg",
}
EPUB_TITLE_RESULT = "专利查询结果展示"
EPUB_TITLE_NO_HIT = "无查询结果"

FIELD_SELECTORS = {
    "class_code": ["#e51"],
    "title": ["#ti"],
    "abstract": [
        "#abs",
        "input#abs",
        "textarea#abs",
        "#ab",
        "input[name='ab']",
        "input[name='abs']",
        "input[name='catalogInfo.Ab']",
        "textarea#ab",
        "textarea[name='ab']",
    ],
    "inventor": ["#e72"],
    "applicant": [
        "#e71_73",
        "input[name='catalogInfo.E71_73']",
        "#pa",
        "#e10",
        "input[name='pa']",
        "input[name='e10']",
    ],
    "application_number": ["#an", "#e21", "input[name='an']", "input[name='catalogInfo.An']"],
    "publication_number": ["#pn", "#e11", "input[name='pn']"],
}
FIELD_LABELS = {
    "abstract": ["摘要/简要说明", "摘要", "简要说明"],
    "title": ["名称"],
    "class_code": ["分类号"],
    "inventor": ["发明（设计）人", "发明人", "设计人"],
    "applicant": ["申请（专利权）人", "申请人"],
    "application_number": ["申请号"],
    "publication_number": ["公布（公告）号", "公布号", "公告号"],
}
_FIND_FIELD_BY_LABEL_JS = """(needles) => {
    const wanted = (needles || []).map((s) => String(s).replace(/\\s+/g, '')).filter(Boolean);
    if (!wanted.length) return null;
    const compact = (s) => String(s || '').replace(/\\s+/g, '');
    const pick = (el) => {
        if (!el) return null;
        if (el.id) return '#' + el.id;
        const name = el.getAttribute('name');
        if (name && !/[\\s"'\\]]/.test(name)) {
            const tag = (el.tagName || 'input').toLowerCase();
            return tag + '[name="' + name + '"]';
        }
        return null;
    };
    const nodes = Array.from(document.querySelectorAll(
        'label, dt, th, td, span, div, p, li, strong, b'
    ));
    for (const el of nodes) {
        const text = compact(el.innerText || el.textContent || '');
        if (!text || text.length > 24) continue;
        if (!wanted.some((n) => text === n || text.startsWith(n))) continue;
        const forId = el.getAttribute('for');
        if (forId) {
            const byFor = document.getElementById(forId);
            const sel = pick(byFor);
            if (sel) return sel;
        }
        const nested = el.querySelector('input[type="text"], input:not([type]), textarea');
        const nestedSel = pick(nested);
        if (nestedSel) return nestedSel;
        const row = el.closest('tr, li, .form-item, .el-form-item, dd, div');
        const inRow = row && row.querySelector('input[type="text"], input:not([type]), textarea');
        const rowSel = pick(inRow);
        if (rowSel) return rowSel;
        let sib = el.nextElementSibling;
        for (let i = 0; i < 4 && sib; i += 1) {
            const hit = sib.matches && sib.matches('input, textarea')
                ? sib
                : sib.querySelector && sib.querySelector('input[type="text"], textarea');
            const sibSel = pick(hit);
            if (sibSel) return sibSel;
            sib = sib.nextElementSibling;
        }
    }
    return null;
}"""

_RESULT_PAGE_READY_JS = """(titles) => {
    const t = document.title.trim();
    if (t === titles.noHit) return true;
    if (t !== titles.result) return false;
    const r = document.querySelector("#result");
    if (!r) return false;
    if (r.querySelector("div.item, h1.title")) return true;
    const html = r.innerHTML;
    if (
        html.includes("无查询结果") ||
        html.includes("没有找到") ||
        html.includes("未检索到") ||
        html.includes("0条")
    ) {
        return true;
    }
    return false;
}"""
_RESULT_FINGERPRINT_JS = """() => {
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    return `${location.href}|${text.slice(0, 2000)}`;
}"""
_RESULT_FINGERPRINT_CHANGED_JS = """(previous) => {
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    return `${location.href}|${text.slice(0, 2000)}` !== previous;
}"""
_CURRENT_PAGE_JS = """() => {
    const el = document.querySelector(".current_page");
    const n = Number.parseInt((el && el.textContent) || "", 10);
    return Number.isFinite(n) ? n : null;
}"""
# 仅取结果区文本（不含 URL/令牌）：公布站每次响应都轮换令牌，
# 整页指纹或带 location.href 的指纹会把「同页重发」误判为翻页成功。
_RESULT_TEXT_JS = """() => {
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    return text.slice(0, 2000);
}"""
_ADVANCE_WAIT_JS = """(arg) => {
    const el = document.querySelector(".current_page");
    const n = Number.parseInt((el && el.textContent) || "", 10);
    if (Number.isFinite(n) && arg.previousPage != null && n > arg.previousPage) return true;
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    return text.slice(0, 2000) !== arg.previousText;
}"""
_ADVANCE_CHECK_JS = """(arg) => {
    const el = document.querySelector(".current_page");
    const n = Number.parseInt((el && el.textContent) || "", 10);
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    return {
        currentPage: Number.isFinite(n) ? n : null,
        changed: text.slice(0, 2000) !== arg.previousText,
    };
}"""
_PAGE_ADVANCED_JS = """(previous) => {
    const el = document.querySelector(".current_page");
    const n = Number.parseInt((el && el.textContent) || "", 10);
    if (Number.isFinite(n) && previous != null && n !== previous) return true;
    const result = document.querySelector("#result");
    const text = result ? result.innerText.replace(/\\s+/g, " ").trim() : "";
    const fp = `${location.href}|${text.slice(0, 2000)}`;
    return typeof previous === "string" && fp !== previous;
}"""
# 回退用：保留 searchAfter，禁止清空（清空会 400）
_FETCH_RESULT_PAGE_JS = """async ({pageNum, pageSize, timeoutMs}) => {
    const form = document.querySelector("#query_form");
    if (!form) return {ok: false, error: "missing_query_form"};
    const pageNumInput = form.querySelector("#pageNum");
    const pageSizeInput = form.querySelector("#pageSize");
    if (!pageNumInput || !pageSizeInput) {
        return {ok: false, error: "missing_page_fields"};
    }
    pageNumInput.value = String(pageNum);
    pageSizeInput.value = String(pageSize);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: new URLSearchParams(new FormData(form)),
            credentials: "same-origin",
            signal: controller.signal,
            headers: {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        const text = await response.text();
        const currentText = document.querySelector(".current_page")?.textContent || "";
        const totalText = document.querySelector(".page_total")?.textContent || "";
        const totalMatch = totalText.match(/共\\s*(\\d+)\\s*页/);
        const totalScriptMatch = text.match(/\\btotal_page\\s*=\\s*(\\d+)/i) ||
            text.match(/\\btotalPage\\s*[:=]\\s*(\\d+)/i);
        return {
            ok: response.ok,
            status: response.status,
            text,
            currentPage: Number.parseInt(currentText, 10) || pageNum,
            totalPages: totalMatch ? Number.parseInt(totalMatch[1], 10) :
                (totalScriptMatch ? Number.parseInt(totalScriptMatch[1], 10) : null),
        };
    } catch (error) {
        return {ok: false, error: String(error)};
    } finally {
        clearTimeout(timer);
    }
}"""
_FIND_NEXT_PAGE_JS = """() => {
    const candidates = Array.from(document.querySelectorAll(
        'a.next_page, a[rel="next"], button[rel="next"], a, button, ' +
        'input[type="button"], input[type="submit"], span[onclick], li[onclick]'
    ));
    const disabled = (element) => {
        const own = `${element.className || ""} ${element.getAttribute("aria-disabled") || ""}`.toLowerCase();
        const parent = element.parentElement
            ? `${element.parentElement.className || ""} ${element.parentElement.getAttribute("aria-disabled") || ""}`.toLowerCase()
            : "";
        return element.disabled || element.hasAttribute("disabled") ||
            own.includes("disabled") || parent.includes("disabled") ||
            own.includes("btn_dis") || parent.includes("btn_dis") ||
            own.includes("layui-disabled") || parent.includes("layui-disabled");
    };
    for (const element of candidates) {
        if (disabled(element)) continue;
        const text = (element.innerText || element.value || "").replace(/\\s+/g, "").trim();
        const rel = (element.getAttribute("rel") || "").toLowerCase();
        const title = (element.getAttribute("title") || "").replace(/\\s+/g, "").trim();
        const aria = (element.getAttribute("aria-label") || "").replace(/\\s+/g, "").trim();
        const classes = `${element.className || ""} ${element.parentElement?.className || ""}`.toLowerCase();
        const explicit = rel === "next" || title.includes("下一页") || aria.includes("下一页") ||
            text.startsWith("下一页") || text.startsWith("下页");
        const pagerSymbol = [">", "›", "»"].includes(text);
        const classNext = /(^|[\\s_-])next([\\s_-]|$)/.test(classes);
        if (!explicit && !pagerSymbol && !classNext) continue;
        return {found: true, label: text || title || aria || rel || "next"};
    }
    return {found: false, label: ""};
}"""
_CLICK_NEXT_PAGE_JS = """() => {
    const candidates = Array.from(document.querySelectorAll(
        'a.next_page, a[rel="next"], button[rel="next"], a, button, ' +
        'input[type="button"], input[type="submit"], span[onclick], li[onclick]'
    ));
    const disabled = (element) => {
        const own = `${element.className || ""} ${element.getAttribute("aria-disabled") || ""}`.toLowerCase();
        const parent = element.parentElement
            ? `${element.parentElement.className || ""} ${element.parentElement.getAttribute("aria-disabled") || ""}`.toLowerCase()
            : "";
        return element.disabled || element.hasAttribute("disabled") ||
            own.includes("disabled") || parent.includes("disabled") ||
            own.includes("btn_dis") || parent.includes("btn_dis") ||
            own.includes("layui-disabled") || parent.includes("layui-disabled");
    };
    for (const element of candidates) {
        if (disabled(element)) continue;
        const text = (element.innerText || element.value || "").replace(/\\s+/g, "").trim();
        const rel = (element.getAttribute("rel") || "").toLowerCase();
        const title = (element.getAttribute("title") || "").replace(/\\s+/g, "").trim();
        const aria = (element.getAttribute("aria-label") || "").replace(/\\s+/g, "").trim();
        const classes = `${element.className || ""} ${element.parentElement?.className || ""}`.toLowerCase();
        const explicit = rel === "next" || title.includes("下一页") || aria.includes("下一页") ||
            text.startsWith("下一页") || text.startsWith("下页");
        const pagerSymbol = [">", "›", "»"].includes(text);
        const classNext = /(^|[\\s_-])next([\\s_-]|$)/.test(classes);
        if (!explicit && !pagerSymbol && !classNext) continue;
        element.click();
        return {clicked: true, label: text || title || aria || rel || "next"};
    }
    return {clicked: false, label: ""};
}"""
_PAGER_PLAN_JS = """() => {
    const totalText = (document.querySelector(".page_total")?.textContent || "")
        + "\\n" + (document.body?.innerText || "");
    const pages = /共\\s*([\\d,]+)\\s*页/.exec(totalText);
    const per = /每页\\s*(\\d+)\\s*条/.exec(document.body?.innerText || "");
    const sizeEl = document.querySelector("#pageSize");
    const size = Number.parseInt((sizeEl && sizeEl.value) || (per && per[1]) || "", 10);
    return {
        total_pages: pages ? Number.parseInt(pages[1].replace(/,/g, ""), 10) : null,
        page_size: Number.isFinite(size) && size > 0 ? size : null
    };
}"""
#: 提交后等查询文档的上限（毫秒）。宽条件时后端可能要一两分钟才回。
_SUBMIT_RESPONSE_TIMEOUT_MS = 150_000
#: 点击后等查询请求发出的上限（毫秒）。检索框出现时页面脚本可能还没挂好，点击会落空。
_SUBMIT_SENT_TIMEOUT_MS = 20_000
#: 点击前等页面加载完成的上限（毫秒）。
_PAGE_SCRIPTS_TIMEOUT_MS = 15_000
_PAGE_SCRIPTS_READY_JS = "() => document.readyState === 'complete'"
#: 放行后检索框一出现就提交会被回 400：页面加载完成后再静置这么久（毫秒）才提交。
_PAGE_SETTLE_MS = 2_000
#: 换新会话重试前的冷却（秒）：刚被拒时立刻换会话仍会被挡在 gate 外。
_FRESH_SESSION_COOLDOWN_SEC = 8.0


class EpubSubmitError(RuntimeError):
    """提交高级查询失败。

    ``reason``：``waf_rejected`` / ``submit_not_sent`` / ``backend_error`` / ``backend_timeout``。
    """

    def __init__(self, reason: str, message: str, *, status: int | None = None) -> None:
        self.reason = reason
        self.status = status
        shown = status if status is not None else "-"
        super().__init__(f"reason={reason} status={shown} {message}")


@dataclass
class PagedSearchResult:
    hits: list[EpubSearchHit]
    pages_scanned: int
    complete: bool
    stop_reason: str
    total_reported: int | None = None
    total_pages: int | None = None
    page_size_actual: int | None = None
    first_page_hit_count: int | None = None
    page_budget: int | None = None
    pages_remaining: int | None = None
    hit_count_estimate: int | None = None
    html_bytes: int = 0
    filled_fields: dict[str, str] | None = None


def _max_wait_sec() -> float:
    """gate 轮询上限（秒）。

    默认 30：站点放行通常在 3–4 秒内完成，180 秒只会让真卡住时白等。
    仍可用 ``EPUB_WAF_MAX_WAIT_SEC`` 上调。
    """
    return float(os.environ.get("EPUB_WAF_MAX_WAIT_SEC", "30"))


def _headed() -> bool:
    return os.environ.get("PLAYWRIGHT_HEADED", "").strip() in ("1", "true", "yes")


_GATE_POLL_STEP_SEC = 0.25
_GATE_GOTO_TIMEOUT_MS = 30_000


def _gate(
    page: Page,
    url: str,
    selectors: tuple[str, ...],
    *,
    what: str,
    max_wait_sec: float | None = None,
) -> None:
    """打开页面并等到检索字段出现。

    三处要点（站点是瑞数类动态 cookie 防护，实测）：

    1. 字段已在就**不重新 goto**，避免整页重载。
    2. ``wait_until="commit"``：只等文档开始提交。站点首访会返回挑战 JS 并**自跳转一次**，
       等 ``load`` 只是白等资源。
    3. 轮询**先查再等**，且必须吞掉 ``Execution context was destroyed``——
       自跳转会销毁执行上下文，裸调用 ``query_selector`` 会在这里抛错。
    """
    limit = max_wait_sec if max_wait_sec is not None else _max_wait_sec()
    for sel in selectors:
        if page.query_selector(sel):
            return
    try:
        page.goto(url, wait_until="commit", timeout=_GATE_GOTO_TIMEOUT_MS)
    except (PlaywrightTimeoutError, Error):
        pass  # 自跳转期间 goto 可能报错，后面以字段是否出现为准
    deadline = time.monotonic() + limit
    # 次数与时间双重上限：``wait_for_timeout`` 在测试替身上不会真的等待，
    # 只靠时间判断会空转到超时。
    max_polls = int(limit / _GATE_POLL_STEP_SEC) + 2
    for _ in range(max_polls):
        for sel in selectors:
            try:
                if page.query_selector(sel):
                    return
            except Error:
                pass
        if time.monotonic() >= deadline:
            break
        page.wait_for_timeout(int(_GATE_POLL_STEP_SEC * 1000))
    raise TimeoutError(
        f"{limit}s 内未出现{what}；可增大 EPUB_WAF_MAX_WAIT_SEC 或设置 PLAYWRIGHT_HEADED=1"
    )


def wait_for_epub_home_ready(page: Page, *, max_wait_sec: float | None = None) -> None:
    _gate(page, EPUB_BASE, ("#searchStr",), what="检索框 #searchStr", max_wait_sec=max_wait_sec)


def wait_for_epub_advanced_ready(page: Page, *, max_wait_sec: float | None = None) -> None:
    _gate(
        page,
        EPUB_ADVANCED,
        ("#e51", "#advForm"),
        what="高级查询页",
        max_wait_sec=max_wait_sec,
    )


def _safe_page_content(page: Page, *, max_attempts: int = 10) -> str:
    last_err: Exception | None = None
    for i in range(max_attempts):
        try:
            return page.content()
        except Error as e:
            msg = str(e).lower()
            last_err = e
            if "navigating" not in msg and "changing" not in msg:
                raise
            try:
                page.wait_for_load_state("load", timeout=20_000)
            except Exception:
                pass
            page.wait_for_timeout(400 + 200 * i)
    if last_err:
        raise last_err
    raise RuntimeError("_safe_page_content: 未返回内容")


def _wait_result_page_ready(page: Page) -> None:
    page.wait_for_function(
        _RESULT_PAGE_READY_JS,
        arg={"result": EPUB_TITLE_RESULT, "noHit": EPUB_TITLE_NO_HIT},
        timeout=120_000,
    )


def _hit_key(hit: EpubSearchHit) -> str:
    return (
        hit.pub_number
        or hit.application_number
        or hit.link
        or (hit.title or "")[:120]
        or hit.raw_html[:120]
    )


def _merge_hits(target: list[EpubSearchHit], incoming: list[EpubSearchHit]) -> None:
    seen = {_hit_key(hit) for hit in target}
    for hit in incoming:
        key = _hit_key(hit)
        if key in seen:
            continue
        seen.add(key)
        target.append(hit)


def apply_epub_advanced_type_filter(page: Page, patent_type: str = TYPE_ALL) -> None:
    states = epub_checkbox_states(patent_type)
    for home_id, want in states.items():
        cid = EPUB_ADVANCED_CHECKBOX.get(home_id)
        if not cid:
            continue
        box = page.query_selector(f"#{cid}")
        if not box:
            continue
        try:
            if want:
                box.check(force=True)
            else:
                box.uncheck(force=True)
        except Error:
            page.evaluate(
                """({id, checked}) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.checked = checked;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('click', { bubbles: true }));
                }""",
                {"id": cid, "checked": want},
            )


def apply_epub_advanced_catalog_filter(page: Page, catalog_id: str) -> None:
    if catalog_id not in EPUB_ADVANCED_CHECKBOX:
        raise ValueError(f"unknown CNIPA publication catalog: {catalog_id}")
    for home_id, advanced_id in EPUB_ADVANCED_CHECKBOX.items():
        box = page.query_selector(f"#{advanced_id}")
        if not box:
            raise RuntimeError(f"CNIPA advanced-search checkbox missing: #{advanced_id}")
        want = home_id == catalog_id
        try:
            if want:
                box.check(force=True)
            else:
                box.uncheck(force=True)
        except Error:
            page.evaluate(
                """({id, checked}) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.checked = checked;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                {"id": advanced_id, "checked": want},
            )


def _label_selector_for_field(page: Page, field: str) -> str | None:
    needles = FIELD_LABELS.get(field) or []
    if not needles:
        return None
    try:
        found = page.evaluate(_FIND_FIELD_BY_LABEL_JS, needles)
    except Error:
        return None
    return str(found).strip() if found else None


def fill_advanced_field(page: Page, field: str, value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    selectors = list(FIELD_SELECTORS.get(field, []))
    for selector in selectors:
        if page.query_selector(selector):
            page.fill(selector, text)
            return True
    labeled = _label_selector_for_field(page, field)
    if labeled and labeled not in selectors and page.query_selector(labeled):
        page.fill(labeled, text)
        return True
    return False


def _adapt_advanced_fields(fields: dict[str, str]) -> dict[str, str]:
    adapted: dict[str, str] = {}
    for field, value in fields.items():
        if field not in FIELD_SELECTORS:
            continue
        text = (value or "").strip()
        if not text:
            continue
        if field == "application_number":
            text = application_number_for_epub_query(text) or text
        elif field == "publication_number":
            text = publication_number_for_epub_query(text) or text
        adapted[field] = text
    return adapted


def submit_advanced_query(page: Page, fields: dict[str, str], *, patent_type: str = TYPE_ALL) -> dict[str, str]:
    apply_epub_advanced_type_filter(page, patent_type)
    fields = _adapt_advanced_fields(fields)
    filled: dict[str, str] = {}
    for field, value in fields.items():
        if fill_advanced_field(page, field, value):
            filled[field] = value
    if not filled:
        raise ValueError("advanced search needs at least one filled field")
    _submit_and_wait(page, lambda: _click_advanced_submit(page))
    return filled


def _is_query_request(request) -> bool:
    try:
        return (
            request.resource_type == "document"
            and request.method == "POST"
            and "/Dxb/" in request.url
        )
    except Error:
        return False


def _is_query_document(response) -> bool:
    try:
        return _is_query_request(response.request)
    except Error:
        return False


def _wait_page_scripts(page: Page) -> None:
    try:
        page.wait_for_function(_PAGE_SCRIPTS_READY_JS, timeout=_PAGE_SCRIPTS_TIMEOUT_MS)
    except (PlaywrightTimeoutError, Error):
        pass
    page.wait_for_timeout(_PAGE_SETTLE_MS)


def _click_advanced_submit(page: Page) -> None:
    btn = page.locator("#advForm button[onclick*='adv_Query']")
    if btn.count():
        btn.first.click(no_wait_after=True)
        return
    form = page.query_selector("#advForm")
    if form is None:
        raise RuntimeError("高级查询未找到 #advForm")
    submit_btn = form.query_selector("button")
    if submit_btn is None:
        raise RuntimeError("高级查询未找到提交按钮")
    submit_btn.click(no_wait_after=True)


def _submit_and_wait(page: Page, click: Callable[[], None]) -> None:
    """点提交后先确认查询已发出，再看查询文档状态码；非 200 立即归类报错，不等满结果页超时。"""
    _wait_page_scripts(page)
    for attempt in (1, 2):
        sent = False
        try:
            with page.expect_response(
                _is_query_document, timeout=_SUBMIT_RESPONSE_TIMEOUT_MS
            ) as info:
                with page.expect_request(_is_query_request, timeout=_SUBMIT_SENT_TIMEOUT_MS):
                    click()
                sent = True
            break
        except PlaywrightTimeoutError as exc:
            if sent:
                raise EpubSubmitError(
                    "backend_timeout",
                    f"{_SUBMIT_RESPONSE_TIMEOUT_MS // 1000} 秒内公布站未返回结果，请缩窄检索条件",
                ) from exc
            if attempt == 2:
                raise EpubSubmitError(
                    "submit_not_sent", "点击提交后未发出查询，页面脚本可能未就绪"
                ) from exc
            print("EPUB_SEARCH_NOTE: submit_not_sent reclick=1", file=sys.stderr, flush=True)
            _wait_page_scripts(page)
    status = int(info.value.status)
    if status >= 500:
        raise EpubSubmitError(
            "backend_error", "公布站后端出错或超时，请缩窄检索条件", status=status
        )
    if status != 200:
        raise EpubSubmitError(
            "waf_rejected", "公布站防护拒绝了本次提交", status=status
        )
    _wait_result_page_ready(page)


def submit_advanced_inventor_search(page: Page, inventor: str, *, catalog_id: str | None = None) -> dict[str, str]:
    if catalog_id:
        apply_epub_advanced_catalog_filter(page, catalog_id)
        if not fill_advanced_field(page, "inventor", inventor):
            raise RuntimeError("CNIPA advanced-search inventor field #e72 missing")
        _submit_and_wait(
            page,
            lambda: page.locator("#advForm button[onclick*='adv_Query']").click(
                no_wait_after=True
            ),
        )
        return {"inventor": inventor.strip()}
    return submit_advanced_query(page, {"inventor": inventor}, patent_type=TYPE_ALL)


def has_next_result_page(page: Page) -> bool:
    found = page.evaluate(_FIND_NEXT_PAGE_JS)
    return bool(found and found.get("found"))


def _fetch_next_fragment(
    page: Page,
    *,
    page_num: int,
    page_size: int,
    retries: int,
    backoff_ms: int,
) -> tuple[dict | None, str | None]:
    last_error = None
    for attempt in range(max(1, retries + 1)):
        result = page.evaluate(
            _FETCH_RESULT_PAGE_JS,
            {"pageNum": page_num, "pageSize": page_size, "timeoutMs": 30_000},
        )
        status = result.get("status")
        if status == 400 or str(result.get("error") or "").find("400") >= 0:
            last_error = "http_400"
            page.wait_for_timeout(backoff_ms * (attempt + 1))
            continue
        if result.get("ok") and result.get("text"):
            return result, None
        last_error = str(result.get("error") or f"http_{status}")
        page.wait_for_timeout(backoff_ms * (attempt + 1))
    return None, last_error


def _advance_confirmed(check: dict | None, previous_page: int | None) -> bool:
    """只有结果区文本确已变化才算翻页成功。

    页码递增不足以作为凭据：实测点击「下页」后翻页器页码会变化而
    结果区仍是旧记录（惰性加载/令牌失效），必须看到新内容才算数。
    """
    if not isinstance(check, dict):
        return False
    return bool(check.get("changed"))


def advance_to_next_result_page(
    page: Page,
    *,
    next_page_num: int | None = None,
    page_size: int = 3,
    retries: int = 2,
    backoff_ms: int = 1500,
) -> str:
    """Advance one result page; return advanced / last_page / stalled / http_400.

    翻页成功须以「结果区文本变化」确认（页码递增不算，实测页码
    会变而结果区仍是旧记录）；仅 URL/令牌变化不算。点击未被确认时改走保留 searchAfter 的
    fetch 旁路，旁路取回内容仍无变化则判 stalled，杜绝同页重发被
    记为多页（那一次 34 页只采到 3 条的根因）。
    """
    previous_page = page.evaluate(_CURRENT_PAGE_JS)
    previous_text = page.evaluate(_RESULT_TEXT_JS)
    clicked = page.evaluate(_CLICK_NEXT_PAGE_JS)
    if clicked and clicked.get("clicked"):
        advanced = False
        try:
            page.wait_for_function(
                _ADVANCE_WAIT_JS,
                arg={"previousPage": previous_page, "previousText": previous_text},
                timeout=120_000,
            )
            check = page.evaluate(
                _ADVANCE_CHECK_JS,
                {"previousPage": previous_page, "previousText": previous_text},
            )
            advanced = _advance_confirmed(check, previous_page)
        except (PlaywrightTimeoutError, Error):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=20_000)
            except Exception:
                pass
            try:
                check = page.evaluate(
                    _ADVANCE_CHECK_JS,
                    {"previousPage": previous_page, "previousText": previous_text},
                )
                advanced = _advance_confirmed(check, previous_page)
            except Exception:
                advanced = False
        if advanced:
            try:
                _wait_result_page_ready(page)
            except (PlaywrightTimeoutError, Error):
                pass
            return "advanced"
        print(
            "EPUB_SEARCH_NOTE: click_not_confirmed fallback=fetch",
            file=sys.stderr,
            flush=True,
        )
    if next_page_num is None or not page.query_selector("#query_form"):
        if clicked and clicked.get("clicked"):
            return "stalled"
        return "last_page"
    result, error = _fetch_next_fragment(
        page,
        page_num=next_page_num,
        page_size=page_size,
        retries=retries,
        backoff_ms=backoff_ms,
    )
    if error == "http_400":
        return "http_400"
    if result is None:
        return "stalled"
    html = str(result.get("text") or "")
    if not html.strip():
        return "stalled"
    page.evaluate(
        """(html) => {
            const result = document.querySelector("#result");
            if (result) {
                result.innerHTML = html;
                return;
            }
            document.body.insertAdjacentHTML("beforeend", html);
        }""",
        html,
    )
    try:
        check = page.evaluate(
            _ADVANCE_CHECK_JS,
            {"previousPage": previous_page, "previousText": previous_text},
        )
    except Exception:
        return "stalled"
    if not _advance_confirmed(check, previous_page):
        return "stalled"
    return "advanced"


def _read_pager_plan(page: Page, html: str) -> tuple[int | None, int | None]:
    total_pages = parse_reported_total_pages(html)
    page_size = parse_reported_page_size(html)
    try:
        info = page.evaluate(_PAGER_PLAN_JS)
    except Exception:
        info = None
    if isinstance(info, dict):
        raw_pages = info.get("total_pages")
        raw_size = info.get("page_size")
        try:
            if raw_pages is not None and int(raw_pages) > 0:
                total_pages = int(raw_pages)
        except (TypeError, ValueError):
            pass
        try:
            if raw_size is not None and int(raw_size) > 0:
                page_size = int(raw_size)
        except (TypeError, ValueError):
            pass
    return total_pages, page_size


def _hit_count_estimate(
    *,
    total_pages: int | None,
    page_size_actual: int | None,
    pages_scanned: int,
    hit_count: int,
    complete: bool,
) -> int | None:
    if complete or (total_pages and pages_scanned >= total_pages):
        return hit_count
    if total_pages and page_size_actual and total_pages > 1:
        return (total_pages - 1) * page_size_actual
    return None


def _finish_pages(
    *,
    hits: list[EpubSearchHit],
    pages_scanned: int,
    complete: bool,
    stop_reason: str,
    total_reported: int | None,
    total_pages: int | None,
    page_size_actual: int | None,
    first_page_hit_count: int | None,
    page_budget: int | None,
    html_bytes: int,
) -> PagedSearchResult:
    remaining = None
    if total_pages is not None:
        remaining = max(0, total_pages - pages_scanned)
    return PagedSearchResult(
        hits=hits,
        pages_scanned=pages_scanned,
        complete=complete,
        stop_reason=stop_reason,
        total_reported=total_reported,
        total_pages=total_pages,
        page_size_actual=page_size_actual,
        first_page_hit_count=first_page_hit_count,
        page_budget=page_budget,
        pages_remaining=remaining,
        hit_count_estimate=_hit_count_estimate(
            total_pages=total_pages,
            page_size_actual=page_size_actual,
            pages_scanned=pages_scanned,
            hit_count=len(hits),
            complete=complete,
        ),
        html_bytes=html_bytes,
    )


def collect_result_pages(
    page: Page,
    *,
    max_pages: int,
    want_complete: bool = False,
    cfg: dict | None = None,
) -> PagedSearchResult:
    settings = cfg or load_search_config()
    fallback_size = int(settings.get("page_size") or 3)
    delay_ms = int(settings["page_delay_ms"])
    retries = int(settings["http_error_retries"])
    backoff_ms = int(settings["http_error_backoff_ms"])

    if page.title().strip() == EPUB_TITLE_NO_HIT:
        return _finish_pages(
            hits=[],
            pages_scanned=1,
            complete=True,
            stop_reason="last_page",
            total_reported=0,
            total_pages=0,
            page_size_actual=fallback_size,
            first_page_hit_count=0,
            page_budget=1,
            html_bytes=0,
        )

    hits: list[EpubSearchHit] = []
    fingerprints: set[str] = set()
    pages_scanned = 0
    total_reported = None
    total_pages: int | None = None
    page_size_actual: int | None = None
    first_page_hit_count: int | None = None
    page_budget = max(1, int(max_pages))
    html_bytes = 0

    while True:
        html = _safe_page_content(page)
        html_bytes += len(html)
        page_hits = parse_search_result_html(html)
        # 以本页解析出的记录指纹判重：公布站响应轮换令牌，整页指纹永不重复，
        # 同页重发只能靠结果记录本身识别。
        digest = hashlib.sha256(
            "|".join(sorted(h.pub_number or h.title for h in page_hits)).encode(
                "utf-8", errors="replace"
            )
        ).hexdigest()
        if digest in fingerprints:
            return _finish_pages(
                hits=hits,
                pages_scanned=pages_scanned,
                complete=False,
                stop_reason="repeated_page",
                total_reported=total_reported,
                total_pages=total_pages,
                page_size_actual=page_size_actual,
                first_page_hit_count=first_page_hit_count,
                page_budget=page_budget,
                html_bytes=html_bytes,
            )
        fingerprints.add(digest)
        pages_scanned += 1
        if total_reported is None:
            total_reported = parse_reported_total(html)
        if pages_scanned == 1:
            total_pages, page_size_actual = _read_pager_plan(page, html)
            if page_size_actual is None:
                page_size_actual = fallback_size
            page_budget = resolve_page_budget(
                requested=None if want_complete else max_pages,
                want_complete=want_complete,
                total_pages=total_pages,
                cfg=settings,
            )
        _merge_hits(hits, page_hits)
        if pages_scanned == 1:
            first_page_hit_count = len(hits)

        if pages_scanned >= page_budget:
            has_next = has_next_result_page(page)
            reached_total = bool(total_pages and pages_scanned >= total_pages)
            if not has_next or reached_total:
                return _finish_pages(
                    hits=hits,
                    pages_scanned=pages_scanned,
                    complete=True,
                    stop_reason="last_page",
                    total_reported=total_reported,
                    total_pages=total_pages,
                    page_size_actual=page_size_actual,
                    first_page_hit_count=first_page_hit_count,
                    page_budget=page_budget,
                    html_bytes=html_bytes,
                )
            stop = "max_pages_hard" if want_complete and total_pages is None else "max_pages"
            return _finish_pages(
                hits=hits,
                pages_scanned=pages_scanned,
                complete=False,
                stop_reason=stop,
                total_reported=total_reported,
                total_pages=total_pages,
                page_size_actual=page_size_actual,
                first_page_hit_count=first_page_hit_count,
                page_budget=page_budget,
                html_bytes=html_bytes,
            )

        status = advance_to_next_result_page(
            page,
            next_page_num=pages_scanned + 1,
            page_size=page_size_actual or fallback_size,
            retries=retries,
            backoff_ms=backoff_ms,
        )
        if status == "last_page":
            return _finish_pages(
                hits=hits,
                pages_scanned=pages_scanned,
                complete=True,
                stop_reason=status,
                total_reported=total_reported,
                total_pages=total_pages,
                page_size_actual=page_size_actual,
                first_page_hit_count=first_page_hit_count,
                page_budget=page_budget,
                html_bytes=html_bytes,
            )
        if status in ("stalled", "http_400"):
            return _finish_pages(
                hits=hits,
                pages_scanned=pages_scanned,
                complete=False,
                stop_reason=status,
                total_reported=total_reported,
                total_pages=total_pages,
                page_size_actual=page_size_actual,
                first_page_hit_count=first_page_hit_count,
                page_budget=page_budget,
                html_bytes=html_bytes,
            )
        page.wait_for_timeout(delay_ms)


def _launch_browser(p: Playwright) -> Browser:
    browser, _label = launch_chromium(p, headless=not _headed())
    return browser


def _new_context(browser: Browser) -> BrowserContext:
    return browser.new_context(
        user_agent=browser_user_agent(browser),
        locale="zh-CN",
        viewport={"width": 1280, "height": 900},
    )


def _worth_fresh_session(exc: Exception) -> bool:
    if isinstance(exc, EpubSubmitError):
        return exc.reason in ("waf_rejected", "submit_not_sent")
    return isinstance(exc, TimeoutError)


def search_advanced(
    fields: dict[str, str],
    *,
    patent_type: str = TYPE_ALL,
    max_pages: int | None = None,
    want_complete: bool = False,
    playwright_factory: Callable[[], Playwright] | None = None,
    cfg: dict | None = None,
) -> PagedSearchResult:
    settings = cfg or load_search_config()
    page_limit = resolve_max_pages(
        requested=max_pages,
        want_complete=want_complete,
        cfg=settings,
    )
    patent_type = normalize_patent_type(patent_type, default=TYPE_ALL)
    pw_gen = playwright_factory or sync_playwright
    with pw_gen() as p:
        browser = _launch_browser(p)
        try:
            for attempt in (1, 2):
                context = _new_context(browser)
                try:
                    page = context.new_page()
                    # 直接去高级查询页：实测无需先过首页即可放行，省掉一次整页加载。
                    wait_for_epub_advanced_ready(page)
                    filled = submit_advanced_query(page, fields, patent_type=patent_type)
                    result = collect_result_pages(
                        page,
                        max_pages=page_limit,
                        want_complete=want_complete,
                        cfg=settings,
                    )
                    result.filled_fields = filled
                    return result
                except (TimeoutError, EpubSubmitError) as exc:
                    if attempt == 2 or not _worth_fresh_session(exc):
                        raise
                    cause = getattr(exc, "reason", "gate_timeout")
                    print(
                        f"EPUB_SEARCH_NOTE: fresh_session_retry cause={cause} "
                        f"cooldown_s={_FRESH_SESSION_COOLDOWN_SEC:g}",
                        file=sys.stderr,
                        flush=True,
                    )
                finally:
                    context.close()
                time.sleep(_FRESH_SESSION_COOLDOWN_SEC)
        finally:
            browser.close()
    raise RuntimeError("CNIPA advanced search did not start")
