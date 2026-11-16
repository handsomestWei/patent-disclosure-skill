# 申请文件 · 附图

发明 / 实用新型：交底 mermaid / 彩色 PNG **只当结构来源**。申请附图须黑白线框。图号写在说明书「附图说明」和插图下方的正文，**不要**画进 PNG/SVG。PNG 按 SVG 内容包围盒截取，不要整页 A4 留白。不要用交底包 `structure_lineart_compose`。外观见文末「外观」节，不走黑白升格。

先按 `figure_plan.md` 写出产出目录 `figures/figure_plan.yaml`。下面出图的 `kind` 必须落在该清单里；不要另画权要没点到的剖视/爆炸。剖视、爆炸、多状态有交底线稿才升格，否则保持 `pending` 并记问题清单。

## 发明

| 种类 | `kind` | 标号 |
|------|--------|------|
| 系统框图 | `block_diagram` | 虚线分组 + 框内模块名；**不**标（10）（20），**不**拉引出线。各列按自身模块数自上而下紧排，不要把较少模块的一列撑成与邻列相同槽位数 |
| 方法流程图 | `flowchart` | 框内写「步骤一…」，与独权同序同义；**不**拉引出线，**不**用 S1、201 |
| 点名示意图 | `source_image` | 用户点名或交底已入文的场景/拓扑/对照图；`source` 为源文件；**不**重画楼层剖面 |

主流程图框数与方法独权步骤数一致。分支、回环写在从属和实施例，不要在独权图上另编步骤。

摘要附图：主流程图（`abstract: true`）。点名场景图不当摘要附图，除非用户指定。

## 点名图（发明 / 实用都适用）

只处理用户自然语言指定或 `@` 的路径，以及交底正文已经编号嵌入的示意图。

1. **理解**：图上对象、关系、图例。
2. **判别**：技术示意图 / 拓扑 / 流程照片 / 结构线稿 / 界面截屏 / 图标切图 / 营销场景。
3. **匹配**：框图、流程仍用脚本重画；环境/拓扑/实施例对照图用 `source_image` 或实用升格脚本入文，编号接在图 1、图 2 之后；图标、切图、营销场景不入文，对话说明原因。

禁止扫描 `node_modules`、`dist`、`build`、`src/assets`、前端切图目录。未点名则不要自己去工程里捞图。不承诺把源图改画成公布稿剖面。

写入 `application_plan.yaml` 的 `named_figures`。

## 实用新型升格

交底线稿不得原样充当申请附图。对 `figure_plan` 中 `use_in_disclosure: true` 的 **lineart**：

```bash
python skills/patent-application/tools/compose_application_figure.py \
  --source <交底线稿.png或.svg> --fig N --out-dir <产出>/figures
```

要求：黑白、按内容裁切、图号只在正文；件号与 `structure_schema.parts` / 权要同一张表（交底 overlay 已有件号则保留，不要另编）。CAD、实拍不升格入申请附图。

## 外观

外观**不走**本节升格。见 `prompts/design_application.md` 与 `references/design_view_cnipa.md`。  
禁止对本案跑 `compose_application_figure.py`。交底入文图原样复制到产出 `figures/`；不合格只写入问题清单。

## 步骤（发明）

1. 按 `figures/figure_plan.yaml` 写 `figures/invention_figures.yaml`（合同见 `references/schemas/invention_figures.schema.yaml`）。只为清单中的 `flowchart` / `block_diagram` / `source_image` 生成 YAML。YAML 同时是生图规格与本地渲染源，生图时也要先写。
2. **生图（后端不是 `local` 时）**：先 `Read` `prompts/figure_generation.md`。

```bash
python skills/patent-application/tools/figure_jobs.py prepare --case-dir <产出> \
  --from-invention-yaml <产出>/figures/invention_figures.yaml
```

逐图出图（样图为主流程图）→ 读图 QA（框内文字逐字、框数与独权一致、无 S1、无件号引出、纯黑白、图内无图号）→ `figure_jobs.py record`。登记时自动转真黑白并按内容裁切，写出 `figures/图N.png`、`图N.svg`（abstract 另写 `摘要附图.png`）。未过 QA 的图 `block` 后只对该图跑第 3 步加 `--only N`，再 `fallback`。`source_image` 不生图，仍用第 3 步 `--only N` 出图。

3. 本地渲染（后端为 `local`，或第 2 步回退的图）：

```bash
python skills/patent-application/tools/render_invention_figures.py \
  --plan <产出>/figures/invention_figures.yaml \
  --out-dir <产出>/figures            # 只出个别图时加 --only N（可重复）
```

4. 看 `APPLICATION_FIG:`。SVG 必有；PNG 供 Word。PNG 失败记问题清单。

不做 TIFF。
