# 外观线稿（成文前必做）

**公共合同先读**：`prompts/image_gen.md`（线稿只有两条路；CAD 不得当线稿、不得入文）  
**视图口径**：`references/design_view_cnipa.md`（审查指南 4.2；与申请文件同一清单）  
**本文件合同**：`references/schemas/design_lineart_brief.schema.yaml`  
**前置**：已有或本轮将写出的 `appearance_schema.yaml` + `figure_plan.yaml`（见 `fill_appearance_schema.md`）  
**性质**：交底入文线稿。途经 1 用材料里已有合格线稿；途经 2 由大模型生成（图生图优先，否则先描述再文生图）。  
**外观入文**：干净**实拍**与**线稿**都要进 Markdown 和 Word；实拍不是线稿，但必须贴进交底。

## 开关

- **默认开启**。不问用户。仅当用户**已经明确说不要线稿**，或 `PATENT_SKILL_SKIP_LINEART=1`，才整段跳过。  
- **禁止**把 CAD / STEP 投影、实拍、场景图当成线稿（不得改 `kind: lineart`）。CAD 不入文。

## 步骤

### 0. 规划途经

```bash
python skills/patent-disclosure/tools/image_gen.py --case-dir "outputs/{案件标识}"
```

按 JSON `mode`：

| mode | 做什么 |
|------|--------|
| `existing_lineart` | 材料已有合格 `kind: lineart`：入文这些 path，**不要**再调生图 |
| `img2img` | 有合格参考图（含高分 CAD/实拍）→ 写 brief → 门禁 → 图生图；失败则 `describe_then_txt2img` |
| `txt2img` | 无过线参考图 → 写 brief（`source_paths` 可空）→ 按 schema 文生图 |

`design_photos` 列表中的干净实拍须 `use_in_disclosure: true`。

### 1. 读 YAML，联读多视

1. **`Read`** `appearance_schema.yaml`（或 json）与 `figure_plan.yaml`。  
2. 按 `figure_plan.relates_to` 联读多图；件名/造型特征跨图一致。  
3. **`Write`** `design_lineart_brief.yaml`：  
   - `enabled: true`  
   - `overall_shape` / `product_form` / `claimed_faces` / `design_points` / `uncertain` 对齐 AppearanceSchema  
   - `views[]` **只含**要点落面对应正投影 + 立体图；**禁止**为 `omitted_views` 或未见背面/底面生图  
   - 途经 2 且有参考图：每个 `views[]` 填存在的 `source_paths`（CAD/实拍均可作参考；实拍另条入文，CAD 不入文）  
   - 途经 2 且无参考图：`source_paths` 可空  
   - `source_figs` / `relates_hint` 抄自 figure_plan  
   - `view_name` / 图题用官方全称（主视图、后视图、左视图、右视图、俯视图、仰视图、立体图）  
   - `gen_prompt`：黑白外观轮廓线稿、正投影（立体图除外）、各视比例一致、无彩色无棚拍阴影、不发明未见结构、保留可见轮廓与开口/倒角；实线只画 `line_scope.claimed`，虚线只画 `line_scope.unclaimed`（可空则全实线），各视同一部位线型相同；**禁止**尺寸线、中心线、定位线、件号引出线、工程剖面阴影、图内图号/视图名；画布对准不超过 150mm×220mm、72–300 DPI；有参考则「以参考图为准」

### 2. 门禁

```bash
python skills/patent-disclosure/tools/design_lineart_gate.py \
  --case-dir "outputs/{案件标识}" --prepare-jobs
```

成功则写出 `lineart_assist/design_lineart_jobs.json`（含 `gen_mode` / `fallback_mode`）。

### 3. 出图（仅 `mode` 不是 `existing_lineart`）

对每一 job，按 `prompts/image_gen.md`：

1. 有 `reference_images`：先图生图。宿主不能图生图或失败 → 对每张参考图写可见细节到 `lineart_assist/{视}_describe.md`，再文生图。  
2. 无参考图：按 `gen_prompt` + AppearanceSchema 文生图。  
3. 不要写死某一家出图工具名。  
4. 输出写到 `output_path`；宿主不能指定路径则复制过去。  
5. 具体执行（后端、样图门、job、读图 QA、登记）见 `prompts/figure_generation.md`：`figure_jobs.py prepare --from-lineart-jobs outputs/{案件}/lineart_assist/design_lineart_jobs.json`，QA 过后 `record`。

### 4. 回写 figure_plan

**线稿与干净实拍都入文**，分配连续 `fig`。CAD 条保持 `use_in_disclosure: false`。`photo_scene` 默认不入。

```yaml
- fig: 1
  role: perspective
  path: assets/view_perspective.jpg
  covers: ["立体图"]
  kind: photo_clean
  use_in_disclosure: true
  reason: 立体实拍
  relates_to:
    - fig: 2
      relation: same_state
      note: 对应线稿
- fig: 2
  role: perspective
  path: lineart_assist/….png
  covers: ["立体图"]
  kind: lineart
  relevance: 80
  quality: 80
  score: 80
  use_in_disclosure: true
  reason: 大模型生成的外观线稿
  relates_to:
    - fig: 1
      relation: same_state
      note: 对应实拍
```

### 5. 成文纪律

- 正文「见图 N」引用实拍与线稿；**Markdown 与同名 Word 都要嵌这两组图**（`md_to_docx.py`）。图题用官方视图名，标在图下方，不写入图片像素。按要点落面出图，**不要**默认补六视。  
- 线稿按 `design_view_cnipa.md` 一次画到规格；未过清单须重画，不得把草稿留给申请文件加工。  
- **禁止**把 CAD 投影或实拍写成线稿。透视棚拍不得当合格正投影实拍。  
- **禁止**线稿上画尺寸线、中心线、定位线、件号引出线、图号。  
- `uncertain` 中的特征不得画死成设计要点。

## 自检（内部）

- [ ] 已跑 `image_gen.py`；CAD 未当合格线稿、未入文  
- [ ] `existing_lineart` 则未再调生图  
- [ ] 否则已图生图，或已「先描述再文生图」/ 文生图  
- [ ] 干净实拍与线稿均为 `use_in_disclosure: true`；md 与 docx 都已嵌入  
- [ ] 多视参照了 `relates_to` / `relates_hint`；线稿视与 `claimed_faces` 一致，未为省略面出图  
- [ ] `line_scope` 已锁定；各视实线/虚线同一口径；已跑 `check_design_views.py`  
- [ ] 线稿无尺寸线 / 中心线 / 定位线 / 件号引出线 / 图内图号；图题为官方视图名  
- [ ] 已按 `design_view_cnipa.md` 复核；未过清单的已有线稿已重画，未走 `existing_lineart`  
