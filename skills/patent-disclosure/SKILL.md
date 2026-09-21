---
name: patent-disclosure
description: "中国专利交底书：发明/实用新型/外观设计的专利点挖掘、轻量查新与成文、保护型1+N专利布局。"
user-invocable: false
---

# 交底书编写

分步指令在 **`prompts/`**（本包内）。发明 / 实用新型 / 外观是**包内三个目录**，不是三个可触发技能。

| 步骤 | 文件 |
|------|------|
| Step 1 | `prompts/intake.md` |
| Step 2 | `prompts/project_scan.md` |
| Step 3–4 | `prompts/invention/` · `utility_model/` · `design/` 挖点 |
| 填表 / 线稿 | `prompts/fill_*`、`image_gen.md`、`*_lineart_*.md`；外观视图口径 `references/design_view_cnipa.md` |
| Step 5 | `prompts/prior_art_search.md`（轻量查新：3～4 个手段短语，公布模式每页 10 条，LLM 摘要精排） |
| Step 5.5 | 同文件「**D1 锁定与区别特征 Fk**」：主比对钉一篇最接近 + 逐特征表（可 D2 补行）+ **三态门禁**，落 `查新与区别定位_*.md`。三态都进 Step 6；**不过**仍成文但创造性降级，禁止假 D1 / 空喊创新性强 |
| Step 6 | `prompts/disclosure_preview.md` |
| Step 7 | 对应类型 `disclosure_builder.md` + `template_reference.md` |
| Step 8 | `prompts/disclosure_self_check.md` |
| 迭代 | `iteration_context.md` / `merger.md` / `correction_handler.md` |
| 旁路 · 保护型 1+N | 首篇定稿后 `prompts/fence/guardrails.md`；用户同意则 `decompose.md` → `design_around.md` → `matrix.md` → `plan.md`（family.yaml + 专利布局.md）→ `score.md`（立项后弱校验）→ 确认后 `dispatch.md` |
| 交付对话 | 定稿回复末块 `prompts/delivery_confirm.md`（标题固定 **交付后请确认**） |

查新工具：`tools/crawl/cnipa_epub_search.py`。整仓安装时路径为 `skills/patent-disclosure/tools/crawl/cnipa_epub_search.py`。著录检索不在本包，**禁止**当查新引擎调用。
交底交付后**不要**自动进入申请文件；用户点名并给出本目录后，再走 `skills/patent-application/SKILL.md`。
首篇 Step 8 之后，围栏只写在交付回复 **`## 交付后请确认`** 第 3 条（见 `prompts/delivery_confirm.md`），不先打分。用户说「专利布局 / 专利围栏 / 族树 / 做围栏」可强开，但仍须分解→突围→矩阵再立项。立项由模型直写 `outputs/{案件}/fence/专利布局.md`（章节见 `prompts/fence/plan.md`），yaml 只给校验和分件；不要出 HTML、不要用脚本转 md。立项后弱校验默认表 `references/scorecards/gbt42748_fence.yaml`：作答与门槛回写说明稿「立项校验」；对话按过门槛/临界/未过门槛给推荐或不推荐，不叫高价值达标。口头确认「按 C1、P1 写」后再分件。
`--type` 与 intake 一致；邻域召回：3～4 个手段短语 → `EPUB_CLASS_HINT` / IPC·LOC → `--class`（默认 1×1，公布模式每页 10 条）→ **LLM 对照摘要精排** 再锁 D1。不足 4 条则同分类号回补。第二轮导航失败保留第一轮，不要当成 0 条、不要因此降级 WebSearch。不要切列表模式、不要自建向量库。

线稿、CAD、公式、Word、PDF 出图用本包 `tools/`（`browser.py`、`mermaid_render.py`、`md_to_docx.py`、`pdf_to_md.py` 等）。

```bash
python skills/patent-disclosure/tools/fence/check_layout.py --decompose outputs/{案件}/fence/decompose.yaml
python skills/patent-disclosure/tools/fence/check_layout.py --family outputs/{案件}/fence/family.yaml --matrix outputs/{案件}/fence/matrix.yaml
python skills/patent-disclosure/tools/fence/check_scorecard.py -i outputs/{案件}/fence/scorecard.yaml --case-dir outputs/{案件}
```
