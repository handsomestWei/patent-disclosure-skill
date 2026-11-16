---
name: patent-disclosure
description: "中国专利交底书：发明/实用新型/外观设计的专利点挖掘、轻量查新与成文、保护型1+N专利布局。"
user-invocable: false
---

# 交底书编写

## 用途

挖专利点、轻量查新、写成发明 / 实用新型 / 外观设计交底书；首篇定稿后可走保护型 1+N 围栏。发明 / 实用新型 / 外观是**包内三个目录**，不是三个可触发技能。分步指令在本包 **`prompts/`**。

## 何时用

用户说专利挖掘、交底书、查新、实用新型、外观设计，或 `/patent-disclosure`、`/交底书`。未显式指定类型时**默认发明**。  
「专利布局 / 专利围栏 / 族树 / 做围栏」走本包旁路（首篇已定稿；用户点名可强开）。不要因写申请、读专利、对照表自动进入。

## 输入

发明人材料、项目目录、可选 `.tex`；类型与联系人在 `prompts/intake.md` 收敛，不全可推断并注明假设。`--type` 与 intake 一致。线稿、CAD、公式、Word 出图、PDF 转 md 用本包 `tools/`。

## 步骤

| 步骤 | 文件 |
|------|------|
| Step 1 | `prompts/intake.md` |
| Step 2 | `prompts/project_scan.md`；有 `.tex` 再 `Read prompts/tex_scan.md` |
| Step 3–4 | `prompts/invention/` · `utility_model/` · `design/` 挖点 |
| 填表 / 线稿 | `prompts/fill_*`、`image_gen.md`、`*_lineart_*.md`；外观视图口径 `references/design_view_cnipa.md`；外观成文前 `tools/check_design_views.py`；结构案成文前 `tools/check_source_parts.py` |
| 出图 | 交底所有绘制类附图（3.2 框图 / 3.4 流程图 / 线稿 / 件号）出第一张图前 `Read` `prompts/figure_generation.md`：定后端 → 样图 → 一图一 job → 读图 QA → 登记；失败回退本地渲染 |
| Step 5 | `prompts/prior_art_search.md`（轻量查新：3～4 个手段短语，公布模式每页 10 条，LLM 摘要精排） |
| Step 5.5 | 同文件「**D1 锁定与区别特征 Fk**」：主比对钉一篇最接近 + 逐特征表（可 D2 补行）+ **三态门禁**，落 `查新与区别定位_*.md`。三态都进 Step 6；**不过**仍成文但创造性降级 |
| Step 6 | `prompts/disclosure_preview.md` |
| Step 7 | 对应类型 `disclosure_builder.md` + `template_reference.md` |
| Step 8 | `prompts/disclosure_self_check.md` |
| 迭代 | `iteration_context.md` / `merger.md` / `correction_handler.md` |
| 旁路 · 保护型 1+N | 首篇定稿后 `prompts/fence/guardrails.md`；用户同意则 `decompose.md` → `design_around.md` → `matrix.md` → `plan.md`（family.yaml + 专利布局.md）→ `score.md`（立项后弱校验）→ 确认后 `dispatch.md` |
| 交付对话 | 定稿回复末块 `prompts/delivery_confirm.md`（标题固定 **交付后请确认**） |

查新：`prompts/prior_art_search.md`，脚本 `tools/crawl/cnipa_epub_search.py`（整仓路径 `skills/patent-disclosure/tools/crawl/cnipa_epub_search.py`）。

围栏：Step 8 之后只在交付回复 **`## 交付后请确认`** 第 3 条询问。口径见 `prompts/fence/guardrails.md`。立项说明直接写 `outputs/{案件}/fence/专利布局.md`（章节见 `prompts/fence/plan.md`），`family.yaml` 只供校验和分件。弱校验表 `references/scorecards/gbt42748_fence.yaml`。口头确认「按 C1、P1 写」后再分件。

```bash
python skills/patent-disclosure/tools/fence/check_layout.py --decompose outputs/{案件}/fence/decompose.yaml
python skills/patent-disclosure/tools/fence/check_layout.py --family outputs/{案件}/fence/family.yaml --matrix outputs/{案件}/fence/matrix.yaml
python skills/patent-disclosure/tools/fence/check_scorecard.py -i outputs/{案件}/fence/scorecard.yaml --case-dir outputs/{案件}
```

## 护栏

- 细则在各步 prompt；围栏先 `Read` `prompts/fence/guardrails.md`。
- 禁止假 D1，禁止空喊创新性强。未披露部件写入 `uncertain`，不进入权要或说明书。
- 未确认立项说明，不分件写多篇交底。

## 产出物

交底书 Markdown + Word，查新与区别定位稿，可选 schema / 线稿 / 公式图（生图登记见 `figure_jobs.json`）；围栏在 `outputs/{案件}/fence/`。对话末块标题 **交付后请确认**。
