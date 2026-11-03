"""线索摘要：清洗脏抓取（导航噪音、竖排拆字、引用符号）与脚本降级抓取。"""
from __future__ import annotations

import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .vocab import MENU_SUFFIXES, MENU_WORDS, NAV_NOISE


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _is_formula_glyph_frag(s: str) -> bool:
    """仅 ASCII/数字/下标短片段视为化学式竖排拆字（勿吞中文导航词）。"""
    return bool(re.fullmatch(r"[A-Za-z0-9²³₀-₉]{1,2}", s))


def _join_broken_glyph_lines(lines: list[str]) -> list[str]:
    """把 Al / 2 / O / 3 这类竖排拆字拼回 Al2O3。"""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    for raw in lines:
        s = raw.strip()
        if not s:
            flush()
            continue
        if _is_formula_glyph_frag(s):
            buf.append(s)
            continue
        if buf:
            # 拆字后紧跟公式续接（如 /勃姆石涂覆）
            if s.startswith("/") or re.fullmatch(r"[A-Za-z0-9²³₀-₉/.\-]+", s):
                buf.append(s)
                flush()
                continue
            # 中文续接且缓冲已是化学式前缀
            joined = "".join(buf)
            if re.search(r"[A-Za-z]\d", joined) and len(s) <= 16:
                buf.append(s)
                flush()
                continue
            flush()
        out.append(s)
    flush()
    return out


def sanitize_clue_summary(
    text: str,
    *,
    title: str = "",
    reason: str = "",
    max_chars: int = 700,
) -> str:
    """清洗脚本/脏抓取摘要：去导航、拼拆字、去掉会触发引用块的 > 行，整理为可读短文。"""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""

    # 已是干净要点列表 / 短文：勿再拼成一行
    if re.search(r"(?m)^页面要点：\s*$", raw) and re.search(r"(?m)^-\s+\S", raw):
        out = format_summary_for_markdown(raw)
        if len(out) > max_chars:
            out = out[: max_chars - 1].rstrip() + "…"
        return out
    if (
        raw.count("\n") >= 2
        and not re.search(r"(?m)^>{1,}\s*$", raw)
        and not re.search(r"(?m)^(OA|SRM|主页|产品展示)\s*$", raw)
        and sum(1 for ln in raw.splitlines() if 0 < len(ln.strip()) <= 2) <= 2
    ):
        out = format_summary_for_markdown(raw)
        if len(out) > max_chars:
            out = out[: max_chars - 1].rstrip() + "…"
        return out

    lines = [ln.strip() for ln in raw.split("\n")]
    lines = _join_broken_glyph_lines(lines)

    bullets: list[str] = []
    body: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        i += 1
        if not ln:
            continue
        low = ln.lower()
        if low in NAV_NOISE or ln in NAV_NOISE:
            continue
        if re.match(r"^(copyright|苏icp|京icp|邮编\s*：|地址\s*：|邮箱\s*：)", ln, re.I):
            continue
        if re.search(r"@|\.com\b", ln) and len(ln) < 80:
            continue
        # 单独的 >> 行：下一非空行视为卖点
        if re.fullmatch(r">+", ln):
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                bit = lines[i].strip()
                i += 1
                bit = re.sub(r"^>+\s*", "", bit)
                if len(bit) >= 4 and bit not in NAV_NOISE and bit.lower() not in NAV_NOISE:
                    bullets.append(bit)
            continue
        # 同行面包屑 / 卖点：>> xxx
        m = re.match(r"^>{1,}\s*(.+)$", ln)
        if m:
            bit = m.group(1).strip()
            if bit and bit not in NAV_NOISE and bit.lower() not in NAV_NOISE:
                if len(bit) >= 4:
                    bullets.append(bit)
            continue
        # 重复标题噪音
        if title and ln.replace(" ", "") == title.replace(" ", ""):
            continue
        if "有限公司_有限公司" in ln or (ln.count("_") >= 2 and "公司" in ln):
            continue
        if len(ln) <= 1:
            continue
        # 菜单式短词（无句号、偏导航）
        if len(ln) <= 16 and not re.search(r"[。！？；,.!?]", ln) and (
            ln.endswith(MENU_SUFFIXES) or ln in MENU_WORDS
        ):
            continue
        body.append(ln)

    # 脏页特征：短行过多或卖点较多 → 优先要点列表
    short_ratio = 0.0
    if lines:
        short_ratio = sum(1 for x in lines if 0 < len(x.strip()) <= 2) / max(
            len(lines), 1
        )

    parts: list[str] = []
    prefer_bullets = bool(bullets) and (
        short_ratio > 0.08 or len(bullets) >= 3 or len(body) < 4
    )
    if prefer_bullets:
        parts.append("页面要点：")
        for b in list(dict.fromkeys(bullets))[:8]:
            parts.append(f"- {b}")
    else:
        # 正常正文：合并为段落；过长时截断
        para = re.sub(r"\s+", " ", " ".join(body)).strip()
        # 去掉残留面包屑符号
        para = re.sub(r"\s*>+\s*", " ", para)
        para = re.sub(r"\s{2,}", " ", para).strip()
        # 新闻站：从首个「实质句」切开（去掉频道栏粘连）
        m_lead = re.search(
            r"((?:\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日).{20,})",
            para,
        )
        if not m_lead:
            m_lead = re.search(
                r"((?:获悉|讯（|报道）|将携|掌握|展示).{30,})",
                para,
            )
        if m_lead and m_lead.start() > 12:
            para = m_lead.group(1).strip()
        para = re.sub(
            r"(点击：?\s*|扫描到手机\s*|放大\s*|缩小\s*|回到顶部\s*)",
            "",
            para,
        )
        para = re.sub(r"\s{2,}", " ", para).strip()
        if para:
            parts.append(para)
        elif bullets:
            parts.append("页面要点：")
            for b in list(dict.fromkeys(bullets))[:8]:
                parts.append(f"- {b}")

    out = "\n".join(parts).strip()
    if not out and reason:
        out = f"（页面正文未能干净抽取，仅保留检索理由）{reason[:160]}"
    if len(out) > max_chars:
        out = out[: max_chars - 1].rstrip() + "…"
    return out


def format_summary_for_markdown(summary: str) -> str:
    """写入笔记时避免以 > 开头的行被 Obsidian 当成引用块。"""
    lines_out: list[str] = []
    for ln in (summary or "").splitlines():
        if re.match(r"^\s*>+", ln):
            ln = re.sub(r"^\s*>+\s*", "", ln)
            if ln:
                lines_out.append(f"- {ln}")
            continue
        lines_out.append(ln)
    return "\n".join(lines_out).strip()


def fetch_url_summary(url: str, *, max_chars: int = 900, timeout: int = 18) -> dict:
    """自动抓取 URL 可读摘要；失败不抛错，返回 status=fetch_failed。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": "",
            "summary": "",
            "error": "invalid_url",
        }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
            final_url = resp.geturl()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": "",
            "summary": "",
            "error": str(e)[:160],
        }

    page_title = ""
    summary = ""
    # 优先 readability / bs4（若已安装）
    try:
        from readability import Document  # type: ignore

        doc = Document(html)
        page_title = (doc.short_title() or "").strip()
        summary = _strip_html(doc.summary())
    except Exception:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                page_title = soup.title.string.strip()
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            summary = soup.get_text("\n", strip=True)
        except Exception:
            mt = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
            page_title = unescape(mt.group(1)).strip() if mt else ""
            summary = _strip_html(html)

    summary = sanitize_clue_summary(
        summary, title=page_title, max_chars=max_chars
    )
    if not summary:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": page_title,
            "summary": "",
            "error": "empty_body",
            "final_url": final_url,
        }
    return {
        "ok": True,
        "status": "script_fetched",
        "page_title": page_title,
        "summary": summary,
        "final_url": final_url,
        "error": "",
    }
