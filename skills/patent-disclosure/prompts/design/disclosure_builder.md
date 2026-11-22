# 外观设计 · 交底/设计说明成文（Step 7）

**本文件仅用于外观设计。** 发明 / 实用新型分见对应目录。

命名时间戳、脱敏、禁止仓库脚注等公共纪律可参照 `../invention/disclosure_builder.md` §7.3 / 文末清洁要求。  
成文前须 AppearanceSchema（`prompts/fill_appearance_schema.md`）及同目录 **`figure_plan.yaml`**（`references/schemas/figure_plan.schema.yaml`）。

外观文件实务格式因代理所而异；本技能交付 **Markdown + 同名 Word**。视图说明须同时嵌入**干净实拍**与**线稿**（两套文档一致，用 `tools/md_to_docx.py`；勿只出 md、勿漏实拍或漏线稿）。

## 7.1 建议结构

```
1. 注意事项（代理人可读、公开充分）
2. 一、产品名称与用途
3. 二、设计要点（形状 / 图案 / 色彩或其结合；对齐 schema.design_points）
4. 三、视图说明（按 `product_form` + `claimed_faces` 的正投影/立体图；对齐 schema.views + **仅嵌 figure_plan 入文图**；省略面写入简要说明）
5. 四、与在先外观的主要差异（查新后写；禁止无依据贬低）
6. 五、其它（可选：使用状态参考图说明；勿写内部结构）
```

## 7.2 文头

```markdown
# 外观设计说明（交底底稿）

**产品名称**：[待填写]

**技术联系人**：
- 姓名：[待填写]
- 电话：[待填写]
- 邮箱：[待填写]

**专利类型**：外观设计
```

## 7.3 写作硬性要求

- 只写**看得见的造型/图案/色彩**，不写内部电路、卡扣受力、工艺步骤。  
- 视图与 `claimed_faces` 对齐；故意不交的面用 `omitted_views` 在简要说明写清（相同/对称/无要点），**不要**默认补六视。要点落面缺源图才写入 `uncertain`。正文「见图 N」**只引用** `figure_plan` 中 `use_in_disclosure: true` 的条目（按 `fig`），勿临场扫全目录。实线/虚线以 `line_scope` 为准，各视同一部位线型相同；检查清单不写入交底正文。  
- **多视联读**：立体/正交/局部之间用 `relates_to`（`same_state` / `alternate_view` / `detail_of`）；正文说明须与之一致，跨图造型特征勿互相矛盾。  
- **入文同时嵌干净实拍与合格线稿**（`photo_clean` + `kind: lineart`）。实拍不得标成线稿；CAD 禁止入文。交底外观图按审查指南 4.2 与电子申请常见图幅出图；申请文件用同一清单核查，不改原图。  
- **线稿（必做）**：成文前已按 `references/design_view_cnipa.md` + `prompts/image_gen.md` + `prompts/design_lineart_assist.md` 选用或生成；未过 4.2 须重画。不问用户。  
- **交付**：`.md` 与同名 `.docx` 均须含上述实拍与线稿。  
- 查新：按 `prior_art_search.md`。有专利检索 MCP 则跳过公布站；否则 `skills/patent-disclosure/tools/crawl/cnipa_epub_search.py --type design`，第一轮后按结果页 **LOC** 做 `--class` 第二轮；不足 4 条则同 LOC 回补第一轮，仍少可仅 `--class` / 相邻号再查，禁止编造。每条在先外观须可核验来源。Google Patents 可选，被墙即跳过。  
- `not_design_signals` 非空时须反问是否改实用新型/发明。  
- **禁止**交付正文末尾追加技能仓库 / `examples/` /「虚构教学」脚注。

## 7.4 命名与交付

- 主文件名：`{产品名规范化}_{YYYYMMDDHHmmss}.md`（规则同发明 §7.3：去占位、非法字符、≤80 字、凡交付必时间戳）。  
- 配图：按 `figure_plan.path` 拷到交付同级 `assets/` 或写相对路径；勿覆盖旧交付。实拍与线稿都拷。  
- **必须**：`tools/md_to_docx.py` 生成同名 `.docx`（与 md 同一套入文图）。

## 7.5 自检（内部）

执行 `../disclosure_self_check.md` **通用项 + §8.5 外观设计**，并确认：

- [ ] 文头为外观设计  
- [ ] 设计要点可追溯 AppearanceSchema  
- [ ] 已写 `product_form` / `claimed_faces`（官方全称）；正投影按落面而非默认六视；`omitted_views` 已入简要说明（无则 `[]`）；`line_scope` 已锁定  
- [ ] 已跑 `check_design_views.py`，`视图检查清单.md` 已落盘；清单不写入交底正文  
- [ ] 视图仅来自 `figure_plan` 且「见图 N」与 `fig` 对齐；干净实拍与线稿均已入文；图题在图外正下方、未烧进像素  
- [ ] 入文多视/局部的 `relates_to` 已写且正文联读一致（可无场景参考图）  
- [ ] 线稿经 image_gen + design_lineart_gate，且过 `design_view_cnipa.md`；CAD 未入文；透视棚拍未当 `photo_clean`；实拍未标成 lineart  
- [ ] 已交付同名 `.md` 与 `.docx`，两套都嵌实拍与线稿  
- [ ] 未把功能构造写成外观要点  
- [ ] 查新 `--type design`；已按 LOC 做 `--class` 第二轮（或第一轮无分类号已按造型要点过滤）；不足 4 条已同 LOC 回补，未编造凑数  
- [ ] 交付回复在 **`## 交付后请确认` 之前**已有方向摘要（`../disclosure_preview.md`）；末块为 **`## 交付后请确认`**（`../delivery_confirm.md`）；政策简报仅第 4 条且按 **`skills/patent-exam-policy/prompts/soft_nudge.md`**
- [ ] **`## 交付后请确认` 第 1 条**：若 cad_scan 为 `ask_enable_step_parse`，交底已落盘后再以 **`(b)` 标签**反问是否开启 STEP 解析；未得「是」未装依赖；若同轮公式 PNG 也待问则按 `delivery_confirm.md` 让位于 `(a)`

表例见同目录 **`template_reference.md`**。
