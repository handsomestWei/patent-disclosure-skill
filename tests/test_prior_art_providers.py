# -*- coding: utf-8 -*-
"""
查新数据源抽象层（P0）离线单元测试：不依赖网络。

覆盖：
- ``Hit.dedupe_key`` 归一化与 ``merge_dedupe`` 去重 / 空字段补全
- Google Patents ``parse_xhr_json`` 针对样本 JSON 的解析
- 编排器 ``run`` 的回退（fallback）、联邦（federate）、跳过不可用源、单源异常不中断

在仓库根目录执行::

  python tests/test_prior_art_providers.py
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from provider_base import Hit, Provider, merge_dedupe, to_jsonable  # noqa: E402
from provider_google_patents import parse_xhr_json  # noqa: E402
import prior_art_search  # noqa: E402


class FakeProvider(Provider):
    def __init__(self, name, rank, hits_by_term=None, available=True,
                 reason="", raises=False):
        self.name = name
        self.quality_rank = rank
        self._hits = hits_by_term or {}
        self._available = available
        self._reason = reason
        self._raises = raises
        self.searched = []

    def available(self):
        return (self._available, self._reason)

    def search(self, term):
        self.searched.append(term)
        if self._raises:
            raise RuntimeError("boom")
        return list(self._hits.get(term, []))


def _h(source, num=None, title=None, link=None, abstract=None):
    return Hit(source=source, pub_number=num, title=title, link=link, abstract=abstract)


def test_dedupe_key_normalizes_pub_number():
    assert _h("x", num="CN 123456789 A").dedupe_key() == "CN123456789A"
    assert _h("x", link="http://e/p").dedupe_key() == "http://e/p"
    assert _h("x", title="A long title here").dedupe_key() == "A long title here"
    assert _h("x").dedupe_key() == ""


def test_merge_dedupe_backfills_citation_fields_but_not_abstract():
    a = _h("cnipa", num="CN111A", title=None, link=None, abstract=None)
    # 同号，后到源带著录字段与摘要
    b = _h("google", num="CN111A", title="标题乙", link="http://x", abstract="机翻摘要")
    c = _h("google", num="CN222B", title="标题丙")
    out = merge_dedupe([[a], [b, c]])
    assert len(out) == 2
    first = out[0]
    assert first.pub_number == "CN111A"
    assert first.source == "cnipa"          # 先到为主，source 不变
    assert first.title == "标题乙"           # 著录字段跨源补全
    assert first.link == "http://x"          # 著录字段跨源补全
    assert first.abstract is None            # abstract 不跨源补全（忠于来源）
    assert out[1].pub_number == "CN222B"


def test_merge_dedupe_skips_empty_keys():
    assert merge_dedupe([[Hit(source="x")]]) == []


def test_parse_xhr_json_extracts_hits():
    obj = {
        "results": {
            "cluster": [
                {
                    "result": [
                        {"patent": {
                            "publication_number": "CN114820000A",
                            "title": "一种<b>调度</b>方法",
                            "snippet": "本发明涉及任务<b>调度</b>...",
                        }},
                        {"patent": {
                            "publication_number": "US20240118920A1",
                            "title": "Scheduling system",
                            "snippet": "A method for scheduling",
                        }},
                    ]
                }
            ]
        }
    }
    hits = parse_xhr_json(obj)
    assert len(hits) == 2
    assert hits[0].pub_number == "CN114820000A"
    assert hits[0].title == "一种调度方法"          # 高亮标签被剥离
    assert hits[0].abstract == "本发明涉及任务调度..."
    assert hits[0].link == "https://patents.google.com/patent/CN114820000A/en"
    assert hits[0].source == "google_patents"


def test_parse_xhr_json_handles_empty_and_malformed():
    assert parse_xhr_json({}) == []
    assert parse_xhr_json({"results": {}}) == []
    assert parse_xhr_json({"results": {"cluster": [{"result": [{"patent": {}}]}]}}) == []


def test_run_fallback_stops_at_first_with_hits():
    p1 = FakeProvider("p1", 10, {"t": [_h("p1", num="CN1A")]})
    p2 = FakeProvider("p2", 20, {"t": [_h("p2", num="CN2A")]})
    out = prior_art_search.run(["t"], [p1, p2], mode="fallback")
    assert [h.pub_number for h in out] == ["CN1A"]
    assert p2.searched == []  # 第一个有命中即停，第二个未被调用


def test_run_fallback_advances_when_first_empty():
    p1 = FakeProvider("p1", 10, {"t": []})           # 无命中
    p2 = FakeProvider("p2", 20, {"t": [_h("p2", num="CN2A")]})
    out = prior_art_search.run(["t"], [p1, p2], mode="fallback")
    assert [h.pub_number for h in out] == ["CN2A"]
    assert p2.searched == ["t"]


def test_run_skips_unavailable_provider():
    p1 = FakeProvider("p1", 10, available=False, reason="no key")
    p2 = FakeProvider("p2", 20, {"t": [_h("p2", num="CN2A")]})
    out = prior_art_search.run(["t"], [p1, p2], mode="fallback")
    assert [h.pub_number for h in out] == ["CN2A"]
    assert p1.searched == []


def test_run_resilient_to_provider_exception():
    p1 = FakeProvider("p1", 10, raises=True)
    p2 = FakeProvider("p2", 20, {"t": [_h("p2", num="CN2A")]})
    out = prior_art_search.run(["t"], [p1, p2], mode="fallback")
    assert [h.pub_number for h in out] == ["CN2A"]  # 异常源被跳过，链路不中断


def test_run_warns_when_serial_source_gets_multiple_terms():
    p = FakeProvider("cnipa", 10, {"a": [_h("cnipa", num="CN1A")], "b": []})
    p.prefers_single_term = True
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        prior_art_search.run(["a", "b"], [p], mode="fallback")
    assert "PA_WARN" in buf.getvalue()
    assert p.searched == ["a", "b"]  # 仍执行（仅告警，不阻断）


def test_run_no_warn_for_serial_source_single_term():
    p = FakeProvider("cnipa", 10, {"a": [_h("cnipa", num="CN1A")]})
    p.prefers_single_term = True
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        prior_art_search.run(["a"], [p], mode="fallback")
    assert "PA_WARN" not in buf.getvalue()


def test_run_federate_merges_all_sources():
    p1 = FakeProvider("p1", 10, {"t": [_h("p1", num="CN1A")]})
    p2 = FakeProvider("p2", 20, {"t": [_h("p2", num="CN2A"), _h("p2", num="CN1A")]})
    out = prior_art_search.run(["t"], [p1, p2], mode="federate")
    nums = sorted(h.pub_number for h in out)
    assert nums == ["CN1A", "CN2A"]      # 跨源去重
    assert p2.searched == ["t"]          # federate 下所有源都跑


def test_to_jsonable_shape():
    rows = to_jsonable([_h("google_patents", num="CN1A", title="t", link="u", abstract="a")])
    assert rows == [{
        "source": "google_patents", "title": "t",
        "pub_number": "CN1A", "link": "u", "abstract": "a",
    }]


def _run_all():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print("ok  -", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL-", fn.__name__, "::", e)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("ERR -", fn.__name__, "::", type(e).__name__, e)
    print("\n%d/%d passed" % (len(funcs) - failed, len(funcs)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
