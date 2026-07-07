# -*- coding: utf-8 -*-
"""
中国专利公布公告网站点：http://epub.cnipa.gov.cn/ —— **首页「公布公告查询」** 检索（#indexForm / #searchStr）。

须安装 **Playwright + Chromium**。若只需内存中解析、不落盘 HTML，优先用同目录 **`cnipa_epub_search.py`**；
本文件侧重 **写出结果页 HTML** 与可插拔的 ``fetch_epub_result_html`` API。

-------------------------------------------------------------------------------
一、整体流程（单次检索）
-------------------------------------------------------------------------------
1. 启动 Chromium（默认无头；可用环境变量改为有界面）。
2. 新建浏览器上下文：设定 **桌面 Chrome UA**、**zh-CN**、固定 **视口**（见 ``_new_context``），使请求形态接近普通用户浏览器。
3. ``page.goto`` 站点首页，**wait_until="load"**。
4. **等待首页可检索**：首页在访客到达后会先经 **前端脚本/WAF 一类逻辑**，未通过前 **不会出现** 检索输入框 ``#searchStr``。本实现通过 **周期性轮询 DOM**（每 3 秒一次，总时长见 ``EPUB_WAF_MAX_WAIT_SEC``，默认 180s）直到 ``#searchStr`` 出现；**不是**用 requests 直接 POST 能等价替代的步骤。
5. ``page.fill`` 将关键词写入 ``#searchStr``，对 ``#indexForm`` 执行 **submit**（而非单独点按钮），并 ``expect_navigation`` 等待结果页 **load**。
6. 结果页 **安定等待**：依次尝试 **load / networkidle**（超时则忽略），再 **固定短时 sleep**，减轻列表/统计脚本未跑完就取 HTML 导致的空壳或半截 DOM。
7. ``page.content()`` 取全页 HTML；若处于导航中抛错则 **重试退避**（``_safe_page_content``），避免竞态。
8. 后续解析由 **`cnipa_epub_parse.py`** 完成（本文件 ``search_epub_keyword`` 内会调用）。

-------------------------------------------------------------------------------
二、策略摘要：在解决什么、用了哪些手段
-------------------------------------------------------------------------------
- **为何用 Playwright**：站点依赖 **浏览器内 JavaScript** 渲染与风控后再开放检索框；**纯 HTTP 抓取**往往拿不到含 ``#searchStr`` 的可用首页或拿不到真实结果 DOM。
- **所谓「绕过」**：指 **技术层面** 与无头自动化、静态抓取之间的 gap——通过 **真实 Chromium 内核 + 等待 JS 完成 + 常见浏览器指纹**（UA、语言、viewport）降低「一进来就_submit」的失败率；**不**表示规避法律法规或站点服务条款，用途应限合法检索与交底书查新辅助。
- **反自动化/特征**：启动参数 ``--disable-blink-features=AutomationControlled`` 用于减弱 Chromium 的 **webdriver 自动化开关** 暴露（效果因站点升级而变，非保证）。
- **不覆盖的场景**：图形/滑块验证码、短信验证、强制登录等——若站点突然启用，本脚本**无**专门破解逻辑；可尝试 ``PLAYWRIGHT_HEADED=1`` 人工辅助或改用 **WebSearch**（见 ``prompts/prior_art_search.md``）。

-------------------------------------------------------------------------------
三、检索关键词建议
-------------------------------------------------------------------------------
- 公布站首页检索框对 **多个词** 通常按 **同时包含（AND）** 理解，**词多且专**时极易 **0 条**；**建议每次尽量使用单个词或极短短语** 做一次检索，需要宽召回时可用 **`cnipa_epub_search.py`**（按空白拆成多词、多次检索再合并），或分多次手动换关键词。
- 本脚本命令行默认仍接受一个参数字符串（可含空格）；含空格时与浏览器内一次提交一致，语义上仍是 **整句 AND**，不等同于拆词多查。

-------------------------------------------------------------------------------
环境变量
-------------------------------------------------------------------------------
  EPUB_WAF_MAX_WAIT_SEC  轮询等待 #searchStr 的最长时间，默认 180
  PLAYWRIGHT_HEADED        设为 1 时使用有界面 Chromium
  EPUB_RESULT_HTML         结果页 HTML 完整路径；不设则 tools/_last_result_YYYYMMDDHHmmss.html
  BROWSER_BACKEND          设为 agent-browser 时使用 agent-browser CLI 替代 Playwright；未设置或 playwright 走 Playwright
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from cnipa_epub_parse import EpubSearchHit, hits_to_jsonable, parse_search_result_html

# Playwright 仅在 BROWSER_BACKEND 非 agent-browser 时需要；延迟导入以避免未安装时报错
_playwright_api = None


def _import_playwright():
    global _playwright_api
    if _playwright_api is None:
        from playwright.sync_api import Browser, BrowserContext, Error, Page, Playwright, sync_playwright as _sync_pw
        _playwright_api = type("PW", (), dict(
            Browser=Browser, BrowserContext=BrowserContext,
            Error=Error, Page=Page, Playwright=Playwright,
            sync_playwright=staticmethod(_sync_pw),
        ))()
    return _playwright_api


def _browser_backend() -> str:
    return os.environ.get("BROWSER_BACKEND", "").strip().lower()


class AgentBrowserSession:
    """通过 agent-browser CLI（subprocess）控制浏览器。

    agent-browser 以 client-daemon 架构运行：每条命令是独立 subprocess，
    但共享 daemon 持久的浏览器状态。
    """

    def __init__(self, headed: bool = False):
        self._headed = headed

    def _resolve_cli(self) -> str:
        """Resolve agent-browser executable path (Windows npm .CMD wrapper)."""
        from shutil import which
        path = which("agent-browser")
        if path is None:
            raise FileNotFoundError(
                "agent-browser not found in PATH; install: npm i -g agent-browser && agent-browser install"
            )
        return path

    def _run(
        self, *args: str, timeout: int = 120
    ) -> subprocess.CompletedProcess:
        cmd = [self._resolve_cli(), *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def open(self, url: str) -> None:
        a = ["open"]
        if self._headed:
            a.append("--headed")
        a.append(url)
        r = self._run(*a, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"agent-browser open failed: {r.stderr.strip()}")

    def eval_js(self, js: str, timeout: int = 30) -> str:
        r = self._run("eval", js, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"agent-browser eval failed: {r.stderr.strip()}")
        return r.stdout.strip()

    def wait_ms(self, ms: int) -> None:
        self._run("wait", str(ms), timeout=ms // 1000 + 10)

    def wait_networkidle(self, timeout: int = 30) -> None:
        try:
            self._run("wait", "--load", "networkidle", timeout=timeout)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._run("close", timeout=10)
        except Exception:
            pass


def fetch_epub_result_html_agent_browser(keyword: str) -> str:
    """使用 agent-browser CLI 后端拉取检索结果页 HTML。"""
    session = AgentBrowserSession(headed=_headed())
    try:
        # 1. 打开站点首页
        session.open(EPUB_BASE)

        # 2. 轮询等待 #searchStr（WAF），与 Playwright 逻辑一致
        limit = _max_wait_sec()
        elapsed = 0.0
        step = 3.0
        while elapsed < limit:
            session.wait_ms(int(step * 1000))
            elapsed += step
            result = session.eval_js(
                'document.querySelector("#searchStr") ? "yes" : "no"'
            )
            if result == "yes":
                break
        else:
            raise TimeoutError(
                f"{limit}s 内未出现检索框 #searchStr；可增大 EPUB_WAF_MAX_WAIT_SEC 或设置 PLAYWRIGHT_HEADED=1"
            )

        # 3. 填写关键词并提交表单
        escaped = keyword.replace("\\", "\\\\").replace('"', '\\"')
        session.eval_js(f'document.querySelector("#searchStr").value = "{escaped}"')
        session.eval_js('document.getElementById("indexForm").submit()')

        # 4. 等待结果页安定
        session.wait_ms(3000)
        session.wait_networkidle(timeout=30)
        session.wait_ms(800)

        # 5. 获取结果页 HTML
        html = session.eval_js("document.documentElement.outerHTML")
        return html
    finally:
        session.close()


def _ensure_utf8_stdio() -> None:
    """减轻 Windows 终端下 JSON 中文乱码（与 cnipa_epub_search.py 一致）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, TypeError):
            pass


EPUB_BASE = "http://epub.cnipa.gov.cn/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _max_wait_sec() -> float:
    return float(os.environ.get("EPUB_WAF_MAX_WAIT_SEC", "180"))


def _headed() -> bool:
    return os.environ.get("PLAYWRIGHT_HEADED", "").strip() in ("1", "true", "yes")


def default_result_html_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return Path(__file__).resolve().parent / f"_last_result_{ts}.html"


def wait_for_epub_home_ready(page: "Page", *, max_wait_sec: float | None = None) -> None:
    limit = max_wait_sec if max_wait_sec is not None else _max_wait_sec()
    page.goto(EPUB_BASE, wait_until="load", timeout=120_000)
    elapsed = 0.0
    step = 3.0
    while elapsed < limit:
        page.wait_for_timeout(int(step * 1000))
        elapsed += step
        if page.query_selector("#searchStr"):
            return
    raise TimeoutError(
        f"{limit}s 内未出现检索框 #searchStr；可增大 EPUB_WAF_MAX_WAIT_SEC 或设置 PLAYWRIGHT_HEADED=1"
    )


def _wait_result_page_settled(page: "Page") -> None:
    try:
        page.wait_for_load_state("load", timeout=30_000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=25_000)
    except Exception:
        pass
    page.wait_for_timeout(800)


def _safe_page_content(page: "Page", *, max_attempts: int = 10) -> str:
    pw = _import_playwright()
    Error = pw.Error
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


def submit_index_search(page: "Page", keyword: str) -> None:
    page.fill("#searchStr", keyword)
    with page.expect_navigation(timeout=120_000, wait_until="load"):
        form = page.query_selector("#indexForm")
        if form:
            form.evaluate("el => el.submit()")
        else:
            page.evaluate(
                """() => {
                const f = document.getElementById('indexForm');
                if (f) f.submit();
            }"""
            )
    _wait_result_page_settled(page)


def fetch_epub_result_html(
    keyword: str,
    *,
    playwright_factory: Callable | None = None,
) -> str:
    """
    只拉取检索结果页 HTML，不在此函数内做正文解析。
    解析请使用 ``cnipa_epub_parse.parse_search_result_html(html)``。
    """
    if _browser_backend() == "agent-browser":
        return fetch_epub_result_html_agent_browser(keyword)
    pw = _import_playwright()
    pw_gen = playwright_factory or pw.sync_playwright
    with pw_gen() as p:
        browser = _launch_browser(p)
        context = _new_context(browser)
        try:
            page = context.new_page()
            wait_for_epub_home_ready(page)
            submit_index_search(page, keyword)
            return _safe_page_content(page)
        finally:
            context.close()
            browser.close()


def search_epub_keyword(
    keyword: str,
    *,
    playwright_factory: Callable | None = None,
) -> tuple[str, list[EpubSearchHit]]:
    html = fetch_epub_result_html(keyword, playwright_factory=playwright_factory)
    return html, parse_search_result_html(html)


def search_epub_keyword_with_page(
    page: "Page",
    keyword: str,
) -> tuple[str, list[EpubSearchHit]]:
    wait_for_epub_home_ready(page)
    submit_index_search(page, keyword)
    html = _safe_page_content(page)
    return html, parse_search_result_html(html)


def _launch_browser(p: "Playwright") -> "Browser":
    return p.chromium.launch(
        headless=not _headed(),
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )


def _new_context(browser: "Browser") -> "BrowserContext":
    return browser.new_context(
        user_agent=DEFAULT_USER_AGENT,
        locale="zh-CN",
        viewport={"width": 1280, "height": 900},
    )


def _dump_home_debug() -> None:
    """调试：仅拉取首页并保存 WAF 通过后 HTML。"""
    out = Path(__file__).resolve().parent / "_last_home.html"
    pw = _import_playwright()
    with pw.sync_playwright() as p:
        browser = _launch_browser(p)
        context = _new_context(browser)
        page = context.new_page()
        try:
            wait_for_epub_home_ready(page)
            out.write_text(page.content(), encoding="utf-8")
            print("已保存:", out)
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    _ensure_utf8_stdio()
    argv = [a for a in sys.argv[1:] if a.strip()]
    if argv and argv[0] in ("--dump-home", "-d"):
        _dump_home_debug()
        sys.exit(0)
    kw = (argv[0] if argv else "批处理").strip()
    if _browser_backend() != "agent-browser":
        try:
            import playwright  # noqa: F401
        except ImportError:
            print(
                "ERROR: pip install -r tools/requirements-cnipa.txt && python -m playwright install chromium",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        from shutil import which
        if not which("agent-browser"):
            print(
                "ERROR: agent-browser not found in PATH; install: npm i -g agent-browser && agent-browser install",
                file=sys.stderr,
            )
            sys.exit(1)
    try:
        out_html, hits = search_epub_keyword(kw)
    except Exception as e:
        print("CNIPA_EPUB_ERROR:", e, file=sys.stderr)
        sys.exit(1)
    out_path = Path(
        os.environ.get("EPUB_RESULT_HTML", "").strip() or default_result_html_path()
    )
    out_path = out_path.expanduser().resolve()
    out_path.write_text(out_html, encoding="utf-8")
    print(
        "结果页长度",
        len(out_html),
        "解析条目数",
        len(hits),
        file=sys.stderr,
        flush=True,
    )
    print("结果页 HTML 已保存:", out_path, file=sys.stderr, flush=True)
    print(
        "EPUB_HITS_JSON:",
        json.dumps(hits_to_jsonable(hits), ensure_ascii=False),
        flush=True,
    )
