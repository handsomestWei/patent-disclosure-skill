#!/usr/bin/env python
"""
按公开号下载专利全文 PDF（本包取证入口，勿每次现写脚本）。

默认链路（见 references/patent_pdf_sources.yaml）：
  1) 用户已给本地 PDF / --url → 直接用
  2) 优先 computer-use MCP 桌面控制（真人浏览器，可下国知局单行本、过 WAF/验证码；Google Patents 连不上时亦用）
  3) 技能脚本：Google Patents 详情页 zh / en / 无后缀三页并行，读到 citation_pdf_url 即断开 → CDN 下载
  4) 已知示例 CDN（仅兜底）
  5) 仍失败：请用户提供 PDF

脚本默认不走国知局公布站（其单行本接口服务端常超时，见源表 unstable_or_skip）；
国知局单行本全文一律用 computer-use MCP 桌面控制（见源表 computer_use_mcp），
不要在脚本里加国知局链路。
外观设计（CN…S）Google 多无 PDF，改用 fetch_design_views.py。

用法：
  python skills/patent-reader/tools/extract/fetch_patent_pdf.py --pub CN119961390A \\
    -o outputs/patent_reader/read-CN119961390A-YYYYMMDDHHmm
  # → {outdir}/source/{PUB}.pdf

  python skills/patent-reader/tools/extract/fetch_patent_pdf.py --pub CN… -o RUN --save-html
  python skills/patent-reader/tools/extract/fetch_patent_pdf.py --url https://…/CNxxx.pdf -o RUN --pub CNxxx
"""
from __future__ import annotations

# Ensure tools/patent_reader is importable when run as a script.
from pathlib import Path as _Path
import sys as _sys

_PR_ROOT = _Path(__file__).resolve().parents[1]
_PKG = _PR_ROOT.parent
if str(_PR_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PR_ROOT))

import argparse
import json
import queue
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from patent_type import resolve_reader_patent_type

UA = "Mozilla/5.0 (compatible; patent-disclosure-skill/1.0)"
# 总时限（秒）：解析详情页 + 下载 PDF。连不上 Google 时尽快失败，不干等。
DEFAULT_TIMEOUT = 45
# 单个详情页的 socket 超时。citation_pdf_url 在页首约 2KB 处，正常 1 秒内读到。
PAGE_TIMEOUT = 8
# PDF 单次 socket 读写超时（不是总时长；总时长受 DEFAULT_TIMEOUT 约束）
PDF_SOCKET_TIMEOUT = 20
PDF_ATTEMPTS = 2
_PAGE_CHUNK = 8192
_PDF_CHUNK = 64 * 1024
_SSL_CTX = ssl.create_default_context()

_SOURCES_YAML = _PKG / "references" / "patent_pdf_sources.yaml"

CDN_HOST_RE = re.compile(
    r"https://patentimages\.storage\.googleapis\.com/[^\s\"'<>\\]+?\.pdf",
    re.I,
)
CITATION_PDF_RE = re.compile(
    r'name=["\']citation_pdf_url["\']\s+content=["\']([^"\']+)["\']'
    r'|content=["\']([^"\']+)["\']\s+name=["\']citation_pdf_url["\']',
    re.I,
)
PDF_LINK_RE = re.compile(
    r'href=["\'](https://patentimages\.storage\.googleapis\.com/[^"\']+\.pdf)["\']',
    re.I,
)


def normalize_pub(pub: str) -> str:
    return re.sub(r"\s+", "", (pub or "").strip()).upper()


def load_known_cdn_examples(yaml_path: Path | None = None) -> dict[str, str]:
    path = yaml_path or _SOURCES_YAML
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    # 轻量解析，避免强制 pyyaml 依赖
    out: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        if line.strip().startswith("known_cdn_examples:"):
            in_block = True
            continue
        if in_block:
            if line and not line.startswith(" ") and not line.startswith("\t"):
                break
            m = re.match(
                r"\s+([A-Z]{2}\d+[A-Z]?\d?)\s*:\s*[\"']([^\"']+)[\"']",
                line,
            )
            if m:
                out[m.group(1).upper()] = m.group(2).strip()
    return out


def google_patent_page_urls(pub: str) -> list[str]:
    p = normalize_pub(pub)
    return [
        f"https://patents.google.com/patent/{p}/zh",
        f"https://patents.google.com/patent/{p}/en",
        f"https://patents.google.com/patent/{p}",
    ]


def extract_pdf_urls_from_html(html: str, pub: str) -> list[str]:
    """从 Google Patents HTML 提取 PDF URL（去重，公开号匹配优先）。"""
    pub_u = normalize_pub(pub)
    found: list[str] = []

    for m in CITATION_PDF_RE.finditer(html):
        u = (m.group(1) or m.group(2) or "").strip()
        if u:
            found.append(u)

    for m in PDF_LINK_RE.finditer(html):
        found.append(m.group(1).strip())

    for m in CDN_HOST_RE.finditer(html):
        found.append(m.group(0).rstrip(".,);]"))

    # 规范化去重，优先含公开号的
    uniq: list[str] = []
    seen: set[str] = set()
    for u in found:
        u = u.replace("&amp;", "&")
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)

    prefer = [u for u in uniq if pub_u in u.upper()]
    rest = [u for u in uniq if pub_u not in u.upper()]
    return prefer + rest


def _open(url: str, *, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)


def read_page_pdf_urls(
    page: str,
    pub: str,
    *,
    timeout: float = PAGE_TIMEOUT,
    save_to: Path | None = None,
) -> tuple[list[str], int]:
    """读 Google 详情页，返回 (pdf_urls, 已读字节)。不存 HTML 时读到 citation_pdf_url 就断开。"""
    buf = bytearray()
    with _open(page, timeout=timeout) as resp:
        while True:
            chunk = resp.read(_PAGE_CHUNK)
            if not chunk:
                break
            buf += chunk
            if (
                save_to is None
                and b"citation_pdf_url" in buf
                and CITATION_PDF_RE.search(buf.decode("utf-8", errors="ignore"))
            ):
                break
    html = buf.decode("utf-8", errors="replace")
    if save_to is not None:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(html, encoding="utf-8")
    return extract_pdf_urls_from_html(html, pub), len(buf)


def download_pdf_bytes(
    url: str,
    *,
    timeout: float = PDF_SOCKET_TIMEOUT,
    deadline: float | None = None,
) -> bytes:
    """``deadline`` 为 ``time.monotonic()`` 时刻；超过即中断，避免慢速下载拖满 socket 超时。"""
    parts: list[bytes] = []
    with _open(url, timeout=timeout) as resp:
        while True:
            chunk = resp.read(_PDF_CHUNK)
            if not chunk:
                break
            parts.append(chunk)
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError(f"PDF 下载超出总时限: {url}")
    data = b"".join(parts)
    if not data.startswith(b"%PDF"):
        raise ValueError(f"not a PDF (magic={data[:8]!r}): {url}")
    if len(data) < 5000:
        raise ValueError(f"PDF too small ({len(data)} bytes): {url}")
    return data


def _download_with_retry(
    urls: list[str],
    *,
    deadline: float,
    log: list[str],
) -> tuple[str, bytes]:
    """按候选顺序下载；网络抖动重试一次，404 / 非 PDF 不重试直接换下一个。"""
    last: Exception | None = None
    for url in urls:
        for attempt in range(1, PDF_ATTEMPTS + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                raise TimeoutError(
                    f"PDF 下载超出总时限。attempts={' | '.join(log)}"
                ) from last
            try:
                data = download_pdf_bytes(
                    url,
                    timeout=min(PDF_SOCKET_TIMEOUT, remaining),
                    deadline=deadline,
                )
                log.append(f"ok_pdf:{url}:try{attempt}:bytes={len(data)}")
                return url, data
            except urllib.error.HTTPError as e:
                last = e
                log.append(f"fail_pdf:{url}:HTTP{e.code}")
                if e.code == 404:
                    break
            except ValueError as e:
                last = e
                log.append(f"fail_pdf:{url}:{e}")
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                log.append(f"fail_pdf:{url}:try{attempt}:{type(e).__name__}:{e}")
    raise FileNotFoundError(
        f"PDF 直链均下载失败。attempts={' | '.join(log)}"
    ) from last


def resolve_pdf_url(
    pub: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    save_html_dir: Path | None = None,
    known_cdn: dict[str, str] | None = None,
) -> tuple[str, str, list[str]]:
    """返回 (pdf_url, source_id, attempts_log)。三个详情页并行，先拿到直链的赢。"""
    pub_u = normalize_pub(pub)
    log: list[str] = []
    known = known_cdn if known_cdn is not None else load_known_cdn_examples()
    pages = google_patent_page_urls(pub_u)
    page_timeout = max(1.0, min(float(timeout), PAGE_TIMEOUT))
    results: queue.Queue = queue.Queue()

    def probe(i: int, page: str) -> None:
        save_to = save_html_dir / f"_gp_{i}.html" if save_html_dir is not None else None
        try:
            urls, n = read_page_pdf_urls(page, pub_u, timeout=page_timeout, save_to=save_to)
            line = f"ok_page:{page}:read={n}" if urls else f"no_cdn_in_page:{page}"
            results.put((urls, line, None))
        except urllib.error.HTTPError as e:
            results.put(([], f"fail_page:{page}:HTTP{e.code}", e.code))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            results.put(([], f"fail_page:{page}:{type(e).__name__}:{e}", None))

    # daemon 线程：赢家返回后，慢的那页不拖住进程退出
    for i, page in enumerate(pages):
        threading.Thread(target=probe, args=(i, page), daemon=True).start()

    deadline = time.monotonic() + page_timeout + 2
    codes: list[int | None] = []
    no_cdn = 0
    for _ in pages:
        try:
            urls, line, code = results.get(timeout=max(0.1, deadline - time.monotonic()))
        except queue.Empty:
            log.append(f"page_timeout:{page_timeout:.0f}s")
            break
        log.append(line)
        if urls:
            log.append(f"cdn_from_page:{urls[0]}")
            return urls[0], "google_patents_page", log
        if line.startswith("no_cdn_in_page:"):
            no_cdn += 1
        else:
            codes.append(code)

    if pub_u in known:
        log.append(f"known_cdn_example:{known[pub_u]}")
        return known[pub_u], "known_cdn_examples", log

    if no_cdn == 0 and 404 in codes:
        reason = (
            f"Google Patents 未收录 {pub_u}（新公开的专利通常 1–3 周后才上 Google）。"
        )
    elif no_cdn:
        reason = f"Google Patents 有 {pub_u} 详情页但没有 PDF（外观设计多如此，改用 fetch_design_views.py）。"
    else:
        reason = "连不上 Google Patents（详情页失败或超时），请检查网络后重试。"
    raise FileNotFoundError(reason + "请用户提供 PDF。attempts=" + " | ".join(log))


def fetch_patent_pdf(
    pub: str,
    outdir: Path,
    *,
    url: str = "",
    timeout: float = DEFAULT_TIMEOUT,
    save_html: bool = False,
    force: bool = False,
) -> dict:
    """下载到 {outdir}/source/{PUB}.pdf，返回状态 dict。``timeout`` 是总时限（秒）。"""
    started = time.monotonic()
    deadline = started + max(5.0, float(timeout))
    pub_u = normalize_pub(pub)
    if not pub_u:
        raise ValueError("empty pub number")

    outdir = Path(outdir)
    source_dir = outdir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    dest = source_dir / f"{pub_u}.pdf"

    status: dict = {
        "pub": pub_u,
        "outdir": str(outdir.resolve()),
        "pdf_path": str(dest.resolve()),
        "ok": False,
        "source_id": "",
        "pdf_url": "",
        "bytes": 0,
        "attempts": [],
        "patent_type": None,
        "patent_type_label_zh": None,
        "patent_type_source": None,
    }
    inferred = resolve_reader_patent_type(pub=pub_u)
    if inferred.get("patent_type"):
        status["patent_type"] = inferred["patent_type"]
        status["patent_type_label_zh"] = inferred.get("label_zh")
        status["patent_type_source"] = inferred.get("source")

    if dest.is_file() and dest.stat().st_size >= 5000 and not force:
        head = dest.read_bytes()[:4]
        if head == b"%PDF":
            status.update(
                {
                    "ok": True,
                    "source_id": "local_existing",
                    "bytes": dest.stat().st_size,
                    "attempts": ["skip_existing"],
                }
            )
            return status

    pdf_url = (url or "").strip()
    source_id = "direct_url"
    attempts: list[str] = []
    candidates: list[str] = []

    if not pdf_url:
        pdf_url, source_id, g_attempts = resolve_pdf_url(
            pub_u,
            timeout=timeout,
            save_html_dir=(outdir if save_html else None),
        )
        attempts.extend(g_attempts)
        candidates.append(pdf_url)
        known = load_known_cdn_examples().get(pub_u)
        if known and known != pdf_url:
            candidates.append(known)
    else:
        attempts.append(f"direct_url:{pdf_url}")
        candidates.append(pdf_url)

    got_url, data = _download_with_retry(candidates, deadline=deadline, log=attempts)
    if got_url != pdf_url:
        source_id = "known_cdn_examples"
    dest.write_bytes(data)

    status.update(
        {
            "ok": True,
            "source_id": source_id,
            "pdf_url": got_url,
            "bytes": len(data),
            "attempts": attempts,
            "elapsed_sec": round(time.monotonic() - started, 2),
        }
    )
    return status


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pub", required=True, help="公开号，如 CN119961390A")
    ap.add_argument(
        "-o",
        "--outdir",
        type=Path,
        required=True,
        help="RUN 目录；PDF 写入 {outdir}/source/{PUB}.pdf",
    )
    ap.add_argument("--url", default="", help="已知 PDF 直链时跳过页面解析")
    ap.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"总时限秒数（解析 + 下载），默认 {DEFAULT_TIMEOUT}",
    )
    ap.add_argument(
        "--save-html",
        action="store_true",
        help="保存 Google Patents HTML 到 outdir/_gp_*.html（排障）",
    )
    ap.add_argument("--force", action="store_true", help="覆盖已有 PDF")
    ap.add_argument(
        "--status-json",
        type=Path,
        default=None,
        help="写入状态 JSON（默认 {outdir}/fetch_pdf_status.json）",
    )
    args = ap.parse_args(argv)

    try:
        status = fetch_patent_pdf(
            args.pub,
            args.outdir,
            url=args.url,
            timeout=args.timeout,
            save_html=args.save_html,
            force=args.force,
        )
    except Exception as e:
        err = {
            "ok": False,
            "pub": normalize_pub(args.pub),
            "error": f"{type(e).__name__}: {e}",
        }
        out_json = args.status_json or (args.outdir / "fetch_pdf_status.json")
        args.outdir.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(err, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"FAIL {err['error']}", file=sys.stderr)
        print(
            "HINT: Google Patents 未取到全文 PDF。请用户提供 PDF；"
            "外观设计改用 fetch_design_views.py。源表见 references/patent_pdf_sources.yaml",
            file=sys.stderr,
        )
        return 1

    out_json = args.status_json or (args.outdir / "fetch_pdf_status.json")
    out_json.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"OK pdf={status['pdf_path']} bytes={status['bytes']} "
        f"source={status['source_id']} elapsed={status.get('elapsed_sec', 0)}s"
    )
    if status.get("patent_type"):
        print(
            f"PATENT_TYPE: {status['patent_type']} "
            f"({status.get('patent_type_label_zh')}) "
            f"source={status.get('patent_type_source')}"
        )
    print(f"FETCH_PDF_STATUS: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
