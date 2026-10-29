---
name: patent-application
description: "申请文件：把已有交底写成权利要求书、说明书、摘要与说明书附图。须指定交底目录；仅缺材料才终止。内容争议写入问题清单，不阻塞主文件。交付后请确认须摘要清单。已有产出上改稿则另存新时间戳目录。须显式触发。代为撰写申请文件属专利代理业务，本稿为内部底稿，提交前应经有资质专利代理师复核。"
user-invocable: false
version: 5.1.0
---

# 申请文件

## 用途

把已有交底写成权利要求书、说明书、摘要与说明书附图（四件套：Markdown + Word + 黑白图）。内容歧义不阻塞主文件，缺口写入问题清单。

## 何时用

须用户点名（申请文件 / 申请底稿 / 申报材料 / 权利要求书 / `/申请底稿` / `/patent-apply`），并**指定交底材料目录**。案卷会稿调度本包时视为已点名，仍须有交底目录。

## 输入

同案交底产出：交底书（时间戳 `.md`，有则兼用 `.docx`）；发明用正文（框图/流程在 mermaid 里）；实用新型用 `structure_schema` + `figure_plan` + 入文线稿；外观用 `appearance_schema` + `figure_plan` + 入文实拍/线稿。仅**缺文件**时终止。发明人/申请人未填只记清单，不终止、不挡案卷轮次。

## 步骤

1. **`Read`** `prompts/guardrails.md` → `intake.md`
2. 已有申请产出上改稿（未要求整案重写）：**`Read`** `iteration_context.md` → `iteration.md`（新时间戳目录、出 Word、问题清单），到此结束
3. 跑 `tools/material_gate.py --case-dir <交底目录>`；退出码 2 则停
4. 发明 / 实用新型：撰写语言与句式参照 `references/专利语句库.md`（句式/词库/附图标记）、`references/公布文本风格指南.md`、`references/撰写任务流程.md`（章节-意图-核心句-逻辑，含附图规范；案例参考 `references/5篇公布文本风格总结.md`）；撰写流程 `claim_strategy.md` → `claims_builder.md` → `figure_plan.md` → `figures.md` → `specification_builder.md` → `numeral_register.md` → `consistency.md`
5. 外观：先 `Read` `references/design_view_cnipa.md`，只走 `design_application.md`；跑本包 `check_design_views.py`
6. 本包 `tools/emit_application_docx.py` 出 Word；交付前 **`Read`** `prompts/self_check.md` 自检一遍，跑本包 `check_support.py --dir <产出>`（实用新型/外观加 `--case-dir <交底目录>`）；**`Read`** `issues.md`，写 `问题清单.md`（不入正式文件），并在**同一条交付回复**末块 **`## 交付后请确认`** 给出路径、摘要条目、请用户先看清单

整仓路径：`python skills/patent-application/tools/…`。

## 护栏

- 细则 `prompts/guardrails.md`。Word 与附图脚本只用本包 `tools/`。
- **合规边界**：代为撰写专利申请文件属专利代理业务（《专利代理条例》第 9、24 条），须由取得执业许可的代理机构及执业证的代理师办理。本包产出为**内部撰写底稿**，不构成法律意见、不评价授权；对外提交前应经有资质专利代理师复核。本人自用申请、或作为发明人向代理师提供材料，不在此限。

## 产出物

`outputs/patent-application/{案件标识}_{时间戳}/`：四件套（Markdown + Word + 黑白图）+ 旁路 `问题清单.md`（外观另有 `视图检查清单.md`）。对话末块标题 **交付后请确认**。
