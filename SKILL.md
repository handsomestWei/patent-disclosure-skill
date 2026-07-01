---
name: yh-patent-disclosure-skill
description: "Use when the user needs Chinese patent mining, prior-art search, patent avoidance discussion, technical disclosure drafting, YH 15-section disclosure generation, Word export, or iterative correction of an existing patent disclosure."
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 专利挖掘与交底书生成

本技能覆盖 **专利点挖掘** → **查新与差异化** → **交底书生成** → **自检完善**。执行时只把 `SKILL.md` 当入口路由；每个阶段开始前先 **`Read`** 对应 `prompts/*.md`，细则以该 prompt 为准。

## 核心目标

先做**检索查重**，避开已有专利点；再基于差异化提出建议和**反问**，必要时借鉴**其他行业类似专利**的解题逻辑，挖掘可保护的**新的金点子**。最终正文须精简、不冗长，写清专利逻辑，并严格遵守 **YH 15 项**模板。

## 触发

- 用户提到：专利挖掘、专利点、技术交底书、交底书、专利交底书、查新、现有技术对比。
- 用户使用：`/yh-patent-disclosure-skill`、`/patent-disclosure-skill`、`/patent-disclosure`、`/交底书`。
- 用户明显是在已有交底书或上一轮输出上继续工作：改章节、补材料、补实施例、修正事实/参数、调整表述等。

## 阶段路由

| 阶段 | 先读文件 | 用途 |
|------|----------|------|
| A | `prompts/intake.md` | 边界与输入确认：Q1 参考文件→Q2 发明概述→Q3 专利类型倾向；无文件则跳过 B 直入 C |
| B | `prompts/project_scan.md` | 项目扫描；`.docx`/`.pptx` 先用 `tools/docx_to_md.py` / `tools/pptx_to_md.py` 转 Markdown |
| C | `prompts/patent_points_analyzer.md` + `prompts/prior_art_search.md`；进入避让讨论时加读 `prompts/patent_avoidance_methods.md` | 候选专利点 → 查新 → 避让讨论（按需加载经典避让法）→ 替代方案与保护点初议 → 结论摘要确认。**深度交互讨论均在此阶段完成**。循环至用户确认后退出 |
| D | `prompts/disclosure_builder.md` + `prompts/template_reference_yh.md` | **以生成为主，有限讨论**：Q1 确认发明名称→基于 C 阶段结论摘要按 YH 15 项写 Markdown 正文、出图、命名、脱敏、公式体例。仅允许发明名称和生成类问题询问用户 |
| E | `prompts/disclosure_self_check.md` | 唯一质量门：figure_check、逻辑闭环、公式参数、格式引用、Word 输出 |
| 迭代 | `prompts/iteration_context.md` + `prompts/merger.md` 或 `prompts/correction_handler.md` | 已有稿的增量合并或纠错，另存新时间戳文件并维护修订记录 |

## 主流程

```
A → B（有参考文件时）→ C（候选专利点→查新→避让讨论→循环至结论摘要确认）→ D（确认发明名称→基于结论摘要写 MD + 图示，仅限名称与生成类提问）→ E（检查、修订、出 .docx）
```

执行要点：

1. 查新优先按 `prior_art_search.md` 使用国知局公布公告链路；异常或无果再降级 WebSearch。
2. C 阶段完成**深度交互讨论**（专利点确认、查新结果判断、避让策略、替代方案、保护点），循环至用户确认结论摘要后退出。D 阶段以**生成为主**，仅保留发明名称确认（Q1）和交底书生成类问题的有限讨论。
3. C 阶段查新**按需执行**：新增专利点→必须检索；删除专利点→不检索；仅修改表述/调整范围→判断是否需要检索（技术实质改变则检索，否则跳过）。
4. 避让讨论中按需加载 **`patent_avoidance_methods.md`** 十类经典避让法（仅当查新命中相似专利、进入步骤 7 时加载）。与用户讨论时保持独立判断，不一味顺从——有疑点时给出具体证据和理由。
5. D 默认使用 **YH 15 项**技术底稿模板；图示、命名、脱敏、公式体例等细则只看 `disclosure_builder.md` 与 `template_reference_yh.md`。
6. E 是唯一质量门；交底书正文不得包含”自检清单”章节。
7. 交付定稿须同时产出 `.md` 与同名 `.docx`，文件名遵守 `disclosure_builder.md` 「输出文件命名」。
8. 定稿或迭代定稿前，在 E 阶段执行**去 AI 痕迹轻量审阅**（自查并修订 AI 腔残留，如机械排比、过度连接词、空泛强调、宣传腔调等；具体检查项见 `disclosure_self_check.md`「逻辑与闭环」）；不得改动技术事实、查新结论、公式参数、附图标记、章节结构或保护边界。

## 迭代模式

当用户意图是在**已有交底书**上补充或纠错时，不要默认回到 C 阶段全文专利点分析，除非用户明确要求重新挖掘专利点。

- 补充材料、扩展章节、按 「交付回复」 强化第 15 章：读 `iteration_context.md` → `merger.md`。
- 指出错误、事实/参数不符、保护点或表述调整：读 `iteration_context.md` → `correction_handler.md`。
- 结果必须另存为 `{发明名称}_{YYYYMMDDHHmmss}.md` 与同名 `.docx`，不覆盖旧稿；并追加 `交底书修订对话记录.md`。

## 工具索引

- Office 转 Markdown：`tools/docx_to_md.py`、`tools/pptx_to_md.py`
- 国知局查新：`tools/cnipa_epub_search.py`；细则见 `prompts/prior_art_search.md`
- 附图一致性：`tools/figure_check.py`
- 图示/公式/Word：`tools/mermaid_render.py`、`tools/math_render.py`、`tools/md_to_docx.py`
- 迭代留档：`tools/iteration_dialog_log.py`

详细命令与依赖见 `tools/README.md`。
