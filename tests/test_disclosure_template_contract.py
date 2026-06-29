# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_yh_template_reference_covers_default_15_section_contract() -> None:
    template = read_text("prompts/template_reference_yh.md")
    original_template = read_text("prompts/template_reference.md")

    required_sections = [
        "发明名称",
        "关键词",
        "相关提案",
        "摘要",
        "代表性附图",
        "技术领域",
        "英文缩略语/非通用术语解释",
        "背景技术",
        "要解决的技术问题",
        "有益的技术效果",
        "所有的实施方式",
        "可替代的技术方案",
        "附图",
        "实物照片",
        "着重保护的技术创新点",
    ]
    for section in required_sections:
        assert section in template

    assert "中文关键词：" in template
    assert "英文关键词：" in template
    assert "不得交叉" in template
    assert "没有实物照片时，填写“无”" in template
    assert "保留本章" in template
    assert "删除第 14 章" not in template
    assert "Images 2.0" in template
    assert "images/" in template
    assert "图示01_" in template
    assert "附图说明" in template
    assert "附图标记表" in template
    assert "专利交底书模版参考（脱敏版）" in original_template


def test_step7_default_uses_yh_template_and_keeps_legacy_as_reference() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    skill = read_text("SKILL.md")

    assert "template_reference_yh.md" in builder
    assert "默认" in builder
    assert "15 项" in builder or "15项" in builder
    assert "图示规划表" in builder
    assert "不写入正文" in builder
    assert "不得伪造图片" in builder

    assert "disclosure_builder.md + template_reference_yh.md" in skill
    assert "历史参考" in skill
    assert "images/" in skill
    assert "仅在用户明确要求 YH" not in skill

    yh_builder = read_text("prompts/disclosure_builder_yh.md")
    assert "第 14 章“实物照片”必须保留" in yh_builder
    assert "不得删除第 14 章" in yh_builder
    assert "删除第 14 章，不写“无”" not in yh_builder


def test_skill_identity_uses_yh_name_and_alias() -> None:
    skill = read_text("SKILL.md")
    readme = read_text("README.md")
    install = read_text("INSTALL.md")

    assert "name: yh-patent-disclosure-skill" in skill
    assert "/yh-patent-disclosure-skill" in skill
    assert "YH-patent-disclosure-skill/" in readme
    assert "yh-patent-disclosure-skill" in install
    assert "name: yh-patent-disclosure-skill" in install


def test_self_check_and_docs_cover_image_consistency_contract() -> None:
    self_check = read_text("prompts/disclosure_self_check.md")
    readme = read_text("README.md")
    skill_structure = read_text("docs/skill-structure.md")

    for text in (self_check, readme, skill_structure):
        assert "YH" in text
        assert "Images 2.0" in text
        assert "images/" in text

    required_self_check_items = [
        "关键词中英分行",
        "摘要必填",
        "相关提案",
        "可替代的技术方案",
        "实物照片保留",
        "图号连续",
        "图片路径存在",
        "图注完整",
        "同一对象标记一致",
        "附图说明",
        "附图标记表",
        "错误文字",
        "装饰风格",
    ]
    for item in required_self_check_items:
        assert item in self_check


def test_yh_template_uses_practical_disclosure_writing_principles() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")
    yh_builder = read_text("prompts/disclosure_builder_yh.md")
    skill = read_text("SKILL.md")
    readme = read_text("README.md")
    skill_structure = read_text("docs/skill-structure.md")

    for text in (builder, template):
        assert "技术底稿" in text
        assert "专业专利团队" in text
        assert "不要写成平台宣传语" in text
        assert "只写必要对比" in text
        assert "编号列清楚" in text
        assert "实施方式用纯文字描述" in text
        assert "附图统一放在第 13 章" in text
        assert "第 5 章不重复插入图片" in text
        assert "默认白底黑蓝线条" in text
        assert "少量绿色/红色" in text
        assert "附图标记仍必须严格一致" in text
        assert "保护点不宜过多" in text

    assert "正文中使用普通 Markdown 图片引用" not in template

    for text in (yh_builder, skill, readme, skill_structure):
        assert "附图统一放在第 13 章" in text
        assert "白底黑蓝线条" in text
        assert "少量绿色/红色" in text
        assert "插入正文" not in text

    for item in [
        "技术底稿定位",
        "发明名称非宣传语",
        "背景技术必要对比",
        "技术问题编号",
        "实施方式纯文字",
        "附图集中第 13 章",
        "白底黑蓝线条",
        "必要时少量绿色/红色",
        "保护点数量克制",
    ]:
        assert item in self_check

    assert "第五章「技术关键点」" not in self_check


def test_skill_emphasizes_prior_art_avoidance_and_new_patent_ideas() -> None:
    skill = read_text("SKILL.md")
    analyzer = read_text("prompts/patent_points_analyzer.md")
    prior_art = read_text("prompts/prior_art_search.md")
    builder = read_text("prompts/disclosure_builder.md")
    preview = read_text("prompts/disclosure_preview.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    for text in (skill, analyzer, prior_art, builder, preview, self_check):
        assert "检索查重" in text
        assert "避开已有专利点" in text
        assert "反问" in text
        assert "其他行业类似专利" in text
        assert "新的金点子" in text
        assert "严格遵守 YH 15 项" in text


def test_disclosure_flow_invokes_humanizer_without_changing_patent_boundaries() -> None:
    skill = read_text("SKILL.md")
    builder = read_text("prompts/disclosure_builder.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    for text in (skill, builder, self_check):
        assert "humanizer-zh" in text
        assert "去 AI 痕迹" in text

    for text in (skill, builder):
        assert "技术事实" in text
        assert "查新结论" in text
        assert "公式参数" in text
        assert "附图标记" in text
        assert "保护边界" in text


def test_figure_check_tool_is_documented_in_skill_contract() -> None:
    skill = read_text("SKILL.md")
    tools_readme = read_text("tools/README.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    for text in (skill, tools_readme, self_check):
        assert "figure_check.py" in text
        assert "第 13 章附图" in text
        assert "图号完全对应" in text
        assert "图片文件是否存在" in text
