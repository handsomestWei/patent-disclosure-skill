# 实用新型结构线稿（成文前必做）

**公共合同先读**：`prompts/image_gen.md`（线稿只有两条路；CAD 不得当线稿、不得入文）  
**本文件合同**：`references/schemas/structure_lineart_brief.schema.yaml`  
**按件拼装（轮廓之后）**：`prompts/structure_lineart_compose.md`  
**前置**：已有或本轮将写出的 `structure_schema.yaml` + `figure_plan.yaml`（见 `fill_structure_schema.md`）  
**与外观分流**：外观用 `design_lineart_assist.md`；禁止混用。

## 开关

- **默认开启**。不问用户。仅当用户**已经明确说不要线稿**，或 `PATENT_SKILL_SKIP_LINEART=1`，才整段跳过。  
- **禁止**把 CAD / STEP 投影、实拍当成线稿入文。CAD 只当普通材料打分，分数够才可能作图生图参考。

## 步骤

### 0. 规划途经

```bash
python skills/patent-disclosure/tools/image_gen.py --case-dir "outputs/{案件标识}"
```

| mode | 做什么 |
|------|--------|
| `existing_lineart` | 材料已有合格 `kind: lineart`：入文这些 path；仍须按 `parts` overlay 件号（若原图无号） |
| `img2img` | 有合格参考图（含高分 CAD/实拍）→ 写 brief → 门禁 → 图生图轮廓；失败则先描述再文生图 |
| `txt2img` | 无过线参考图 → 写 brief（`source_paths` 可空）→ 按 StructureSchema 文生图 |

### 1. 读 YAML，联读多视 + 统一件号

1. **`Read`** `structure_schema.yaml`（或 json）与 `figure_plan.yaml`。  
2. 按 `figure_plan.relates_to` 联读总装/局部；**跨图同一 `parts.id`**。  
3. **`Write`** `structure_lineart_brief.yaml`：  
   - `enabled: true`  
   - `structure_summary` / `parts_legend` 对齐 StructureSchema（`id`+`name` 不得改号）  
   - `callout_mode` 默认 **`overlay`**  
   - 有参考图则填存在的 `source_paths`；无参考图可空。`visible_part_ids` 为本视可见件  
   - `gen_prompt`：黑白结构线稿、不发明未见结构；**禁止**件号数字、引出线、尺寸线、中心线、点划剖切线、剖切箭头（剖视关系用 `figure_plan.relates_to`，不要让模型在外形图上画箭头）。默认不要让模型自由编造序号（留给 overlay）  
   - `visible_part_ids` 只列真实结构件；**不要**把「剖切指示」当可见零件去画  
   - `uncertain` 中的件不得列入本视必标序号

### 2. 门禁

```bash
python skills/patent-disclosure/tools/structure_lineart_gate.py \
  --case-dir "outputs/{案件标识}" --prepare-jobs
```

缺少 Structure / `visible_part_ids` 不在 `parts` → 拒绝。  
成功则写出 `lineart_assist/structure_lineart_jobs.json`。

### 3. 出图（轮廓 → 按件拼装 → 锚点 → 叠标 → 语义自查）

对每一 job：

1. **轮廓层**（`mode` 不是 `existing_lineart` 时）：按 `image_gen.md` 图生图或「先描述再文生图」或文生图，写入 `output_path`。已有合格线稿则用原图当本视轮廓。执行按 `prompts/figure_generation.md`：`figure_jobs.py prepare --from-lineart-jobs outputs/{案件标识}/lineart_assist/structure_lineart_jobs.json --with-callouts`。  
2. **按件拼装（必做）**：**`Read`** `prompts/structure_lineart_compose.md`。按 `parts` 写 `structure_lineart_compose.yaml`（每件一个槽位），跑 `structure_lineart_compose.py`：每件落 `lineart_assist/parts/{视}_{id}.svg`，总图 `*_composed.svg` 相对引用子文件。总装用 `crop`（子文件裁总装 PNG，隔离弱）；爆炸/分件用每件小图 `image`（仅 schema 已分开的可分离件，须先有单件图）。不要把整图 base64+clip 进总 SVG，也不要把一件再拆成筋/齿/螺栓。  
3. **锚点定位**（`callout_mode: overlay`）：大模型读取**拼装后的图**（优先 composed SVG 的预览，或无号轮廓），逐个定位 job `callouts` 对应部件；把归一化 `anchor`、附近**图外留白** `label`、`confidence` 持久化到案件目录 `structure_callout_anchors.yaml`。合同见 `references/schemas/structure_callout_anchors.schema.yaml`。该视填写 `base_svg_path` 指向 composed SVG。

   - **`anchor`**：引出线末端，必须落在**该件可见墨线**上（轮廓或剖面线），禁止停在空腔、孔洞内部或背景白底。
   - **`label`**：序号数字必须在整图**外轮廓之外**的留白里，禁止压在实体、剖面线、内腔或孔内；不要用 crop 窗的角点当序号位置（窗里往往仍是剖面线）。
   - 序号围绕结构就近分散，禁止全部排到画布同一条边；多条线从不同方向引出。
   **生图件号（后端不是 `local` 时先试）**：锚点写好后，用 `callout_{视}` job 以轮廓图为输入改图，只加件号与引出线，prompt 带上锚点坐标与 parts 表。读图核对下面第 5 步各项，**另加一条：轮廓与输入图不一致即不过**。一次不过就 `figure_jobs.py block` 后走第 4 步 overlay，**不要**反复改图纠号。通过则 `record`，跳过第 4 步，仍做第 5 步语义自查。
4. **精确叠标**：运行：

```bash
python skills/patent-disclosure/tools/structure_callout_overlay.py \
  --case-dir "outputs/{案件标识}" \
  --anchors "outputs/{案件标识}/structure_callout_anchors.yaml"
```

有 `base_svg_path` 时，脚本把件号组**注入**拼装 SVG，不覆盖零件图层。默认会按原图墨线**校正**：把压在实体/内腔上的序号推到外轮廓留白，把落在空腔的引线终点吸到最近墨线。`--no-autolayout` 可关闭。Python 仍不判断「标的是不是这件」；结果写入 `output_svg_path`。需要 PNG 时再用 `svg_screenshot.py --svg … --png …`。

5. **叠标后语义自查（必做，最多 2 轮校正）**：Python 通过 ≠ 图面对。须 **`Read` 叠标后的 PNG/SVG**（不要只看无号轮廓），对照本视 `visible_part_ids` + `structure_schema.parts` 的 **id+名称**：

   | 查什么 | 不合格则 |
   |--------|----------|
   | 每个必标件号是否都在图上 | 补锚点后重叠标 |
   | 序号是否压在实体、剖面线、内腔或孔内 | 改 `label` 到图外留白；优先让 overlay 自动推（不要靠 crop 窗角） |
   | 引出线末端是否落在**该名称对应的构造墨线**上（不是邻件、不是空腔） | 改 `anchor`/`label`，禁止改件号 |
   | 相邻易混件是否对调（腔体↔腔内件、轴↔转子、接头↔法兰、剖切符号↔零件） | 按名称把锚点挪到正确轮廓 |
   | 图上有号但 `visible_part_ids` 没有的 | 删该 callout，禁止自创件号 |
   | 序号全贴画布边缘、引出线全竖直/全水平 | 把 label 就近散开，改 `route` |

   校正只改 `structure_callout_anchors.yaml` 再跑 `structure_callout_overlay.py`（及必要时 `svg_screenshot.py`）。**禁止**为纠件号而二次文生图/图生图改轮廓或重拼零件。两轮后仍对不上的件写入 `uncertain` 或从本视 `visible_part_ids` 拿掉，不得硬标。

6. **`in_prompt` 降级**：仅当无法叠图时，把可见件号列表写入提示；生成后对照 `parts_legend`，错号则重做或改 overlay。
7. **`contour_only`**：只出无号轮廓；正文用部件表说明。仍建议按件拼装，便于日后补号。

### 4. 回写 figure_plan

**生成（或合格已有）线稿默认入文**。CAD / 实拍条 `use_in_disclosure: false`。

```yaml
- fig: 1
  role: assembly
  path: lineart_assist/….png   # 入文预览；可编辑源为 parts/{视}_{id}.svg + 同视 *_composed.svg / *_callouts.svg
  covers: ["1", "2", "总装"]
  kind: lineart
  relevance: 80
  quality: 80
  score: 80
  use_in_disclosure: true
  reason: 大模型生成的结构线稿（件号对齐 StructureSchema）
  relates_to: []
```

有总装+局部对时，补写 `relates_to: detail_of`。CAD 条不得改成入文。

### 5. 成文纪律

- 正文「如图 N」只引用合格线稿。  
- **禁止**把 CAD 投影写成线稿或入文。  
- **禁止**写成「已按国知局规范绘制的正式附图」。  
- 第三章部件表件号须与图上序号、`structure_schema.parts` 一致。

## 自检（内部）

- [ ] 已跑 `image_gen.py`；CAD 未当合格线稿、未入文  
- [ ] 已按 `structure_lineart_compose.md` 写出 `parts/{视}_{id}.svg` 与相对引用的总 SVG（非扁图、非总图 clip 整图）；一层一件号，未把筋/齿/螺栓拆成独立组  
- [ ] `parts_legend` / 图上件号与 StructureSchema 一致；跨图未改号  
- [ ] `structure_callout_anchors.yaml` 已落盘且含 `base_svg_path`；已 Read 叠标后的图；件号与部件名称一一对应；序号在结构外、引线末端在墨线上；校正只改 YAML 重叠标
- [ ] `uncertain` 件未画死序号、未用 crop/image 冒充已绘结构  
- [ ] 优先 overlay；未自创件号或子件号；轮廓层未画剖切箭头 / 中心线 / 件号  
- [ ] 未误用 `design_lineart_*`  
