# 交底线稿出图（公共方法）

实用新型与外观成文前**必须**走本文件。Agent 在写 brief / 调门禁之前 **`Read` 本文**。

实现：`tools/image_gen.py`。先跑：

```bash
python skills/patent-disclosure/tools/image_gen.py --case-dir "outputs/{案件标识}"
```

看 JSON 的 `mode` / `fallback`。stderr 前缀 `IMAGE_GEN:`。

仅当用户**已经明确说不要线稿**，或环境变量 `PATENT_SKILL_SKIP_LINEART=1`，才整段跳过。

## 线稿从哪来（只有两条）

1. **材料里已有合格线稿**：`kind: lineart`，且内容匹配 + 画质过关（见打分）。**直接入文**，不再生成。  
2. **大模型生成**：先图生图；图生图不可用则 **先写参考图细节描述，再文生图**。无参考图则直接文生图。

**不是**线稿（不得标成 `kind: lineart`）：

- CAD / STEP 投影（`kind: cad` 的 SVG/PNG）— **任何类型都不入文**
- 实拍、截图、场景图、效果图 — **不得当线稿**；外观的干净实拍见下方「入文」。发明用户点名的技术环境示意图按 `disclosure_builder.md` §7.4 入文，不要套本表 `photo_scene` 默认不入。

这些仍打分；分数够才可能成为图生图的参考图。

## 扫描打分（填 figure_plan 时必做）

对每张候选图 **Read 识图**，写：

| 字段 | 含义 |
|------|------|
| `kind` | `lineart` 仅当本来就是结构/外观线稿（专利附图、干净黑白轮廓）。CAD 投影写 `cad`，实拍写 `photo_clean` / `photo_scene` |
| `relevance` | 0–100，与本案主题/部件/外形是否同一对象 |
| `quality` | 0–100：清晰、少遮挡、不是瞎画/糊图/广告拼图。**外观**另须过 `design_view_cnipa.md`（未过则不得超过 69） |
| `score` | 可与 `0.5*relevance+0.5*quality` 一致 |

合格已有线稿（走途经 1）：`kind: lineart` 且 `score>=70`，若写了分项则 **relevance 与 quality 均 >=70**，文件存在。瞎画、与本案无关、CAD 投影：**不能**标成合格线稿。

**外观另加**（`prompts` 先 `Read` `references/design_view_cnipa.md`）：正投影（或立体图角色正确）、各视比例一致、无尺寸线/中心线/阴影线、图内无图号/视图名。电子申请画布对准 JPEG、不超过 150mm×220mm、72–300 DPI。未过该清单则 `quality` **不得超过 69**，**不得** `existing_lineart`，必须重画。实拍按 4.2.3：透视棚拍不得当合格 `photo_clean` 正投影。

## 入文

按专利类型：

| 类型 | Markdown + Word 须嵌入 | 不入文 |
|------|------------------------|--------|
| **外观设计** | **干净实拍**（`photo_clean`）**和**合格/生成的 **线稿**（`kind: lineart`）。两套文档内容一致，用 `md_to_docx.py` 出同名 `.docx`，勿只贴线稿漏实拍、也勿只出 md 不出 Word。 | CAD 投影；重场景/包装（`photo_scene`）默认不入 |
| **实用新型** | 合格/生成的 **线稿** | CAD、实拍（可作图生图参考） |

- 新生成的线稿默认 `use_in_disclosure: true`（实用先按件写出子 SVG 再拼总图，再 overlay 件号；叠标后须读图按 `parts` 名称核对引出线，见 `structure_lineart_assist.md` / `structure_lineart_compose.md`）。  
- 外观实拍条同样 `use_in_disclosure: true`，与对应视线稿用 `relates_to: same_state` 互链。  
- `kind: cad`：**禁止** `use_in_disclosure: true`。

CAD 投影进 figure_plan 后**重评分**，再跑本脚本；有合格线稿才跳过生成，否则图生图（CAD/实拍可作参考）或文生图。另存新时间戳稿。CAD 图本身不入文。

## 生成策略（途经 2）

`image_gen.py` 给出 `mode`：

| mode | 何时 | Agent 做什么 |
|------|------|----------------|
| `existing_lineart` | 已有合格线稿 | 入文这些 path；**不要**再调生图 |
| `img2img` | 有合格参考图（含高分 CAD/实拍） | 宿主图生图，`reference_images` 为条件输入 |
| `txt2img` | 没有任何过线的参考图 | 按 schema + `gen_prompt` 文生图 |

`mode=img2img` 时必带 `fallback: describe_then_txt2img`：

1. 先尝试图生图。  
2. 宿主没有图生图 / 调用失败 / 无法把参考图当条件输入 → **不要停**。对每张参考图写一段可见细节（轮廓、开口、相对位置、禁止臆造的部分），写入 `lineart_assist/{视}_describe.md`。  
3. 用该描述 + `gen_prompt` **文生图**，仍禁止发明未见结构。`gen_prompt` 和线稿只许出现 `structure_schema.parts` / 本视 `visible_part_ids` 里的件；其余进 `uncertain`，不要画进轮廓、不要写进权要。

不要写死某一家出图工具名。

**怎么出图**：按 `prompts/figure_generation.md` 执行（定后端、样图、一图一 job、读图 QA、登记）。门禁 jobs 写出后用 `figure_jobs.py prepare --from-lineart-jobs` 建 job。CLI 后端对有参考图的 job 走 `image_api.py` 的 edit，即真正的图生图；只有 edit 也不可用时，才走上面的 `describe_then_txt2img`。后端为 `local`（无生图能力）时，线稿无本地等价物，按上文在交付里说明缺图。

**外观生成规格**（途经 2）：`gen_prompt` 与画布直接对准 `design_view_cnipa.md`（正投影或正确立体图、各视比例一致、禁尺寸线/中心线/阴影线、图内无图号/视图名、JPEG、不超过 150mm×220mm、72–300 DPI）。不要先出草稿留给申请文件加工。
