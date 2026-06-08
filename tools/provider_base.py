# -*- coding: utf-8 -*-
"""
查新数据源抽象层（P0）：统一命中结构 ``Hit`` + 数据源接口 ``Provider`` + 合并去重工具。

设计目标：把"国知局爬虫"从主干降级为众多 provider 之一，新增/替换数据源时**不动编排逻辑**；
单个 provider 不可用或抓取失败时，编排器（``prior_art_search.py``）按质量序**回退**到下一个，
从而消除"单点爬站"故障。

Provider 约定：

- ``name``：稳定的机器标识（写入 ``Hit.source``，便于在交底书 1.1 标注公开数据库名）。
- ``quality_rank``：**越小优先级越高**（回退/合并排序用）。
- ``available()``：返回 ``(bool, reason)``；缺依赖 / 缺密钥 / 明显不可用时为 ``False``，
  编排器**跳过且不计为失败**。
- ``search(term)``：对单个检索词返回 ``list[Hit]``；网络等运行期异常应由 provider **自行吞掉
  并返回 []**（或抛出由编排器捕获），不得让某个数据源的异常中断整条链路。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass
class Hit:
    """统一命中结构（跨数据源）。字段尽力填充，可能为空。"""

    source: str  # provider.name，如 "cnipa_epub" / "google_patents"
    title: str | None = None
    pub_number: str | None = None
    link: str | None = None
    abstract: str | None = None

    def dedupe_key(self) -> str:
        """去重主键：公开号（归一化）> 链接 > 标题前缀。"""
        return (
            (self.pub_number or "").replace(" ", "").upper()
            or (self.link or "")
            or (self.title or "")[:120]
        )


class Provider(ABC):
    """单个查新数据源。子类须设置 ``name`` / ``quality_rank`` 并实现两个方法。"""

    name: str = "base"
    quality_rank: int = 100
    #: 该源单次调用宜只处理一个检索词（如 Playwright 类抓取，多词单进程易超时）。
    #: 编排器对这类源在收到多词时会打印 ``PA_WARN`` 提示 Agent 改为每词一次调用。
    prefers_single_term: bool = False

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """是否可用；不可用时返回原因（ASCII，供 stderr 诊断）。"""
        raise NotImplementedError

    @abstractmethod
    def search(self, term: str) -> list[Hit]:
        """对单个检索词返回命中列表。"""
        raise NotImplementedError


#: 跨源去重时可安全补全的字段。**不含 ``abstract``**：摘要须忠于其来源
#: （``source``），跨源补全会使一条命中的摘要来自另一数据库却仍标着原 ``source``，
#: 与 ``prior_art_search.md``「abstract 必用、1.1 标注公开数据库名」相悖。
_BACKFILL_FIELDS = ("title", "pub_number", "link")


def merge_dedupe(hit_lists: list[list[Hit]]) -> list[Hit]:
    """
    跨词 / 跨数据源按 ``dedupe_key`` 合并去重；保留先出现者，并用后到者补全其**空的著录字段**
    （``title`` / ``pub_number`` / ``link``）。**不跨源补全 ``abstract``**，以保持摘要与 ``source`` 一致。
    """
    out: list[Hit] = []
    index: dict[str, Hit] = {}
    for hits in hit_lists:
        for h in hits:
            key = h.dedupe_key()
            if not key:
                continue
            cur = index.get(key)
            if cur is None:
                index[key] = h
                out.append(h)
                continue
            for field_name in _BACKFILL_FIELDS:
                if not getattr(cur, field_name) and getattr(h, field_name):
                    setattr(cur, field_name, getattr(h, field_name))
    return out


def to_jsonable(hits: list[Hit]) -> list[dict]:
    """供 JSON 序列化。"""
    return [asdict(h) for h in hits]
