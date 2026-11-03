"""线索落地：clues/ 笔记与索引、附录 B、Canvas 卡片数据。"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .matching import _claim_key_to_num, _clue_highlight, match_clue_to_note, resolve_feature_entry
from .model import (
    _region_text,
    _table_wikilink,
    agent_fits_for,
    clue_filename,
    filter_clues,
    normalize_anchor_fits,
    normalize_clue,
)
from .summary import fetch_url_summary, format_summary_for_markdown, sanitize_clue_summary
from .vocab import DEFAULT_MAX_CLUES


APPENDIX_B_RE = re.compile(
    r"(###\s*B\.\s*公开检索线索[\s\S]*?)(?=^##\s+|\Z)",
    re.M,
)


def render_clue_note(
    clue: dict,
    *,
    pub: str,
    note_link: str = "",
) -> str:
    claims = clue.get("related_claims") or []
    feats = clue.get("related_features") or []
    status = clue.get("status") or "draft"
    fetched_at = clue.get("fetched_at") or ""
    summary = format_summary_for_markdown(
        sanitize_clue_summary(
            clue.get("summary") or "",
            title=clue.get("title") or "",
            reason=clue.get("reason") or "",
        )
    )
    page_title = (clue.get("page_title") or "").strip()
    # 去掉「公司_公司」重复标题噪音
    page_title = re.sub(r"(_[^_]*){2,}$", "", page_title).strip("_") or page_title
    err = (clue.get("fetch_error") or "").strip()
    lines = [
        "---",
        "tags:",
        "  - patent/clue",
        "cssclasses:",
        "  - patent-clue",
        f"pub_number: {pub}",
        f"clue_id: {clue.get('clue_id') or ''}",
        f"confidence: {clue.get('confidence') or '中'}",
        f"status: {status}",
        f"url: {clue.get('url') or ''}",
        "related_claims:",
    ]
    if claims:
        for n in claims:
            lines.append(f"  - {n}")
    else:
        lines.append("  []")
    lines.append("related_features:")
    if feats:
        for f in feats:
            lines.append(f"  - {json.dumps(f, ensure_ascii=False)}")
    else:
        lines.append("  []")
    if fetched_at:
        lines.append(f"fetched_at: {fetched_at}")
    lines.extend(
        [
            "---",
            f"# 线索：{clue.get('title') or '未命名'}",
            "",
            "> [!warning] 推测线索",
            "> 公开网页语境，**不构成法律意见**，也不是说明书/权利要求证据。",
            "",
            "## 元信息",
            "",
            f"- **置信度**：{clue.get('confidence') or '中'}",
            *([f"- **地区**：{_region_text(clue)}"] if _region_text(clue) else []),
            f"- **来源**：[打开原文]({clue.get('url') or ''})",
            f"- **与本案关系**：{clue.get('reason') or '—'}",
            f"- **状态**：{status}",
        ]
    )
    if note_link:
        lines.append(f"- **所属解读**：[[{note_link}|打开解读]]")
    lines.extend(["", "## 页面摘要", ""])
    if page_title:
        lines.append(f"**页面标题**：{page_title}")
        lines.append("")
    if summary:
        # 列表/段落直接写；勿把原始网页整页粘贴进笔记
        lines.append(summary)
        lines.append("")
    elif err:
        lines.append(f"（抓取未成功：{err}。请 Agent 重读该 URL，或启用脚本降级。）")
        lines.append("")
    else:
        lines.append(
            "（暂无摘要。主路径应由 Agent 写入可读短文/要点列表，勿粘贴整页导航。）"
        )
        lines.append("")
    lines.extend(["", "## 可能相关权项 / 特征", ""])
    if claims:
        lines.append("- **权项**：" + "、".join(f"权{n}" for n in claims))
    if feats:
        lines.append("- **特征共现**：" + "；".join(feats))
    if not claims and not feats:
        lines.append("- （弱匹配未命中；仍可作行业语境参考）")
    lines.append("")
    return "\n".join(lines)


def render_clues_index(clues: list[dict], *, pub: str, note_link: str = "") -> str:
    lines = [
        "---",
        "tags:",
        "  - patent/clue-index",
        "---",
        f"# `{pub}` 公开线索索引",
        "",
        "> 推测层材料，可手工追加笔记后在此补链。**不构成法律意见**。",
        "",
    ]
    if note_link:
        lines.append(f"- 解读：[[{note_link}|打开]]")
        lines.append("")
    lines.extend(
        [
            "| 线索 | 置信 | 状态 | 可能相关 |",
            "| --- | --- | --- | --- |",
        ]
    )
    # 索引在 clues/ 子目录：链到同目录笔记用短路径；权项锚点在上级专利目录
    claim_base = f"{pub}_权项锚点"
    for c in clues:
        fname = c.get("filename") or ""
        stem = Path(fname).stem if fname else c.get("clue_id") or "线索"
        title = (c.get("title") or stem)[:40]
        claims = c.get("related_claims") or []
        if claims:
            rel = "、".join(
                _table_wikilink(f"{claim_base}#^claim-{n}", f"权{n}") for n in claims
            )
        else:
            rel = "—"
        # 索引页本身在 clues/ 下，链同目录笔记勿加 clues/ 前缀
        clue_cell = _table_wikilink(stem, title)
        lines.append(
            f"| {clue_cell} | {c.get('confidence') or '中'} "
            f"| {c.get('status') or '—'} | {rel} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_appendix_b(clues: list[dict], *, clues_dir_link: str) -> str:
    if not clues:
        return (
            "### B. 公开检索线索\n\n"
            "> [!warning]- 公开检索线索\n"
            ">\n"
            "> 未发现可核验的公开对应，可能为防御性/储备专利。\n"
        )
    lines = [
        "### B. 公开检索线索",
        "",
        "> [!warning]- 公开检索线索",
        ">",
        f"> 详情与抓取摘要见 [[{clues_dir_link}|线索文件夹]]（最多保留高置信条目）。",
        ">",
    ]
    for c in clues:
        stem = Path(c.get("filename") or "x.md").stem
        title = c.get("title") or stem
        conf = c.get("confidence") or "中"
        url = c.get("url") or ""
        reason = (c.get("reason") or "")[:80]
        link = f"[[clues/{stem}|{title}]]"
        src = f"[来源]({url})" if url else "来源：—"
        where = _region_text(c)
        where = f" — 地区：{where}" if where else ""
        lines.append(
            f"> - **线索**：{link} — 置信度：{conf}{where} — {src} — 理由：{reason}"
        )
    lines.append("")
    return "\n".join(lines)


def upsert_appendix_b(content: str, section_md: str) -> str:
    section_md = section_md.rstrip() + "\n"
    if APPENDIX_B_RE.search(content):
        return APPENDIX_B_RE.sub(section_md, content, count=1)
    # 插在「十、附录」内、免责之前
    m = re.search(r"^##\s*十、附录[\s\S]*?(?=^##\s*十一、|\Z)", content, re.M)
    if m:
        block = m.group(0)
        if "### B." in block:
            return content
        insert_at = m.end()
        return content[:insert_at].rstrip() + "\n\n" + section_md + "\n" + content[insert_at:]
    return content.rstrip() + "\n\n" + section_md


def materialize_clues(
    clues: list[dict],
    *,
    note_dir: Path,
    pub: str,
    note_rel: str = "",
    claim_summaries: dict[int, str] | None = None,
    feature_rows: list[str] | None = None,
    feature_entries: list[dict] | None = None,
    max_keep: int = DEFAULT_MAX_CLUES,
    fetch_fallback: bool = False,
    fetch: bool | None = None,
) -> tuple[list[dict], str]:
    """筛选→写入 clues/→附录 Markdown。

    摘要主路径应由 Agent 写入 public_clues.json（summary/status=agent_fetched）。
    fetch_fallback=True 时，仅对**缺少 summary** 的条目尝试脚本 HTTP 降级抓取。
    参数 fetch 为旧别名：True/False 映射到 fetch_fallback（兼容调用方）。
    """
    if fetch is not None:
        fetch_fallback = bool(fetch)
    kept, _dropped = filter_clues(clues, max_keep=max_keep)
    clues_dir = note_dir / "clues"
    clues_dir.mkdir(parents=True, exist_ok=True)
    note_link = note_rel[:-3] if note_rel.endswith(".md") else note_rel
    today = date.today().isoformat()
    entries = list(feature_entries or [])
    if not entries and feature_rows:
        entries = [{"id": "", "label": "", "text": r} for r in feature_rows]

    rich: list[dict] = []
    for i, c in enumerate(kept):
        item = normalize_clue(c, index=i)
        # 保留 Agent 已写字段
        for key in (
            "summary",
            "page_title",
            "status",
            "related_claims",
            "related_features",
            "related_feature_ids",
            "anchor_fits",
            "fits",
            "fetch_note",
            "fetched_at",
        ):
            if c.get(key) not in (None, "", []):
                item[key] = c[key]
        # 统一规范 Agent 贴合字段
        fits = normalize_anchor_fits(item)
        if fits:
            item["anchor_fits"] = fits
            item.pop("fits", None)
        fname = clue_filename(item.get("title") or "线索", i)
        item["filename"] = fname

        # 无论来源，落盘前清洗摘要（修竖排拆字 / 导航噪音 / > 引用污染）
        if item.get("summary"):
            item["summary"] = sanitize_clue_summary(
                str(item.get("summary") or ""),
                title=item.get("title") or "",
                reason=item.get("reason") or "",
            )

        has_summary = bool(str(item.get("summary") or "").strip())
        status = str(item.get("status") or "").strip()
        if has_summary and not status:
            item["status"] = "agent_fetched"
            item.setdefault("fetched_at", today)
        elif has_summary and status in ("draft", ""):
            item["status"] = "agent_fetched"
            item.setdefault("fetched_at", today)
        elif (
            fetch_fallback
            and item.get("url")
            and not has_summary
            and status
            not in ("agent_fetched", "fetched", "script_fetched", "reviewed")
        ):
            fetched = fetch_url_summary(item["url"])
            item["status"] = (
                "script_fetched" if fetched.get("ok") else "fetch_failed"
            )
            item["summary"] = fetched.get("summary") or ""
            item["page_title"] = fetched.get("page_title") or item.get("page_title") or ""
            item["fetch_error"] = fetched.get("error") or ""
            item["fetch_note"] = (item.get("fetch_note") or "") + (
                " · 脚本降级抓取" if fetched.get("ok") else " · 脚本降级失败"
            )
            if fetched.get("ok"):
                item["fetched_at"] = today
        else:
            item.setdefault("status", status or "draft")

        match = match_clue_to_note(
            item,
            claim_summaries=claim_summaries,
            feature_entries=entries,
        )
        # 权项：保留 Agent 已写；缺则启发式补
        if not item.get("related_claims"):
            item["related_claims"] = match.get("related_claims") or []
        for key, _fit in agent_fits_for(item, "claim"):
            n = _claim_key_to_num(key)
            if n and n not in (item.get("related_claims") or []):
                item.setdefault("related_claims", []).append(n)
        # 特征：优先 Agent anchor_fits / related_*，再与笔记表对齐；禁止空号
        agent_feat_keys = [k for k, _ in agent_fits_for(item, "feature")]
        if not agent_feat_keys:
            agent_feat_keys = [
                str(x)
                for x in (item.get("related_feature_ids") or item.get("related_features") or [])
                if str(x).strip()
            ]
        resolved_ids: list[str] = []
        if agent_feat_keys and entries:
            for key in agent_feat_keys:
                ent = resolve_feature_entry(str(key), entries)
                if not ent:
                    continue
                prefer = str(ent.get("id") or ent.get("label") or "")[:40]
                if prefer and prefer not in resolved_ids:
                    resolved_ids.append(prefer)
        if resolved_ids:
            item["related_feature_ids"] = resolved_ids[:6]
            item["related_features"] = resolved_ids[:4]
        else:
            # 无可用 Agent 锚定：按正文弱匹配重算
            item["related_features"] = match.get("related_features") or []
            item["related_feature_ids"] = match.get("related_feature_ids") or []

        body = render_clue_note(item, pub=pub, note_link=note_link)
        (clues_dir / fname).write_text(body, encoding="utf-8")
        rich.append(item)

    index_body = render_clues_index(rich, pub=pub, note_link=note_link)
    (clues_dir / "_线索索引.md").write_text(index_body, encoding="utf-8")

    # 旁路 JSON，供 Canvas / 再入库
    (clues_dir / "clues.json").write_text(
        json.dumps(rich, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    clues_dir_link = "clues/_线索索引"
    appendix = render_appendix_b(rich, clues_dir_link=clues_dir_link)
    return rich, appendix


def clue_cards_for_canvas(clues: list[dict], *, note_dir_rel: str = "") -> list[dict]:
    """供 build_canvas 使用的短卡数据。"""
    cards = []
    base = note_dir_rel.replace("\\", "/").rstrip("/")
    for c in clues[: DEFAULT_MAX_CLUES]:
        stem = Path(c.get("filename") or "x.md").stem
        link = f"{base}/clues/{stem}" if base else f"clues/{stem}"
        claims = c.get("related_claims") or []
        fids = c.get("related_feature_ids") or []
        cards.append(
            {
                "id": c.get("clue_id") or stem,
                "title": c.get("title") or stem,
                "confidence": c.get("confidence") or "中",
                "status": c.get("status") or "",
                "link": link,
                "related_claims": claims,
                "related_feature_ids": fids,
                "reason": _clue_highlight(c, limit=72),
            }
        )
    return cards
