from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_yh_template_exists_and_covers_required_sections() -> None:
    template_path = ROOT / "prompts" / "template_reference_yh.md"
    assert template_path.exists()

    template = template_path.read_text(encoding="utf-8")
    required_sections = [
        "发明名称",
        "关键词",
        "相关提案",
        "摘要",
        "最能说明本方案的附图",
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


def test_yh_template_defines_image_generation_contract() -> None:
    template = read_text("prompts/template_reference_yh.md")

    required_terms = [
        "Images 2.0",
        "images/",
        "图示1_",
        "图示2_",
        "图示3_",
        "图注",
        "附图标记",
        "黑白线条图",
        "不得为了装饰",
        "同一技术特征或对象",
        "专利交底书风格",
        "不要在图示图片内部生成",
        "图名和说明",
    ]
    for term in required_terms:
        assert term in template


def test_yh_template_documents_physical_photos_as_required_section() -> None:
    template = read_text("prompts/template_reference_yh.md")

    assert "没有则填写「无」" in template
    assert "实物照片" in template


def test_builder_and_skill_use_yh_template_by_default() -> None:
    builder = read_text("prompts/disclosure_builder.md")
    skill = read_text("SKILL.md")

    assert "template_reference_yh.md" in builder
    assert "template_reference_yh.md" in skill
    assert "template_reference.md" in skill
    assert "发明人在专利系统中是否提交过相似技术方案" in builder
    assert "没有则填写「无」" in builder
    assert "图示图片内部不要生成" in builder


def test_readme_keeps_system_and_flow_chart_language() -> None:
    readme = read_text("README.md")

    assert "系统框图、流程图" in readme
    assert "专利风格" in readme
