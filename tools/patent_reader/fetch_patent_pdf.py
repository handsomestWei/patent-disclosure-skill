#!/usr/bin/env python3
"""
按公开号下载专利全文 PDF（解读模式固化入口，勿每次现写脚本）。

默认链路（见 references/patent_pdf_sources.yaml）：
  1) 用户已给本地 PDF / --url → 直接用
  2) Google Patents 详情页解析 CDN（zh → en → 无语言后缀）
  3) 已知示例 CDN（references 里 known_cdn_examples，仅兜底）
  4) 失败时提示：用国知局 epub 核验公开号，或请用户自备 PDF

用法：
  python tools/patent_reader/fetch_patent_pdf.py --pub CN119961390A \\
    -o tmp/patent_reader/read-CN119961390A-YYYYMMDDHHmm
  # → {outdir}/source/{PUB}.pdf

  python tools/patent_reader/fetch_patent_pdf.py --pub CN… -o RUN --save-html
  python tools/patent_reader/fetch_patent_pdf.py --url https://…/CNxxx.pdf -o RUN --pub CNxxx
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (compatible; patent-disclosure-skill/1.0)"
DEFAULT_TIMEOUT = 90

# 仓库根：tools/patent_reader/ → ../..
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCES_YAML = _REPO_ROOT / "references" / "patent_pdf_sources.yaml"

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


def http_get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    binary: bool = False,
) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
    if binary:
        return data
    # Google 页多为 utf-8；失败则 replace
    return data.decode("utf-8", errors="replace")


def download_pdf_bytes(url: str, *, timeout: int = 120) -> bytes:
    data = http_get(url, timeout=timeout, binary=True)
    assert isinstance(data, bytes)
    if not data.startswith(b"%PDF"):
        raise ValueError(f"not a PDF (magic={data[:8]!r}): {url}")
    if len(data) < 5000:
        raise ValueError(f"PDF too small ({len(data)} bytes): {url}")
    return data


def resolve_pdf_url(
    pub: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    save_html_dir: Path | None = None,
    known_cdn: dict[str, str] | None = None,
) -> tuple[str, str, list[str]]:
    """返回 (pdf_url, source_id, attempts_log)。"""
    pub_u = normalize_pub(pub)
    log: list[str] = []
    known = known_cdn if known_cdn is not None else load_known_cdn_examples()

    for i, page in enumerate(google_patent_page_urls(pub_u)):
        try:
            html = http_get(page, timeout=timeout)
            assert isinstance(html, str)
            log.append(f"ok_page:{page}:len={len(html)}")
            if save_html_dir is not None:
                save_html_dir.mkdir(parents=True, exist_ok=True)
                (save_html_dir / f"_gp_{i}.html").write_text(html, encoding="utf-8")
            urls = extract_pdf_urls_from_html(html, pub_u)
            if urls:
                log.append(f"cdn_from_page:{urls[0]}")
                return urls[0], "google_patents_page", log
            log.append(f"no_cdn_in_page:{page}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            log.append(f"fail_page:{page}:{type(e).__name__}:{e}")

    if pub_u in known:
        log.append(f"known_cdn_example:{known[pub_u]}")
        return known[pub_u], "known_cdn_examples", log

    raise FileNotFoundError(
        "未能解析 PDF 直链。可：1) 检查网络后重试；2) 用 cnipa_epub_search 核验公开号；"
        "3) 用户自备 PDF 后直接 extract。attempts=" + " | ".join(log)
    )


def fetch_patent_pdf(
    pub: str,
    outdir: Path,
    *,
    url: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    save_html: bool = False,
    force: bool = False,
) -> dict:
    """下载到 {outdir}/source/{PUB}.pdf，返回状态 dict。"""
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
    }

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

    if not pdf_url:
        pdf_url, source_id, attempts = resolve_pdf_url(
            pub_u,
            timeout=timeout,
            save_html_dir=(outdir if save_html else None),
        )
    else:
        attempts.append(f"direct_url:{pdf_url}")

    data = download_pdf_bytes(pdf_url, timeout=max(timeout, 120))
    dest.write_bytes(data)

    status.update(
        {
            "ok": True,
            "source_id": source_id,
            "pdf_url": pdf_url,
            "bytes": len(data),
            "attempts": attempts,
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
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
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
            "HINT: 无稳定国内免费全文镜像；可 cnipa_epub_search 核验后自备 PDF，"
            "或稍后重试 Google Patents / CDN。源表见 references/patent_pdf_sources.yaml",
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
        f"source={status['source_id']}"
    )
    print(f"FETCH_PDF_STATUS: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
