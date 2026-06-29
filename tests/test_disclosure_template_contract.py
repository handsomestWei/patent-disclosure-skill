# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_yh_template_reference_covers_default_15_section_contract() -> None:
    template = read_text("prompts/template_reference_yh.md")

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


def test_step7_default_uses_yh_template_without_legacy_template_reference() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    skill = read_text("SKILL.md")

    assert "template_reference_yh.md" in builder
    assert "默认" in builder
    assert "15 项" in builder or "15项" in builder
    assert "图示规划表" in builder
    assert "不写入正文" in builder
    assert "不得伪造图片" in builder

    assert "disclosure_builder.md + template_reference_yh.md" in skill
    assert "images/" in skill
    assert "仅在用户明确要求 YH" not in skill

    yh_builder = read_text("prompts/disclosure_builder_yh.md")
    assert "兼容入口" in yh_builder
    assert "不要在本文件维护另一套章节或图示规则" in yh_builder
    assert "第 14 章“实物照片”必须保留" not in yh_builder
    assert "删除第 14 章，不写“无”" not in yh_builder


def test_legacy_template_file_and_references_are_removed() -> None:
    assert not (ROOT / "prompts/template_reference.md").exists()

    checked_paths = [
        "SKILL.md",
        "README.md",
        "INSTALL.md",
        "docs/PRD.md",
        "docs/skill-structure.md",
        "examples/README.md",
        "tools/README.md",
        "tools/mermaid_render.py",
        "tools/md_to_docx.py",
        "prompts/disclosure_builder.md",
        "prompts/disclosure_builder_yh.md",
        "prompts/template_reference_yh.md",
        "prompts/disclosure_self_check.md",
        "prompts/disclosure_preview.md",
        "prompts/iteration_context.md",
        "prompts/merger.md",
        "prompts/correction_handler.md",
    ]

    forbidden_phrases = [
        "template_reference.md",
        "历史参考模板",
        "历史交底书模版参考",
        "旧模板参考",
        "原模板保留",
        "原模板文件",
        "旧模板章节结构",
        "专利交底书模版参考（脱敏版）",
        "合并进第三章",
        "扩写 3.4",
        "修正 3.5",
    ]

    for path in checked_paths:
        text = read_text(path)
        for phrase in forbidden_phrases:
            assert phrase not in text, f"{path} still contains legacy template phrase: {phrase}"


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

    for text in (skill, readme, skill_structure):
        assert "附图统一放在第 13 章" in text
        assert "白底黑蓝线条" in text
        assert "少量绿色/红色" in text
        assert "插入正文" not in text

    assert "附图统一放在第 13 章" not in yh_builder
    assert "白底黑蓝线条" not in yh_builder

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


def test_yh_template_matches_latest_section_wording_preferences() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    assert "提案编号用顿号隔开汇总为一行" in template
    assert "代表性附图为图1“[图名]”。该图是该专利最佳代表性图示，完整图示说明及附图标记见第 13 章。" in template
    assert "不要使用表格" in template
    assert "数字序号分行描述" in template
    assert "字数不宜过多" in template
    assert "| 术语/缩略语 | 中文名称 | 含义解释 |" not in template

    for text in (builder, template, self_check):
        assert "1.1 文献" in text
        assert "公开数据库名称与检索词" in text
        assert "请勿写" in text
        assert "技术方向分类引用" in text
        assert "局限性" in text
        assert "公开源 URL" in text
        assert "充分理解摘要后再概括" in text
        assert "本发明与现有技术的本质区别" in text
        assert "分点索引" in text
        assert "核心缺陷" in text
        assert "逐条说明本发明的解决思路" in text


def test_yh_template_keeps_useful_technical_detail_without_architecture_change() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    for text in (builder, template, self_check):
        assert "应用场景的通用描述" in text
        assert "模块间关联关系" in text
        assert "数据流或控制流" in text
        assert "流程步骤与附图节点" in text
        assert "符号与变量定义" in text
        assert "关键技术参数" in text
        assert "实施例" in text
        assert "不作为权利要求限制" in text
        assert "先概括性观点，再分点详述" in text
        assert "与第 9 章技术问题和第 15 章保护点呼应" in text

    assert "## 三、技术方案详细阐述" not in template
    assert "## 四、与现有技术相比的优点" not in template
    assert "## 五、技术关键点和欲保护点" not in template


def test_active_yh_prompts_do_not_reference_obsolete_five_chapter_structure() -> None:
    active_paths = [
        "prompts/disclosure_builder.md",
        "prompts/disclosure_self_check.md",
        "prompts/disclosure_preview.md",
        "prompts/iteration_context.md",
        "prompts/merger.md",
        "prompts/correction_handler.md",
        "INSTALL.md",
        "tools/README.md",
        "tools/mermaid_render.py",
    ]

    forbidden_phrases = [
        "第五章权利要求书式强化",
        "合并范围以第五章为主",
        "改第三章",
        "第四章、第五章论点",
        "3.4.1",
        "3.5",
        "第六章实施例",
        "3.2 系统框图",
        "3.4 流程图",
        "mermaid 系统框图与流程图",
    ]

    for path in active_paths:
        text = read_text(path)
        for phrase in forbidden_phrases:
            assert phrase not in text, f"{path} still contains legacy phrase: {phrase}"


def test_disclosure_builder_yh_is_only_a_thin_compatibility_redirect() -> None:
    yh_builder = read_text("prompts/disclosure_builder_yh.md")

    assert "disclosure_builder.md" in yh_builder
    assert "template_reference_yh.md" in yh_builder
    assert len(yh_builder.splitlines()) <= 30

    duplicated_rule_phrases = [
        "章节结构",
        "图示生成流程",
        "交付检查",
        "Images 2.0 提示词",
        "附图统一放在第 13 章",
        "第 14 章“实物照片”必须保留",
    ]
    for phrase in duplicated_rule_phrases:
        assert phrase not in yh_builder


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
