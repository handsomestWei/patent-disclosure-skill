# -*- coding: utf-8 -*-
"""债修复与体验增强冒烟：IPC、术语、导航、lint、clues、stub 撞名。"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "patent_reader"))

from common import load_ipc_application_hints  # noqa: E402
from extract_patent_text import extract_glossary  # noqa: E402
from lint_patent_note import REQUIRED_HEADINGS, main as lint_main  # noqa: E402
from obsidian import (  # noqa: E402
    append_glossary_backlinks,
    bootstrap_vault,
    claim_delta_text,
    enrich_note_frontmatter,
    ensure_glossary_stub,
    evidence_scope_zh,
    is_spurious_patent_note,
    normalize_wiki_path,
    render_claim_tree_markdown,
    repair_glossary_backlinks,
    scan_glossary_index,
)
from validate_public_clues import validate_clues  # noqa: E402
from write_patent_obsidian_note import (  # noqa: E402
    _ensure_nav_section,
    harvest_glossary_from_note,
    harvest_narrative_from_note,
    merge_glossary_candidates,
)


def test_ipc_hints_count() -> None:
    hints = load_ipc_application_hints()
    assert len(hints) >= 5, f"IPC hints too few: {len(hints)}"
    industries = {h.get("industry") for h in hints}
    assert "电化学储能" in industries
    # 不应被下一条污染成「通用技术」独占
    h01 = next(h for h in hints if h.get("ipc_prefix") == "H01M")
    assert h01.get("industry") == "电化学储能"
    assert "电池" in (h01.get("keywords") or [])


def test_glossary_pair_quotes() -> None:
    text = (
        "本发明属于电化学储能领域。本文中，「耐热层」是指覆盖在基膜表面的无机涂层。"
        "基膜是指多孔聚合物膜。"
    )
    gloss = extract_glossary(text)
    terms = {g["term"] for g in gloss}
    assert "耐热层" in terms, gloss
    assert not any("本文中" in t or "发明属于" in t for t in terms)


def test_nav_merge() -> None:
    content = (
        "# 标题\n\n## Obsidian 导航\n\n"
        "- [[Research/Patents/_专利解读索引|旧索引]]\n\n"
        "## 一、一句话\n\nok\n"
    )
    out = _ensure_nav_section(
        content,
        [
            "[[Research/Patents/_专利解读索引|专利解读索引]]",
            "[[Research/术语/_术语索引|术语索引]]",
        ],
    )
    assert "术语索引" in out
    assert "专利解读索引" in out
    assert out.count("## Obsidian 导航") == 1


def test_lint_heading_not_bare_feature() -> None:
    # 「特征」仅出现在第四节表头，不应满足第六节
    labels = [lab for _, lab in REQUIRED_HEADINGS]
    assert any("特征" in lab for lab in labels)
    note = (
        "---\ncssclasses:\n  - patent-reader\nipc: H01M\ndomain: 测试\n---\n"
        "# t\n\n## Obsidian 导航\n\n## 一、一句话\n\n"
        "## 二、连贯叙事\n\n## 三、权利要求树\n\n"
        "## 四、独立权利要求精读\n\n| 特征 | 说明 |\n|---|---|\n| a | b |\n\n"
        "## 五、专利内术语表\n\n## 七、和现有技术的差别\n\n"
        "## 八、阅读建议\n\n## 九、技术应用场景\n\ndesc_001 背景\n\n"
        "## 十、附录\n\nIPC 行业坐标\n\n### B. 公开\n\n未发现可靠对应，防御性。\n\n"
        "## 十一、免责声明\n\n"
        "不构成法律意见。专利保护范围以官方法律文本为准。"
        "重大决策请咨询专利代理师。\n\n"
        "> [!patent-meta]\n> [!grounding]\n> [!warning]-\n"
    )
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        note_p = td_p / "n.md"
        note_p.write_text(note, encoding="utf-8")
        man = {"evidence_scope": "full_text", "independent_claim_count": 0}
        tree = {"nodes": [], "roots": []}
        (td_p / "m.json").write_text(json.dumps(man), encoding="utf-8")
        (td_p / "t.json").write_text(json.dumps(tree), encoding="utf-8")
        rc = lint_main(
            [
                "--note",
                str(note_p),
                "--manifest",
                str(td_p / "m.json"),
                "--claim-tree",
                str(td_p / "t.json"),
                "--output",
                str(td_p / "lint.json"),
            ]
        )
        assert rc == 1
        lint = json.loads((td_p / "lint.json").read_text(encoding="utf-8"))
        assert any("特征" in i for i in lint["issues"])


def test_glossary_index_ignores_tags() -> None:
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        gdir = "Research/术语"
        (vault / gdir).mkdir(parents=True)
        (vault / gdir / "耐热层.md").write_text(
            "---\ntags:\n  - glossary\naliases:\n  - 耐热涂层\ntitle: 耐热层\n---\n\n# 耐热层\n",
            encoding="utf-8",
        )
        idx = scan_glossary_index(vault, gdir)
        assert "耐热层" in idx
        assert "耐热涂层" in idx
        assert "glossary" not in idx


def test_stub_collision() -> None:
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        gdir = "Research/术语"
        rel1, _ = ensure_glossary_stub(
            vault, gdir, "foo bar", definition="一", source_pub="CN1"
        )
        rel2, created = ensure_glossary_stub(
            vault, gdir, "foo!!bar", definition="二", source_pub="CN2"
        )
        assert created is True
        assert rel1 != rel2
        assert (vault / f"{rel2}.md").is_file()
        text2 = (vault / f"{rel2}.md").read_text(encoding="utf-8")
        assert "foo!!bar" in text2 or "title: foo!!bar" in text2
        # 原文件未被错误覆盖
        text1 = (vault / f"{rel1}.md").read_text(encoding="utf-8")
        assert "一" in text1 or "foo bar" in text1
        assert "二" not in text1[:200] or "foo!!bar" not in text1


def test_validate_public_clues() -> None:
    ok = validate_clues(
        [
            {
                "title": "某白皮书",
                "url": "https://example.org/a",
                "confidence": "中",
                "reason": "与实施例隔膜结构对应",
            }
        ]
    )
    assert ok["passed"]
    bad = validate_clues([{"title": "x", "confidence": "高"}])
    assert not bad["passed"]


def test_filter_clues_max_three() -> None:
    from clue_vault import filter_clues

    clues = [
        {"title": "低1", "url": "https://a.example/1", "confidence": "低", "reason": "理由足够长了"},
        {"title": "高1", "url": "https://a.example/2", "confidence": "高", "reason": "理由足够长了"},
        {"title": "中1", "url": "https://a.example/3", "confidence": "中", "reason": "理由足够长了"},
        {"title": "中2", "url": "https://a.example/4", "confidence": "中", "reason": "理由足够长了"},
        {"title": "高2", "url": "https://a.example/5", "confidence": "高", "reason": "理由足够长了"},
    ]
    kept, dropped = filter_clues(clues, max_keep=3)
    assert len(kept) == 3
    assert len(dropped) == 2
    assert [c["title"] for c in kept] == ["高1", "高2", "中1"]


def test_sanitize_clue_summary_nav_and_glyphs() -> None:
    from clue_vault import format_summary_for_markdown, sanitize_clue_summary

    dirty = (
        "OA\n邮箱\n主页\n>\n产品展示\n>\n涂覆\n>>\nAl\n2\nO\n3\n/勃姆石涂覆\n"
        ">>\n单面/双面涂覆\n>>\n较基膜更高的穿刺强度，进一步降低电芯制程短路率\n"
        "联系方式\nCopyright © 2016\n"
    )
    clean = sanitize_clue_summary(dirty, title="陶瓷涂覆隔膜")
    assert "OA" not in clean
    assert "主页" not in clean
    assert "Al2O3/勃姆石涂覆" in clean or "Al2O3" in clean
    assert "穿刺强度" in clean
    assert "页面要点" in clean or clean.lstrip().startswith("-")
    assert not re.search(r"^>", clean, re.M)
    md = format_summary_for_markdown(">> 卖点甲\n正文")
    assert not md.lstrip().startswith(">")
    assert "卖点甲" in md


def test_materialize_prefers_agent_summary_no_script_by_default() -> None:
    import tempfile
    from clue_vault import materialize_clues

    clues = [
        {
            "title": "Agent已读",
            "url": "https://example.org/a",
            "confidence": "高",
            "reason": "与权1水性浆料对应充分",
            "summary": "页面写明水系PVDF涂覆产线。",
            "status": "agent_fetched",
            "related_claims": [1],
        },
        {
            "title": "仅有链接",
            "url": "https://example.org/b",
            "confidence": "中",
            "reason": "同申请人产品新闻足够长",
        },
    ]
    with tempfile.TemporaryDirectory() as td:
        rich, _ = materialize_clues(
            clues,
            note_dir=Path(td),
            pub="CN1",
            fetch_fallback=False,
        )
        by_title = {c["title"]: c for c in rich}
        assert by_title["Agent已读"]["status"] == "agent_fetched"
        assert "水系PVDF" in by_title["Agent已读"]["summary"]
        assert by_title["Agent已读"]["related_claims"] == [1]
        # 无降级时不脚本抓取，保持 draft
        assert by_title["仅有链接"]["status"] == "draft"
        assert not (by_title["仅有链接"].get("summary") or "").strip()


def test_inject_clue_annotations_l1_l4() -> None:
    from clue_vault import inject_clue_annotations

    note = """# 专利解读：测试

## Obsidian 导航

- [[x_图谱.canvas|专利族图谱]]

## 一、一句话

一句话正文。

## 二、连贯叙事

叙事。

## 三、权利要求树

表。

## 四、独立权利要求精读

> [!patent-claim] 权利要求 1

> 【CN1·权利要求1】含陶瓷涂层与基膜。

| 特征 | 大白话 | 说明书依据 |
|------|--------|------------|
| F1 双面陶瓷涂层结构 | 上下陶瓷 | 发明 |
| F6 拉伸后陶瓷涂覆 | 仍要涂层 | 权1 |

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| [[Research/术语/陶瓷涂层|陶瓷涂层]] | 涂层 | — |

## 六、特征—说明书—附图对照

| 特征 | 说明书位置 | 附图 |
|------|------------|------|
| 陶瓷 | 背景 | — |

## 七、和现有技术的差别

差别。

## 八、阅读建议

1. 建议。

## 九、技术应用场景

> [!grounding] 应用场景
> 场景。

## 十、附录：行业坐标与公开线索

### A. IPC

x

### B. 公开检索线索

old

## 十一、免责声明

免责。
"""
    clues = [
        {
            "title": "陶瓷产品页",
            "filename": "01-陶瓷产品页.md",
            "summary": "页面要点：\n- Al2O3/勃姆石涂覆\n- 单面/双面涂覆",
            "reason": "同申请人陶瓷涂覆隔膜产品线",
            "related_claims": [1],
            "related_feature_ids": ["F1", "F6"],
            "confidence": "中",
            "status": "agent_fetched",
        }
    ]
    out = inject_clue_annotations(note, clues)
    assert "公开线索（1 条）" in out
    assert "公开线索入口" in out
    assert "公开案例（推测）" in out
    assert "差别对照·公开线索" in out
    assert "阅读建议·公开线索" in out
    assert "场景·公开线索" in out
    assert "权项—公开语境（推测）" in out
    assert "特征—公开语境（推测）" in out
    assert "F1 双面陶瓷涂层结构" in out or "**F1" in out
    assert "术语·公开语境" in out
    # 术语旁注在第五节后、第六节前；特征旁注紧挨第六节对照表后、附图/第七节前
    i5, i_term = out.find("## 五、"), out.find("术语·公开语境")
    i6, i_feat = out.find("## 六、"), out.find("特征—公开语境（推测）")
    i7 = out.find("## 七、")
    assert 0 <= i5 < i_term < i6 < i_feat < i7
    # 对照表在旁注之前
    assert out.find("| 特征 | 说明书位置 | 附图 |") < i_feat
    # 幂等
    out2 = inject_clue_annotations(out, clues)
    assert out2.count("公开线索入口") == 1
    assert out2.count("特征—公开语境（推测）") == 1


def test_agent_anchor_fits_preferred() -> None:
    """有 anchor_fits 时，旁注必须用 Agent 贴合句，而非启发式首句。"""
    from clue_vault import inject_clue_annotations

    note = """# t

## Obsidian 导航

- [[x|图谱]]

## 一、一句话

a

## 二、连贯叙事

b

## 三、权利要求树

c

## 四、独立权利要求精读

> [!patent-claim] 权利要求 1

> 含陶瓷与纤维素涂覆层。

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| 纤维素 | 涂层 | — |

## 六、特征—说明书—附图对照

| 特征 | 说明书位置 | 附图 |
|------|------------|------|
| 涂覆层含陶瓷和纤维素 | 权1 | 图1 |
| 纤维素分子量 5万-250万 | 权2 | — |

## 七、和现有技术的差别

d

## 八、阅读建议

1. x

## 九、技术应用场景

y

## 十、附录

### A. IPC

x

## 十一、免责声明

z
"""
    clues = [
        {
            "title": "公开页A",
            "filename": "01-公开页A.md",
            "summary": "页面要点：\n- 无关的第一句卖点会被启发式误用\n- 纸基涂布纤维素溶液",
            "reason": "同主题",
            "related_claims": [1],
            "related_feature_ids": ["涂覆层含陶瓷和纤维素", "纤维素分子量 5万-250万"],
            "anchor_fits": [
                {
                    "kind": "feature",
                    "key": "涂覆层含陶瓷和纤维素",
                    "fit": "AGENT贴合：纸基涂布纤维素溶液",
                },
                {
                    "kind": "claim",
                    "key": "1",
                    "fit": "AGENT权贴合：同主题涂覆隔膜制备",
                },
                {
                    "kind": "term",
                    "key": "纤维素",
                    "fit": "AGENT术语：文中举例棉浆溶解",
                },
            ],
            "confidence": "中",
            "status": "agent_fetched",
        }
    ]
    out = inject_clue_annotations(note, clues)
    feat = out.split("特征—公开语境（推测）")[1].split("## 七、")[0]
    assert "AGENT贴合：纸基涂布纤维素溶液" in feat
    assert "无关的第一句卖点" not in feat
    claim = out.split("权项—公开语境（推测）")[1].split("## 五、")[0]
    assert "AGENT权贴合：同主题涂覆隔膜制备" in claim
    term = out.split("术语·公开语境")[1].split("## 六、")[0]
    assert "AGENT术语：文中举例棉浆溶解" in term


def test_claim_and_term_callouts_distill() -> None:
    """权项/术语 warning：按锚点抽贴合句，且 L2 不再硬编码「湿法」话术。"""
    from clue_vault import inject_clue_annotations

    note = """# t

## Obsidian 导航

- [[x|图谱]]

## 一、一句话

a

## 二、连贯叙事

b

## 三、权利要求树

c

## 四、独立权利要求精读

> [!patent-claim] 权利要求 1

> 【CN·权利要求1】含陶瓷涂层与基膜，采用碱尿素溶解纤维素后涂布。

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| [[Research/术语/陶瓷涂层|陶瓷涂层]] | 涂层 | — |
| 纤维素 | 涂层组分 | — |

## 六、特征—说明书—附图对照

| 特征 | 说明书位置 | 附图 |
|------|------------|------|
| 陶瓷涂层 | 权1 | 图1 |

## 七、和现有技术的差别

d

## 八、阅读建议

1. x

## 九、技术应用场景

y

## 十、附录

### A. IPC

x

## 十一、免责声明

z
"""
    clues = [
        {
            "title": "纤维素涂布与陶瓷隔膜公开页",
            "filename": "01-纤维素陶瓷.md",
            "summary": (
                "页面要点：\n"
                "- 提出在纸基上涂布纤维素溶液\n"
                "- 采用碱尿素体系溶解非衍生化纤维素后涂布\n"
                "- 陶瓷涂层用于提升热稳定性"
            ),
            "reason": "同主题公开",
            "related_claims": [1],
            "related_feature_ids": ["陶瓷涂层"],
            "confidence": "中",
            "status": "agent_fetched",
        }
    ]
    out = inject_clue_annotations(note, clues)
    assert "湿法工艺" not in out
    claim_zone = out.split("权项—公开语境（推测）")[1].split("## 五、")[0]
    assert "碱尿素" in claim_zone or "纤维素" in claim_zone or "陶瓷" in claim_zone
    assert "同主题语境（摘要未点名该权项）" not in claim_zone or "—" in claim_zone
    term_zone = out.split("术语·公开语境")[1].split("## 六、")[0]
    assert "陶瓷涂层" in term_zone or "纤维素" in term_zone


def test_feature_callout_dedupes_clue_and_distills() -> None:
    """多特征命中同一线索时：线索只出现一次，并为特征抽不同贴合句。"""
    from clue_vault import inject_clue_annotations

    note = """# t

## Obsidian 导航

- [[x|图谱]]

## 一、一句话

a

## 二、连贯叙事

b

## 三、权利要求树

c

## 四、独立权利要求精读

> [!patent-claim] 权利要求 1

> 隔膜。

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| 纤维素 | 涂层 | — |

## 六、特征—说明书—附图对照

| 特征 | 说明书位置 | 附图 |
|------|------------|------|
| 基膜+至少一面涂覆层 | 权1 | 图1 |
| 涂覆层含陶瓷和纤维素 | 权1 | 图1 |
| 纤维素分子量 5万-250万 | 权2 | — |
| 非衍生化碱尿素溶解 | 权3 | 图2 |

## 七、和现有技术的差别

d

## 八、阅读建议

1. x

## 九、技术应用场景

y

## 十、附录

### A. IPC

x

## 十一、免责声明

z
"""
    clues = [
        {
            "title": "一种纤维素涂布锂离子电池隔膜的制备方法（碱尿素溶）",
            "filename": "01-纤维素涂布.md",
            "summary": (
                "页面要点：\n"
                "- 该公开文本针对聚烯烃隔膜热稳定性差，提出在纸基上涂布纤维素溶液\n"
                "- 采用碱尿素体系溶解非衍生化纤维素后涂布"
            ),
            "reason": "同主题纤维素涂布隔膜公开文本",
            "related_feature_ids": [
                "基膜+至少一面涂覆层",
                "涂覆层含陶瓷和纤维素",
                "纤维素分子量 5万-250万",
                "非衍生化碱尿素溶解",
            ],
            "confidence": "中",
            "status": "agent_fetched",
        }
    ]
    out = inject_clue_annotations(note, clues)
    zone = out.split("特征—公开语境（推测）")[1].split("## 七、")[0]
    # 线索标题在特征块内只出现一次（按线索归纳）
    assert zone.count("纤维素涂布锂离子电池隔膜") == 1
    assert "涂覆层含陶瓷和纤维素" in zone
    assert "非衍生化碱尿素溶解" in zone
    # 应有针对特征的贴合句，而非每行重复整段同一摘要
    assert "碱尿素" in zone
    assert "涂布纤维素" in zone or "纸基" in zone
    # 数值特征无摘要锚点时收进另涉，避免刷屏
    assert "另涉" in zone or "分子量" in zone


def test_feature_callout_drops_orphan_fids() -> None:
    """第六节只有特征名、无 F 编号时：丢弃 sidecar 空号 F1–F6，改挂表内名称。"""
    from clue_vault import inject_clue_annotations, match_clue_to_note

    note = """# t

## Obsidian 导航

- [[x|图谱]]

## 一、一句话

a

## 二、连贯叙事

b

## 三、权利要求树

c

## 四、独立权利要求精读

> [!patent-claim] 权利要求 1

> 【CN·权利要求1】水性PVDF浆料涂覆隔膜。

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| PVDF | 涂层聚合物 | — |

## 六、特征—说明书—附图对照

| 特征 | 说明书位置 | 附图 |
|------|------------|------|
| 循环性能对比 | 表2 | 图1 |
| 水性球状形貌 | 成孔机理 | 图2 |
| 油性海绵状对比 | 溶剂对比 | 图3 |

## 七、和现有技术的差别

d

## 八、阅读建议

1. x

## 九、技术应用场景

y

## 十、附录

### A. IPC

x

## 十一、免责声明

z
"""
    clues = [
        {
            "title": "水系PVDF产品页",
            "filename": "01-水系PVDF产品页.md",
            "summary": "掌握水系 PVDF、油系 PVDF 涂覆技术",
            "reason": "公开水系/油系 PVDF 涂覆能力",
            # 旧 sidecar 空号，笔记里并不存在
            "related_feature_ids": ["F1", "F2", "F4", "F6", "F5"],
            "related_claims": [1],
            "confidence": "中",
            "status": "agent_fetched",
        }
    ]
    out = inject_clue_annotations(note, clues)
    feat_zone = out.split("特征—公开语境（推测）")[1].split("## 七、")[0]
    assert "水性球状形貌" in feat_zone
    assert "油性海绵状对比" in feat_zone
    assert re.search(r"\bF[1-6]\b", feat_zone) is None
    m = match_clue_to_note(
        clues[0],
        feature_entries=[
            {"id": "", "label": "水性球状形貌", "text": "水性球状形貌 成孔"},
            {"id": "", "label": "油性海绵状对比", "text": "油性海绵状对比 溶剂"},
            {"id": "", "label": "循环性能对比", "text": "循环性能对比 表2"},
        ],
    )
    assert "水性球状形貌" in m["related_feature_ids"]
    assert "油性海绵状对比" in m["related_feature_ids"]
    assert "F1" not in m["related_feature_ids"]


def test_clue_appendix_and_annotate() -> None:
    from clue_vault import (
        inject_clue_annotations,
        match_clue_to_note,
        render_appendix_b,
        upsert_appendix_b,
    )

    clue = {
        "title": "水性PVDF产品报道",
        "url": "https://news.example/x",
        "confidence": "中",
        "reason": "公开水系PVDF涂覆能力",
        "filename": "01-水性PVDF产品报道.md",
        "summary": "公司掌握水性PVDF浆料涂覆隔膜技术",
    }
    m = match_clue_to_note(
        clue,
        claim_summaries={1: "水性PVDF浆料涂覆隔膜"},
        feature_rows=["F1 水性PVDF 浆料"],
    )
    assert 1 in m["related_claims"]
    clue.update(m)
    app = render_appendix_b([clue], clues_dir_link="clues/_线索索引")
    assert "[[clues/01-水性PVDF产品报道|" in app
    note = "## 四、独立权利要求精读\n\nbody\n\n## 五、专利内术语表\n\nx\n"
    note2 = inject_clue_annotations(note, [clue])
    assert "外部线索（推测）" in note2
    full = "## 十、附录\n\n### A. IPC\n\nx\n\n### B. 公开检索线索\n\nold\n\n## 十一、免责声明\n"
    full2 = upsert_appendix_b(full, app)
    assert "线索文件夹" in full2
    assert "old" not in full2.split("### B.")[1]


def test_optional_path_not_cwd() -> None:
    from common import optional_path
    import argparse

    assert optional_path("") is None
    assert optional_path(None) is None
    assert optional_path("tmp/x") == Path("tmp/x")

    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=None, type=optional_path)
    ap.add_argument("--output", default=None, type=optional_path)
    ns = ap.parse_args([])
    assert ns.workdir is None
    assert ns.output is None


def test_obsidian_detect_and_env_disable() -> None:
    import os
    from common import (
        candidate_default_vault_paths,
        detect_obsidian_installed,
        probe_obsidian_environment,
        resolve_obsidian_vault,
    )

    install = detect_obsidian_installed()
    assert "installed" in install
    assert any("Obsidian Vault" in str(p) for p in candidate_default_vault_paths())

    # 显式清空环境变量 = 本会话禁用 Obsidian，不得回退探测
    old = {
        k: os.environ.get(k)
        for k in (
            "PATENT_READER_OBSIDIAN_VAULT",
            "PATENT_DISCLOSURE_OBSIDIAN_VAULT",
        )
    }
    try:
        os.environ["PATENT_READER_OBSIDIAN_VAULT"] = ""
        os.environ.pop("PATENT_DISCLOSURE_OBSIDIAN_VAULT", None)
        r = resolve_obsidian_vault()
        assert r.get("source") == "env_disabled"
        assert r.get("vault") == ""
        assert r.get("needs_user_input") is False
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    report = probe_obsidian_environment()
    assert report.get("obsidian_required") is False
    assert "status" in report


def test_bootstrap_creates_appearance() -> None:
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        actions = bootstrap_vault(vault, "Research/MyPatents")
        assert (vault / ".obsidian" / "appearance.json").is_file()
        data = json.loads(
            (vault / ".obsidian" / "appearance.json").read_text(encoding="utf-8")
        )
        assert "patent-reader" in data.get("enabledCssSnippets", [])
        base = (vault / "Research" / "MyPatents" / "patents.base").read_text(
            encoding="utf-8"
        )
        assert "MyPatents" in base
        assert "{{PAPERS_DIR}}" not in base
        assert any("enabled_snippet" in a or "appearance" in a for a in actions)
        core = json.loads(
            (vault / ".obsidian" / "core-plugins.json").read_text(encoding="utf-8")
        )
        assert core.get("bases") is True
        assert any("enabled_core:bases" in a for a in actions)
        graph = json.loads(
            (vault / ".obsidian" / "graph.json").read_text(encoding="utf-8")
        )
        assert graph.get("colorGroups")
        assert any("file:_解读_" in (g.get("query") or "") for g in graph["colorGroups"])
        search = graph.get("search") or ""
        assert "-file:.json" in search
        assert "-file:_权项锚点" in search
        assert "-file:_说明书段落" in search
        assert any("graph_colors:" in a for a in actions)


def test_harvest_narrative_from_note() -> None:
    note = """# t

## 一、一句话

用一句话说清专利。

## 二、连贯叙事

**问题**：旧工艺不安全。

**思路**：改用水性浆料。

**怎么做**：分散、研磨、涂布。

**效果**：更薄更透气。

## 七、和现有技术的差别

- **相对丙酮**：更安全。
"""
    n = harvest_narrative_from_note(note)
    assert n.get("problem") and "不安全" in n["problem"]
    assert n.get("effect") and "薄" in n["effect"]
    assert n.get("diff")


def test_glossary_backlink_backslash_dedupe() -> None:
    assert normalize_wiki_path(r"Research\Patents\a\b.md") == "Research/Patents/a/b"
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        gdir = "Research/术语"
        (vault / gdir).mkdir(parents=True)
        path = vault / gdir / "耐热层.md"
        path.write_text(
            "---\ntags:\n  - glossary\ntitle: 耐热层\n---\n\n# 耐热层\n\n定义\n\n"
            "## 反链\n"
            "- 解读：[[Research/Patents/化工/CN1/CN1_解读_20260101|CN1]]\n"
            "- 解读：[[Research\\Patents\\化工\\CN1\\CN1_解读_20260101|CN1]]\n",
            encoding="utf-8",
        )
        n = repair_glossary_backlinks(vault, gdir)
        assert n == 1
        text = path.read_text(encoding="utf-8")
        assert text.count("CN1_解读_20260101") == 1
        assert "\\" not in text.split("## 反链", 1)[1]
        # 再追加反斜杠路径不应重复
        append_glossary_backlinks(
            path,
            source_pub="CN1",
            note_rel=r"Research\Patents\化工\CN1\CN1_解读_20260101.md",
        )
        text2 = path.read_text(encoding="utf-8")
        assert text2.count("|CN1]]") == 1


def test_render_claim_tree_markdown() -> None:
    tree = {
        "roots": [1],
        "nodes": [
            {
                "number": 1,
                "is_independent": True,
                "parent": None,
                "text_preview": "一种方法，其特征在于：先分散再拉伸成膜。",
            },
            {
                "number": 2,
                "is_independent": False,
                "parent": 1,
                "text_preview": "如权利要求1所述的方法，其特征在于：拉伸比为3～12。",
            },
        ],
    }
    md = render_claim_tree_markdown(tree, pub="CN1", summaries={1: "分散+拉伸成膜"})
    assert "| 结构 | 权 | 本项新增 |" in md
    assert "◆" in md and "└─" in md or "├─" in md
    assert "分散+拉伸成膜" in md
    assert "拉伸比" in md or "3～12" in claim_delta_text(tree["nodes"][1]["text_preview"])
    # 默认不嵌入 mermaid，避免与表重复
    assert "```mermaid" not in md
    md2 = render_claim_tree_markdown(tree, pub="CN1", include_mermaid=True)
    assert "```mermaid" in md2


def test_claim_tree_multi_parent_and_validate() -> None:
    """多引用父号解析 + Agent 校对校验。"""
    from common import (
        normalize_claim_tree,
        parent_claim_numbers,
        validate_claim_tree,
    )

    assert parent_claim_numbers("如权利要求1或2所述的隔膜，其特征在于：…") == [1, 2]
    assert parent_claim_numbers("according to claims 3 or 4, wherein")[:2] == [3, 4]

    tree = {
        "roots": [1],
        "nodes": [
            {
                "number": 1,
                "is_independent": True,
                "parent": None,
                "text_preview": "一种隔膜",
            },
            {
                "number": 2,
                "is_independent": False,
                "parent": 1,
                "text_preview": "如权利要求1",
            },
            {
                "number": 5,
                "is_independent": False,
                "parent": 2,
                "parent_candidates": [1, 2],
                "text_preview": "如权利要求1或2所述",
            },
        ],
        "review": {
            "by": "agent",
            "status": "reviewed",
            "notes": "权5挂独立权1",
            "corrections": [{"claim": 5, "to_parent": 1}],
        },
    }
    # Agent 纠正父号
    tree["nodes"][2]["parent"] = 1
    result = validate_claim_tree(tree)
    assert result["passed"]
    assert result["tree"]["nodes"][2]["parent"] == 1
    assert any("multi_parent_candidates" in w for w in result["warnings"])

    bad = normalize_claim_tree(
        {
            "nodes": [
                {"number": 1, "is_independent": True, "parent": 9},
                {"number": 2, "is_independent": False, "parent": 99},
            ]
        }
    )
    assert bad["nodes"][0]["parent"] is None
    assert bad["nodes"][1]["parent"] == 1  # 悬空父号回退到独立权1
    unchecked = validate_claim_tree({"nodes": bad["nodes"]})
    assert "not_agent_reviewed" in unchecked["warnings"]


def test_claim_deltas_agent_preferred() -> None:
    """Agent claim_deltas 覆盖启发式截句。"""
    from obsidian import (
        load_claim_deltas,
        merge_claim_summaries,
        render_claim_tree_markdown,
    )

    tree = {
        "roots": [1],
        "nodes": [
            {
                "number": 1,
                "is_independent": True,
                "parent": None,
                "text_preview": "一种隔膜，其特征在于：包括基膜和涂覆层。",
            },
            {
                "number": 2,
                "is_independent": False,
                "parent": 1,
                "text_preview": "如权利要求1所述的隔膜，其特征在于：涂覆层含陶瓷和纤维素。",
            },
        ],
    }
    agent = load_claim_deltas(
        {
            "source": "agent",
            "deltas": [
                {"claim": 1, "delta": "基膜+涂覆层骨架"},
                {"claim": 2, "delta": "涂层同时含陶瓷与纤维素"},
            ],
        }
    )
    assert agent[2] == "涂层同时含陶瓷与纤维素"
    # 笔记旧句不应压过 Agent
    summaries = merge_claim_summaries({2: "旧启发式句子"}, agent)
    assert summaries[2] == "涂层同时含陶瓷与纤维素"
    md = render_claim_tree_markdown(tree, pub="CN1", summaries=summaries)
    assert "涂层同时含陶瓷与纤维素" in md
    assert "基膜+涂覆层骨架" in md
    # 缺 Agent 的权号仍可启发式
    md_fb = render_claim_tree_markdown(tree, pub="CN1", summaries={1: "骨架"})
    assert "骨架" in md_fb
    assert "陶瓷" in md_fb or "纤维素" in md_fb


def test_spurious_patent_note_detect() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "CN1_解读_20260721 1.md"
        p.write_text("", encoding="utf-8")
        assert is_spurious_patent_note(p)
        p2 = Path(td) / "CN1_解读_20260721.md"
        p2.write_text("# ok\n", encoding="utf-8")
        assert not is_spurious_patent_note(p2)


def test_sanitize_user_facing_titles() -> None:
    from write_patent_obsidian_note import sanitize_user_facing_titles

    dirty = (
        "## 二、连贯叙事（故事线）\n"
        "### 结构图（可选 mermaid）\n"
        "## 七、和现有技术的差别（若能从原文读出）\n"
        "## 九、技术应用场景（专利内依据）\n"
        "### A. IPC 行业坐标（离线词表）\n"
        "### B. 公开检索线索（推测）\n"
        "## 相关专利（自动关联）\n"
        "### 附图（扫描件整页预览）\n"
        "> [!grounding] 应用场景（专利内依据 · 高置信）\n"
        "> [!warning]- 公开检索线索（推测 · 默认折叠）\n"
        "- [[Research/Patents/x/y_图谱.canvas|专利族图谱]]（入库后生成）\n"
        "**效果（专利自述）**：ok\n"
        "- **来源**：`context_anchor.ipc_application`（离线词表）+ Google Patents 分类信息\n"
        "*第 1 页 · `page_001_xref_01.png`*\n"
        "> 由 `write_patent_obsidian_note.py` / `setup_obsidian_vault.py` 维护。\n"
        "- 关联（交付后运行 `link_patent_notes.py` 生成）\n"
    )
    clean = sanitize_user_facing_titles(dirty)
    assert "（故事线）" not in clean
    assert "（若能从原文读出）" not in clean
    assert "（专利内依据）" not in clean
    assert "## 二、连贯叙事\n" in clean
    assert "## 七、和现有技术的差别\n" in clean
    assert "## 相关专利\n" in clean
    assert "### 附图\n" in clean
    assert "> [!grounding] 应用场景\n" in clean
    assert "（入库后生成）" not in clean
    assert "**效果**：" in clean
    assert "context_anchor" not in clean
    assert "page_001_xref" not in clean
    assert ".py" not in clean
    assert "离线 IPC 行业词表；Google Patents 分类信息" in clean
    assert "*第 1 页*" in clean
    assert "入库后自动维护" in clean


def test_evidence_label_zh_in_frontmatter() -> None:
    assert evidence_scope_zh("full_text") == "全文"
    note = (
        "---\npub_number: CN1\ndomain: 测试\nevidence_scope: full_text\n"
        "confidence_speculative: true\n---\n\n# t\n\n"
        "> [!speculative]\n> 低置信度线索\n"
    )
    out = enrich_note_frontmatter(
        note,
        pub="CN1",
        domain="测试",
        manifest={"evidence_scope": "full_text"},
        anchor={},
    )
    assert "evidence_label: 全文" in out
    assert "speculative_label: 是" in out


def test_glossary_stub_fills_section5_definition() -> None:
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        gdir = "Research/术语"
        rel, _ = ensure_glossary_stub(
            vault, gdir, "陶瓷涂层", definition="", source_pub="CN1"
        )
        path = vault / f"{rel}.md"
        assert "待补充" in path.read_text(encoding="utf-8")
        ensure_glossary_stub(
            vault,
            gdir,
            "陶瓷涂层",
            definition="复合在基础层表面的无机涂层",
            source_pub="CN1",
        )
        text = path.read_text(encoding="utf-8")
        assert "复合在基础层表面的无机涂层" in text
        assert "待补充" not in text.split("# 陶瓷涂层", 1)[1].split("来源专利", 1)[0]


def test_harvest_glossary_from_note_section5() -> None:
    note = """# t

## 五、专利内术语表

| 术语 | 本文含义/位置 | 备注 |
|------|---------------|------|
| [[Research/术语/耐热层|耐热层]] | 涂层 | 定义句 |
| 基膜 | 多孔膜 | |

## 六、特征—说明书—附图对照
"""
    harvested = harvest_glossary_from_note(note)
    terms = {g["term"] for g in harvested}
    assert "耐热层" in terms and "基膜" in terms, harvested
    merged = merge_glossary_candidates([{"term": "耐热层", "definition": ""}], harvested)
    by = {g["term"]: g for g in merged}
    assert by["耐热层"]["definition"] == "涂层"
    assert "基膜" in by


def main() -> int:
    test_ipc_hints_count()
    test_glossary_pair_quotes()
    test_nav_merge()
    test_lint_heading_not_bare_feature()
    test_glossary_index_ignores_tags()
    test_stub_collision()
    test_validate_public_clues()
    test_filter_clues_max_three()
    test_sanitize_clue_summary_nav_and_glyphs()
    test_materialize_prefers_agent_summary_no_script_by_default()
    test_inject_clue_annotations_l1_l4()
    test_feature_callout_drops_orphan_fids()
    test_clue_appendix_and_annotate()
    test_optional_path_not_cwd()
    test_obsidian_detect_and_env_disable()
    test_bootstrap_creates_appearance()
    test_evidence_label_zh_in_frontmatter()
    test_glossary_stub_fills_section5_definition()
    test_harvest_glossary_from_note_section5()
    test_harvest_narrative_from_note()
    test_sanitize_user_facing_titles()
    test_glossary_backlink_backslash_dedupe()
    test_spurious_patent_note_detect()
    test_render_claim_tree_markdown()
    test_claim_tree_multi_parent_and_validate()
    test_claim_deltas_agent_preferred()
    print("OK debt_and_enhancement smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
