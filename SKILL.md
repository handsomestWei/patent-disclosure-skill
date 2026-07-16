---
name: yh-patent-disclosure-skill
description: "Use when the user needs Chinese patent mining, prior-art search, patent avoidance discussion, technical disclosure drafting, YH 15-section disclosure generation, Word export, or iterative correction of an existing patent disclosure."
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 专利挖掘与交底书生成

本 Skill 覆盖 **专利点挖掘 → 检索查重 → 交底书生成 → 自检完善**。触发词：专利挖掘/交底书/查新等，或使用 `/yh-patent-disclosure-skill` 等斜杠命令。
**入口规则**：每阶段进入前必须先 `Read` 对应 prompt 文件；阶段结束时声明完成凭证，满足出口条件方可进入下一阶段。细则以各 prompt 为准。

## 执行序列（严格按序，不可跳步）

### 1. 阶段 A — 边界确认
`Read prompts/intake.md` → Q1-Q3 收敛边界 → 汇总 bullet 确认
→ Q1 无参考文件则跳 B 直入 C
**出口**：Q1-Q3 已回答或注明缺口，路由方向已确定

### 2. 阶段 B — 项目扫描（条件执行）
`Read prompts/project_scan.md` → `.docx`/`.pptx` 先 `docx_to_md.py` / `pptx_to_md.py` 转 Markdown → 输出扫描摘要
→ 仅当 A.Q1 有参考文件且非迭代纠错时执行；否则跳过
**出口**：优先级文档已扫描并阅读，扫描摘要已输出

### 3. 阶段 C — 专利挖掘与交互讨论
`Read prompts/patent_points_analyzer.md` + `prompts/prior_art_search.md`
→ 候选专利点 → 查新（新增必检 / 删除跳过 / 修改判断实质） → 避让讨论 → 替代方案与保护点 → 结论摘要
→ 避让时加读 `prompts/patent_avoidance_methods.md`
→ **循环至用户确认结论摘要**
**出口**：结论摘要已确认，专利点·区别·避让·保护点·替代方案均已定案

### 4. 阶段 D — 交底书生成
`Read prompts/disclosure_builder.md` + `prompts/template_reference_yh.md`
→ Q1 确认发明名称 → 基于 C 结论摘要按 YH 15 项写 Markdown → **出图：每幅优先 Image2 / Images 2.0，连接/调用失败重试 3 次，3 次均败则 Mermaid 降级；内容错误修 prompt 重试** → 落盘
→ 仅允许名称确认和生成类问题提问（专利点/查新/避让讨论已在 C 完成）
→ 声明 D 完成收据 → **立即进入 E**
**出口**：Markdown 已落盘（含时间戳），图示已处理，完成收据已在对话中声明

### 5. 阶段 E — 全量检查与交付
`Read prompts/disclosure_self_check.md`
→ figure_check → 全量自检 → **回顾验证 C/D 阶段完成凭证与 Image2 降级依据** → 全部通过 → 生成 `.docx`
**出口**：figure_check OK，全部检查项通过，`.md` + `.docx` 已交付

### 迭代模式
已有稿上补充/纠错时，读 `prompts/iteration_context.md` → `merger.md` 或 `correction_handler.md` → 新时间戳落盘 + 修订记录。**不重跑全流程**，除非用户明确要求重新挖掘专利点。

## 全局铁律

1. **检索查重，避开已有专利点**：基于差异化提出反问，必要时借鉴其他行业类似专利挖掘新的金点子
2. 查新优先国知局公布公告链路（`cnipa_epub_search.py`），异常再降级 WebSearch
3. Agent 保持独立判断——与查新证据/技术事实冲突时给出具体证据，不盲从
4. 定稿必交付 `.md` + 同名 `.docx`，文件名 `{发明名称}_{YYYYMMDDHHmmss}`
5. 去 AI 痕迹在 E 阶段执行，不得改动技术事实·查新结论·公式参数·附图标记·保护边界
6. 自检清单不入正文，仓库脚注不入正文

## 工具索引

- Office 转 Markdown：`tools/docx_to_md.py`、`tools/pptx_to_md.py`
- 国知局查新：`tools/cnipa_epub_search.py`；细则见 `prompts/prior_art_search.md`
- 附图一致性：`tools/figure_check.py`
- 图示/公式/Word：`tools/mermaid_render.py`、`tools/math_render.py`、`tools/md_to_docx.py`
- 迭代留档：`tools/iteration_dialog_log.py`

详细命令与依赖见 `tools/README.md`。
