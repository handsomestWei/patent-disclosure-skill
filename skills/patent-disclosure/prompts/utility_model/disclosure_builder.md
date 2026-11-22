# 实用新型 · 交底书成文（Step 7）

**本文件仅用于实用新型。** 发明细则见 `../invention/disclosure_builder.md`；外观见 `../design/disclosure_builder.md`。

公共规则（命名时间戳、脱敏、查新 URL、`abstract` 必用、禁止正文写自检清单 / 仓库脚注）与发明 **§7.3 / 第一章硬性要求** 一致时，直接引用发明 builder 对应节，**勿复制发明的 3.2/3.4 mermaid 系统主线**。

成文前须已有 StructureSchema（`prompts/fill_structure_schema.md`）及同目录 **`figure_plan.yaml`**（`references/schemas/figure_plan.schema.yaml`）。

## 7.1 章节结构（实用新型）

```
1. 注意事项
2. 一、相关技术背景与最接近现有技术的缺点
   - 1.1 现有技术（结构向；含检索；每条须 URL；abstract 必用）
   - 1.2 现有技术存在的缺点（对应结构缺陷，如难拆装、占孔多）
3. 二、本实用新型所要解决的技术问题
4. 三、技术方案详细阐述（结构主线）
   - 3.1 总体构成（部件清单，对齐 schema.parts）
   - 3.2 连接与配合（对齐 schema.relations；可附表）
   - 3.3 空间布局与附图说明（嵌入脱敏结构图 + 件号）
   - 3.4 结构作用 / 使用或拆装过程（可短流程；勿写成纯方法专利主线）
   - 3.5 关键尺寸或材料（可选；uncertain 勿写死）
5. 四、与现有技术相比的优点（完整效果句，构造写进句子；F 号最多句末括注，见发明 **§7.10**）
6. 五、技术关键点与欲保护点（装置/结构书式）
7. 六、其它（实施例、效果）
```

**禁止**：以算法步骤、工艺参数表作为第五章主保护点；把 `uncertain` 写成既定事实；把纯外观美感当构造创新；把源图/原文未见的部件写进第三章部件表或第五章。

## 7.2 文头

```markdown
# 技术交底书

**案件名称**：[待填写]一种……装置/结构

**技术联系人**：
- 姓名：[待填写]
- 电话：[待填写]
- 邮箱：[待填写]

**专利类型**：实用新型
```

注意事项三条口径与发明文头相同（代理人可读、充分公开、配合补材）。

## 7.3 命名与交付

与发明 **§7.3** 相同：`{案件名规范化}_{YYYYMMDDHHmmss}.md` + 同名 `.docx`（凡交付必时间戳；勿覆盖旧稿）。

图示：

- **只嵌** `figure_plan.yaml` 中 `use_in_disclosure: true` 的图，按 `fig` 序号写「如图 N」；**禁止**绕过清单扫全 `assets/` 临场挑图。  
- **入文只选合格 `lineart`**；`cad` / 实拍禁止当线稿入文。若清单缺失或与主题不符，先按 `fill_structure_schema.md` **重写 figure_plan** 再成文。  
- **多图联读**：正文「如图 M 为图 N 的局部/剖视…」须与 `relates_to` 一致；跨图件号同一套命名。  
- **结构线稿（必做）**：成文前已按 `prompts/image_gen.md` + `prompts/structure_lineart_assist.md` + `prompts/structure_lineart_compose.md` 选用或生成；图上件号须与 `structure_schema.parts` 一致。CAD 投影不得入文。  
- 连接关系可用表格；必要时用简短 mermaid `flowchart` 表达「A —卡扣→ B」（**不是**发明那套系统框图/调度流程图）。  
- 若有 mermaid，定稿可用 `tools/mermaid_render.py` 转 PNG。

## 7.4 第三章写作要点

1. **先表后文**：部件表（件号、名称、形状）→ 关系表（from/to/type/where）→ 叙述。  
2. **图必有号**：正文「如图 N」与 `figure_plan` 的 `fig`/`path`/`covers` 一致；钩部、缺口等关键局部单独说明。  
3. **图际可追溯**：有总装+局部时，叙述顺序与 `relates_to`（如 `detail_of`）对齐。  
4. **结构作用一句清**：该构造解决什么装配 / 受力 / 通道 / 拆装问题。  
5. **与 schema 闭环**：parts/relations/`spatial` 在正文均有落点；schema 未写的复杂公差勿杜撰。

## 7.5 第五章欲保护点口径

- 推荐：「一种……装置，包括……；其特征在于……（连接/形状限定）」  
- 避免：「一种……方法，包括以下步骤……」作为唯一独立点  
- **分 5.1 必要技术特征 / 5.2 优选特征**，按**删除测试**归类（删掉该构造后还能否解决第二章的装配/受力/通道/拆装问题：不能→5.1，仍能→5.2）；5.1 条目与 1.1 比对表的 **Fk 同编号**，每条**复述构造全文**，件号与 `structure_schema.parts` 同一张表。口径见发明 **`../invention/disclosure_builder.md` §7.10**（比对维度换成部件与连接关系；门禁优先 **带疑点过**，不必抬到「过」；正文 Fk 出场同样适用）。  
- 对话中「本稿可调整」须来自本稿结构特征，勿凭空捏造；定稿回复先按 **`../disclosure_preview.md`** 写方向摘要（默认不等人），末块见 **`../delivery_confirm.md`**。

## 7.6 自检（内部）

执行 `../disclosure_self_check.md` **通用项 + §8.4 实用新型 + §8.7 法定要件**（客体组按结构类口径），并确认：

- [ ] 文头为实用新型  
- [ ] 过 / 带疑点过：1.1 已点名最接近的一篇并给出部件/连接维度的逐特征比对表（编号单独成列 + 表后特征一览；有组合风险才 D2 补行）。第三章、第六章未把 Fk 当主语。**不过**：未点名假 D1，区别对材料/常规结构做法写。第二章技术问题**未**写入本案构造手段、**未**在问题句后点名 Fk；带疑点过时写了证据边界  
- [ ] 第三章可追溯 StructureSchema  
- [ ] 附图仅来自 `figure_plan` 且「如图 N」与 `fig` 对齐  
- [ ] 总装+局部入文时 `relates_to` 已写且正文联读一致  
- [ ] 查新使用 `--type utility_model`（或 all 后人工筛）；第二轮不足 4 条已同 IPC 回补，未编造凑数  
- [ ] 未把外观美感 / 纯方法写成构造主线  
- [ ] 结构线稿已按 image_gen + structure_lineart_assist + 按件拼装 选用或生成（含 `parts/{视}_{id}.svg`）；件号对齐 StructureSchema；CAD 未入文  
- [ ] 交付回复在 **`## 交付后请确认` 之前**已有方向摘要（`../disclosure_preview.md`）；末块为 **`## 交付后请确认`**（`../delivery_confirm.md`）；政策简报仅第 4 条且按 **`skills/patent-exam-policy/prompts/soft_nudge.md`**
- [ ] **`## 交付后请确认` 第 1 条**：若 cad_scan 为 `ask_enable_step_parse`，交底已落盘后再以 **`(b)` 标签**反问是否开启 STEP 解析；未得「是」未装依赖；若同轮公式 PNG 也待问则按 `delivery_confirm.md` 让位于 `(a)`

模版表例见同目录 **`template_reference.md`**。
