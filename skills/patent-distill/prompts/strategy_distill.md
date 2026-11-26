# 专利蒸馏 · 思路

每个 `cases/{案件}/` 是一个案件。先填对人看的表，再把洗掉事实的切法写进该案的 `playbook.yaml`。枚举只许用 `references/contract.yaml` 里的值。多案并列入批次时，各案各写，文风另在批次根目录。

## 人读：`策略观察.md`

用下面的标题，写完删掉 TODO。

1. **材料**：每份文件的角色。写明是 strong、weak 还是 observe。
2. **点清单**：交底有，就从交底列点（对象、手段、效果、有没有实施例）。没有交底，就只从说明书实施例列，并标明来源弱。
3. **点与权要对照**：每一行一个点，列：独权、从属、仅说明书、交底有但申请无。说明书有而权要没有，写成「披露未请求保护」，不要写成「申请人放弃」。
4. **时间轴**：只写材料里真有的阶段。同一案同时放入公布文本和授权公告时，才写两稿差异。`evidence.laid_open_pub` 与 `evidence.grant_pub` 都有值、而 `pair_in_batch` 为 false 时，时间轴写明缺了哪一份，不比较两稿。没有审查意见全文时，时间轴不写审查意见。
5. **观察**：能指回权项号或章节的切法。
6. **推测**：动机、产品上没写的点、为何不申请。这一节不进入 playbook。

## 模型读：`playbook.yaml`

`strategy.callable` 为 true 时才有这份文件。改切法，保留 `must_not_copy` 三条，把 `apply` 三句从 TODO 换成短指令。优先读案件目录里的 `全文.txt`（已去掉汉字间空格和页眉）。

`strength` 为 `observe` 时不写 `playbook.yaml`。切法只留在 `策略观察.md` 的观察节，撰写新案不读取该案。

| 块 | 给以后哪一步 | 写什么 |
|----|----------------|--------|
| `disclosure` | 交底第五章 | 必要/优选怎么切、一篇几个核心、第六章是否留未升为保护点的实施例 |
| `claims` | 权要 | 独权卡在哪一层、几条独权、从属层、什么留在说明书、什么不进独权 |
| `spec` | 说明书 | 先撑满独权特征，再决定是否多写未请求保护的实施例 |
| `layout` | 周边布局 | 没有 `has_family: true` 时 `enabled: false`，`pattern` 留空 |
| `apply` | 三步各一句 | 写「本案事实只来自当前交底；本档只约束切法」以及上表对应的禁止项 |

`apply` 每句不超过 400 字。`claims` / `spec` / `disclosure` 里的字符串不超过 80 字，防止把样本句子抄进来。

`status` 与 `profile.strategy.status` 相同。先保持 `draft`，等用户在交付里确认后才可改为 `confirmed`，并同时把 `samples_confirmed` 设为 `true`。`strength` 与 `profile.strategy.strength` 相同，按 `intake.md` 的表，不要改成更强。

## 对照时怎么拆权要

独权看它卡住的是主题名称、结构关系、方法步骤、模块关系、关键参数，还是外观整体。从属只归入 `preferred_param`、`branch`、`system_map`、`embodiment` 四层，与申请包从属层同名。不要在 playbook 里重写样本权要。

外观：`independent_grain` 用 `appearance_overall`，`point_split` 可用 `design_views`，`support_rule` 可用 `view_consistency`。不要把外观蒸成方法步骤。
