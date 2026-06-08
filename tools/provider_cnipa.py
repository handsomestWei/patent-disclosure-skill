# -*- coding: utf-8 -*-
"""
国知局公布公告站 provider：包装现有 ``cnipa_epub_*`` 能力为统一 ``Provider`` 接口，
**不改变**抓取 / 解析行为（仍走 Playwright，结果页 HTML 不落盘）。

CN 专利的官方权威来源，故 ``quality_rank`` 最高（最优先）；缺 Playwright 时 ``available()``
返回 False，编排器跳过并回退到其它数据源。
"""
from __future__ import annotations

from provider_base import Hit, Provider


class CnipaEpubProvider(Provider):
    name = "cnipa_epub"
    quality_rank = 10  # 中国专利官方公布站，CN 检索优先
    prefers_single_term = True  # 走 Playwright，多词应分多次进程调用（编排器会告警）

    def available(self) -> tuple[bool, str]:
        try:
            import playwright  # noqa: F401
        except ImportError:
            return (
                False,
                "playwright not installed (pip install -r tools/requirements-cnipa.txt)",
            )
        return (True, "")

    def search(self, term: str) -> list[Hit]:
        from cnipa_epub_crawler import search_epub_keyword

        _html, hits = search_epub_keyword(term)
        return [
            Hit(
                source=self.name,
                title=h.title,
                pub_number=h.pub_number,
                link=h.link,
                abstract=h.abstract,
            )
            for h in hits
        ]
