# 申请文件 · 图型决策

权要写完后、画附图之前：按权要语言选定图型，写入产出目录 `figures/figure_plan.yaml`。交底目录已有的 `figure_plan.yaml` 只当材料，不要覆盖。

合同：`references/schemas/application_figure_plan.schema.yaml`。

## 决策（按权要原文，可多选）

| 权要语言 | `kind` |
|----------|--------|
| 「包括如下步骤/以下步骤」/「步骤1…」 | `flowchart` |
| 系统/装置 + 模块、单元、处理器 | `block_diagram` |
| 内部、内设、腔体、剖视 | `section` |
| 可拆卸、分解、依次套设、从…拆出 | `exploded` |
| 第一/第二状态、锁定/触发、切换至 | `multi_state` |
| 交底入文线稿 | 保留 `lineart`，再按上行补缺 |
| 点名场景图 | `source_image` |

发明方法独权默认要流程图；另有系统独立权项则加框图。`section` / `exploded` / `multi_state` 无论发明还是实用新型，**只在交底有对应入文线稿时实施**（脚本已自动把无源图型挂 `source: pending`）；不要为了凑套图去画权要没写到的剖视/爆炸。

剖视 / 爆炸 / 多状态：优先用交底 `relates_to` 已标明的入文线稿升格。交底没有对应图则 `source: pending`，记问题清单，禁止编内部结构。

每条写清 `reason` 和 `covers`（可见件号或模块名）。

```bash
python skills/patent-application/tools/plan_figures.py \
  --claims <产出>/权利要求书.md \
  --type invention \
  --out <产出>/figures/figure_plan.yaml
```

实用新型加上 `--disclosure-plan <交底>/figure_plan.yaml`。看 `APPLICATION_FIG_PLAN:`。再按 `figures.md` 出图，种类须落在本清单里。
