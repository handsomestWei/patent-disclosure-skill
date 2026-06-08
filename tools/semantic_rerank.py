# -*- coding: utf-8 -*-
"""
P2b 语义重排：对**已召回的候选集**（P0/P1 federate 结果）按与查询的 embedding 相似度重排。

为什么是"重排已召回集"而非"语料级向量召回"：真正的向量召回需要**用同一 embedding 空间预先
编码好的专利语料库**；Google Patents 的 ``embedding_v1`` 出自 Google 自有模型、无法把查询编进
同一空间，而全量专利实时编码不现实。故此处对**候选集**做语义重排，提升排序/精度，与 Agent 的
LLM 重排（``prompts/prior_art_search.md`` P1 第三步）互补，也便于批量/非交互场景。

**Embedding 后端可插拔，未配置即降级为 no-op**（保持架构一致：缺配置/缺网不报错、原样返回）：

- ``PATENT_EMBED_URL``：OpenAI 兼容的 embeddings 端点（如 ``https://api.openai.com/v1/embeddings``，
  或 Vertex/本地 text-embeddings-inference / ollama 的兼容端点）。
- ``PATENT_EMBED_MODEL``：模型名（如 ``text-embedding-3-small``）。
- ``PATENT_EMBED_API_KEY``：可选，作 ``Authorization: Bearer``（本地服务可留空）。
- ``PATENT_EMBED_TIMEOUT``：可选，秒，默认 30。

未设 URL 或 MODEL → ``embed_via_env`` 返回 ``None`` → ``rerank`` 原样返回（``applied=False``）。
仅用标准库（``urllib``）。
"""
from __future__ import annotations

import json
import math
import os
import urllib.request

from provider_base import Hit


def backend_name() -> str:
    """当前 embedding 后端的可读标识（不含密钥）；未配置为 ``none``。"""
    url = os.environ.get("PATENT_EMBED_URL", "").strip()
    model = os.environ.get("PATENT_EMBED_MODEL", "").strip()
    if not url or not model:
        return "none"
    return "http:%s" % model


def embed_via_env(texts: list[str]) -> list[list[float]] | None:
    """
    用环境变量配置的 OpenAI 兼容端点为一批文本求 embedding。未配置返回 ``None``；
    网络/解析失败抛异常（由 ``rerank`` 捕获并降级）。返回顺序与 ``texts`` 一致。
    """
    url = os.environ.get("PATENT_EMBED_URL", "").strip()
    model = os.environ.get("PATENT_EMBED_MODEL", "").strip()
    if not url or not model:
        return None
    key = os.environ.get("PATENT_EMBED_API_KEY", "").strip()
    try:
        timeout = float(os.environ.get("PATENT_EMBED_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        obj = json.loads(r.read())
    data = obj.get("data") or []
    vecs = [d.get("embedding") for d in data if isinstance(d, dict)]
    if len(vecs) != len(texts) or any(not v for v in vecs):
        raise ValueError(
            "embedding count mismatch: got %d for %d texts" % (len(vecs), len(texts))
        )
    return vecs


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度；任一零向量或维度不匹配返回 0.0。"""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _hit_text(h: Hit) -> str:
    """用于 embedding 的文本：标题 + 摘要（缺则退化为标题/公开号）。"""
    parts = [p for p in (h.title, h.abstract) if p]
    return " ".join(parts).strip() or (h.pub_number or "")


def rerank(
    query: str,
    hits: list[Hit],
    top_k: int | None = None,
    embed_fn=None,
) -> tuple[list[Hit], dict]:
    """
    对 ``hits`` 按与 ``query`` 的语义相似度降序重排，写入每条 ``Hit.score``，返回 ``(hits, info)``。
    ``top_k`` 截断；``embed_fn`` 可注入（默认 ``embed_via_env``，便于测试）。

    **降级为 no-op**（原样返回、``applied=False``）的情形：无 ``hits``、查询为空、后端未配置
    （``embed_fn`` 返回 ``None``）、或 embedding 调用异常——均不报错、不丢结果。
    """
    info = {"applied": False, "backend": backend_name(), "reason": "",
            "scored": 0, "top_k": top_k, "returned": len(hits)}
    if not hits:
        info["reason"] = "no hits"
        return hits, info
    if not (query or "").strip():
        info["reason"] = "empty query"
        return hits, info

    fn = embed_fn or embed_via_env
    try:
        vecs = fn([query] + [_hit_text(h) for h in hits])
    except Exception as e:  # 网络/解析失败：降级，不丢已召回结果
        info["reason"] = "embed error: %s" % repr(str(e))[:200]
        return hits, info
    if not vecs:
        info["reason"] = "embed backend not configured"
        return hits, info

    qv = vecs[0]
    for h, v in zip(hits, vecs[1:]):
        h.score = round(cosine(qv, v), 6)
    ranked = sorted(
        hits,
        key=lambda h: h.score if h.score is not None else float("-inf"),
        reverse=True,
    )
    if top_k and top_k > 0:
        ranked = ranked[:top_k]
    info.update(applied=True, scored=len(hits), returned=len(ranked))
    return ranked, info
