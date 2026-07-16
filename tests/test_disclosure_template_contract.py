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
    assert "没有实物照片时，填写" in template
    assert "保留本章" in template
    assert "删除第 14 章" not in template
    assert "images/" in template
    assert "不使用独立汇总表格" in template
    assert "图中关键附图标记" in template


def test_step7_default_uses_yh_template_without_legacy_template_reference() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    skill = read_text("SKILL.md")

    assert "template_reference_yh.md" in builder
    assert "默认" in builder
    assert "15 项" in builder or "15项" in builder
    assert "图示规划表" in builder
    assert "不写入正文" in builder
    assert "不得伪造图片" in builder

    assert "disclosure_builder.md" in skill
    assert "template_reference_yh.md" in skill
    assert "Images 2.0" in builder
    assert "images/" in builder
    assert "图示01_" in builder
    assert "仅在用户明确要求 YH" not in skill

def test_legacy_template_file_and_references_are_removed() -> None:
    assert not (ROOT / "prompts/template_reference.md").exists()

    checked_paths = [
        "SKILL.md",
        "tools/mermaid_render.py",
        "tools/md_to_docx.py",
        "prompts/disclosure_builder.md",
        "prompts/template_reference_yh.md",
        "prompts/disclosure_self_check.md",
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

    assert "name: yh-patent-disclosure-skill" in skill
    assert "/yh-patent-disclosure-skill" in skill


def test_self_check_is_image_consistency_authority_and_skill_routes_to_it() -> None:
    skill = read_text("SKILL.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    assert "disclosure_self_check.md" in skill
    assert "YH" in self_check
    assert "Images 2.0" in self_check
    assert "images/" in self_check

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
        "关键附图标记",
        "无独立附图说明汇总表格",
        "无独立附图标记表",
        "错误文字",
        "装饰风格",
    ]
    for item in required_self_check_items:
        assert item in self_check


def test_yh_core_writing_principles() -> None:
    """Verifies core writing principles exist across builder + template (not exact phrasing)."""
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    # --- 技术底稿定位 ---
    for text in (builder, template):
        assert "技术底稿" in text
        assert "专业专利团队" in text

    # --- 克制写作 ---
    for text in (builder, template):
        assert "宣传语" in text  # 不要写成平台宣传语 / 发明名称非宣传语
        assert "必要对比" in text
    assert "编号列清楚" in builder or "编号列清楚" in template
    assert "保护点不宜过多" in builder or "保护点不宜过多" in template

    # --- 实施方式与附图 ---
    assert any(kw in builder for kw in ["实施方式用纯文字描述", "纯文字描述实施方式"])
    assert any(kw in builder for kw in ["附图统一放在第 13 章", "附图集中第 13 章"])

    # --- 附图风格（builder §7.4 为权威源） ---
    for kw in ("白底黑蓝线条", "少量绿色/红色", "附图标记仍必须严格一致"):
        assert kw in builder

    # --- Self-check 覆盖 ---
    self_check_concepts = [
        "技术底稿定位", "发明名称", "背景技术", "技术问题",
        "实施方式", "第 13 章", "保护点数量",
    ]
    for concept in self_check_concepts:
        assert concept in self_check

    # --- 无旧版章节残留 ---
    assert "第五章「技术关键点」" not in self_check


def test_yh_section_content_requirements() -> None:
    """Verifies each YH chapter has required content guidance (concept coverage, not exact phrasing)."""
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    # --- 第 3 章 相关提案: 一行汇总 ---
    assert any(kw in template for kw in ["汇总为一行", "一行文字"])

    # --- 第 5 章 代表性附图: 嵌入 + 指向第 13 章 ---
    assert "代表性附图" in template
    assert "第 13 章" in template

    # --- 第 7 章 术语: 非表格 ---
    assert "不要使用表格" in template or "不得使用表格" in template
    assert any(kw in template for kw in ["字数不宜过多", "精简描述", "数字序号"])

    # --- 第 8 章 背景技术: 六要素 ---
    for kw in ("1.1 文献", "公开数据库名称与检索词", "请勿写"):
        assert kw in builder or kw in template or kw in self_check
    for kw in ("本发明与现有技术的本质区别", "分点索引", "核心缺陷", "局限性", "公开源 URL"):
        assert kw in template or kw in self_check

    # --- 第 8 章 1.1 / 1.2 ---
    for kw in ("技术方向分类引用", "充分理解摘要后再概括", "逐条说明本发明的解决思路"):
        assert kw in builder or kw in template

    # --- 无旧版模板残留 ---
    for forbidden in ("## 三、技术方案详细阐述", "## 四、与现有技术相比的优点", "## 五、技术关键点和欲保护点"):
        assert forbidden not in template


def test_yh_implementation_detail_requirements() -> None:
    """Verifies implementation detail requirements exist in builder + template + self_check."""
    builder = read_text("prompts/disclosure_builder.md")
    template = read_text("prompts/template_reference_yh.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    required_concepts = [
        "应用场景",
        "模块间关联关系",
        "数据流或控制流",
        "流程步骤与附图节点",
        "符号与变量定义",
        "关键技术参数",
        "实施例",
    ]
    for concept in required_concepts:
        assert concept in builder, f"'{concept}' missing in builder"
        assert concept in template, f"'{concept}' missing in template"
        assert concept in self_check, f"'{concept}' missing in self_check"

    # --- 参数约束声明 ---
    assert "不作为权利要求限制" in builder or "不作为权利要求限制" in template

    # --- 有益效果与保护点呼应 ---
    assert any(kw in builder for kw in ["先概括性观点", "概括性观点，再分点详述"])
    assert any(kw in builder for kw in ["第 9 章技术问题", "与第 9 章", "技术问题和第 15 章保护点呼应"])


def test_active_yh_prompts_do_not_reference_obsolete_five_chapter_structure() -> None:
    active_paths = [
        "SKILL.md",
        "prompts/disclosure_builder.md",
        "prompts/disclosure_self_check.md",
        "prompts/iteration_context.md",
        "prompts/merger.md",
        "prompts/correction_handler.md",
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



def test_skill_emphasizes_prior_art_avoidance_and_new_patent_ideas() -> None:
    skill = read_text("SKILL.md")
    analyzer = read_text("prompts/patent_points_analyzer.md")
    prior_art = read_text("prompts/prior_art_search.md")
    builder = read_text("prompts/disclosure_builder.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    # Prior art avoidance messaging in C stage, search, and quality gate
    for text in (skill, analyzer, prior_art, self_check):
        assert "检索查重" in text
        assert "避开已有专利点" in text
        assert "反问" in text
        assert "其他行业类似专利" in text
        assert "新的金点子" in text

    # YH 15 项 template reference (not in analyzer which is discussion-stage)
    for text in (skill, prior_art, builder, self_check):
        assert "YH 15 项" in text


def test_disclosure_flow_invokes_humanizer_without_changing_patent_boundaries() -> None:
    skill = read_text("SKILL.md")
    builder = read_text("prompts/disclosure_builder.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    assert "去 AI 痕迹" in skill
    for text in (builder, self_check):
        assert "去 AI 痕迹" in text

    for text in (skill, builder):
        assert "技术事实" in text
        assert "查新结论" in text
        assert "公式参数" in text
        assert "附图标记" in text
        assert "保护边界" in text


def test_figure_check_tool_is_documented_in_skill_contract() -> None:
    skill = read_text("SKILL.md")
    self_check = read_text("prompts/disclosure_self_check.md")

    assert "figure_check.py" in skill
    for text in (self_check,):
        assert "figure_check.py" in text
        assert "第 13 章附图" in text
        assert "图号完全对应" in text
        assert "图片文件是否存在" in text


# --- 执行纪律契约（L1-L4） ---

def test_each_stage_prompt_has_execution_checklist_and_exit_conditions() -> None:
    """每个阶段 prompt (A/B/C/D/E) 必须含"执行清单"和"出口条件"."""
    stage_prompts = [
        "prompts/intake.md",
        "prompts/project_scan.md",
        "prompts/patent_points_analyzer.md",
        "prompts/disclosure_builder.md",
        "prompts/disclosure_self_check.md",
    ]
    for path in stage_prompts:
        text = read_text(path)
        assert "执行清单" in text, f"{path} missing 执行清单"
        assert "出口条件" in text, f"{path} missing 出口条件"


def test_skill_md_has_numbered_execution_sequence() -> None:
    """SKILL.md 必须含编号 L1 执行序列，覆盖 A-E 完整路由."""
    skill = read_text("SKILL.md")
    assert "intake.md" in skill
    assert "disclosure_builder.md" in skill
    assert "disclosure_self_check.md" in skill
    # 执行序列必须包含 A B C D E 五个阶段标记
    assert "A" in skill and "B" in skill and "C" in skill and "D" in skill and "E" in skill
    # 硬性要求：每阶段必须先 Read 对应 prompt
    assert "Read" in skill


def test_disclosure_builder_image2_always_priority_with_retry() -> None:
    """D 阶段 Image2 策略：始终优先尝试，连接失败重试 3 次，内容错误修 prompt."""
    builder = read_text("prompts/disclosure_builder.md")
    # 优先 Image2 / Images 2.0
    assert "优先" in builder
    assert "Image" in builder
    # 连接/调用失败重试，最多 3 次
    assert "重试" in builder
    assert "3 次" in builder or "三次" in builder
    # 降级 Mermaid 只在连接失败后
    assert "降级" in builder
    assert "Mermaid" in builder
    # 内容错误（错字/结构/标记）应修 prompt 重试 Image2，不得直接降级
    assert "提示词" in builder


def test_disclosure_builder_has_d_stage_completion_receipt() -> None:
    """D 阶段出口条件含完成收据声明，完成后立即进入 E 全量检查."""
    builder = read_text("prompts/disclosure_builder.md")
    assert "完成收据" in builder or "阶段D完成" in builder
    assert "进入" in builder
    assert "E" in builder


def test_self_check_has_retrospective_audit_of_upstream_stages() -> None:
    """E 阶段自检必须回顾验证上游阶段（C/D）的完成情况与 Image2 降级依据."""
    self_check = read_text("prompts/disclosure_self_check.md")
    # E 必须反查上游阶段完成凭证或阶段账本
    assert "完成凭证" in self_check or "完成收据" in self_check or "阶段" in self_check
    # 必须检查 Image2 降级是否仅在 3 次连接失败后才发生
    assert "Image" in self_check
    assert "降级" in self_check


def test_builder_forbids_subjective_image2_suitability_judgment() -> None:
    """D 阶段禁止 LLM 自行判断"适不适合 Image2"."""
    builder = read_text("prompts/disclosure_builder.md")
    forbidden = [
        "判断是否适合",
        "判断适不适合",
        "判断该图是否适合",
        "判断图片是否适合",
        "根据图片类型选择",
    ]
    for phrase in forbidden:
        assert phrase not in builder, f"builder contains forbidden subjective judgment: {phrase}"
