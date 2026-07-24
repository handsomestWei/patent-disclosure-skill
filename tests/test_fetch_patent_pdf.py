"""fetch_patent_pdf：HTML/CDN 解析与 known_cdn 兜底（不依赖外网）。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "patent_reader"))

from fetch_patent_pdf import (  # noqa: E402
    extract_pdf_urls_from_html,
    load_known_cdn_examples,
    normalize_pub,
    resolve_pdf_url,
)


SAMPLE_HTML = """
<html>
<meta name="citation_pdf_url" content="https://patentimages.storage.googleapis.com/58/1b/9b/07a9f35635df34/CN119961390A.pdf">
<title>CN119961390A - demo</title>
<a href="https://patentimages.storage.googleapis.com/58/1b/9b/07a9f35635df34/CN119961390A.pdf" itemprop="pdfLink">Download PDF</a>
</html>
"""


class FetchPatentPdfTest(unittest.TestCase):
    def test_normalize_pub(self) -> None:
        self.assertEqual(normalize_pub(" cn119961390a "), "CN119961390A")

    def test_extract_cdn_from_html(self) -> None:
        urls = extract_pdf_urls_from_html(SAMPLE_HTML, "CN119961390A")
        self.assertTrue(urls)
        self.assertIn("CN119961390A.pdf", urls[0])
        self.assertTrue(urls[0].startswith("https://patentimages.storage.googleapis.com/"))

    def test_load_known_cdn_examples(self) -> None:
        known = load_known_cdn_examples()
        self.assertIn("CN114552122A", known)
        self.assertTrue(known["CN114552122A"].endswith(".pdf"))

    def test_resolve_falls_back_to_known_cdn(self) -> None:
        """页面全部失败时，用 known_cdn_examples 兜底。"""

        def boom(*_a, **_k):
            raise TimeoutError("simulated")

        import fetch_patent_pdf as mod

        old = mod.http_get
        mod.http_get = boom  # type: ignore[assignment]
        try:
            url, source, log = resolve_pdf_url(
                "CN114552122A",
                timeout=1,
                known_cdn={
                    "CN114552122A": "https://patentimages.storage.googleapis.com/c2/6c/51/75412585086edf/CN114552122A.pdf"
                },
            )
            self.assertEqual(source, "known_cdn_examples")
            self.assertIn("CN114552122A.pdf", url)
            self.assertTrue(any("fail_page" in x for x in log))
        finally:
            mod.http_get = old

    def test_fetch_uses_direct_url(self) -> None:
        from fetch_patent_pdf import fetch_patent_pdf
        import fetch_patent_pdf as mod

        fake = b"%PDF-1.4" + b"0" * 6000
        calls: list[str] = []

        def fake_dl(url: str, *, timeout: int = 120) -> bytes:
            calls.append(url)
            return fake

        old = mod.download_pdf_bytes
        mod.download_pdf_bytes = fake_dl  # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as td:
                out = Path(td)
                st = fetch_patent_pdf(
                    "CN1",
                    out,
                    url="https://example.com/CN1.pdf",
                )
                self.assertTrue(st["ok"])
                self.assertEqual(st["source_id"], "direct_url")
                self.assertTrue((out / "source" / "CN1.pdf").is_file())
                self.assertEqual(calls, ["https://example.com/CN1.pdf"])
        finally:
            mod.download_pdf_bytes = old


if __name__ == "__main__":
    raise SystemExit(unittest.main())
