# 交底 · 蒸馏参考（旁路）

用户点名蒸馏档（`outputs/patent-distill/` 下的目录或档案 id），或经根 `SKILL.md`「组合路由」带来档案路径时才用。没有就跳过本文件，不要自己去 `outputs/patent-distill/` 里找。

蒸馏档只给第五、六章的切法，不给技术事实。本案事实仍只来自发明人材料与 Step 5 查新。

## 读取（Step 5.5 之后、Step 7 之前）

```bash
python skills/patent-disclosure/tools/distill_ref.py --ref <档案目录或档案id> --type <invention|utility_model|design> --stage disclosure
```

| 输出 | 读什么 |
|------|--------|
| `DISTILL_REF_STYLE: … skip reason=交底不套申请文风` | 正常结果，文风只给申请文件用 |
| `DISTILL_REF_CASE: … use` | 该案 `playbook.yaml` 的 `disclosure` 块、`claims.never_in_independent`；`DISTILL_REF_APPLY` 的 `when_writing_disclosure` |
| `DISTILL_REF_CASE: … observe` | 该案 `策略观察.md` 的「观察」节，只作参考；「推测」节不读 |
| 其他 `skip` / `DISTILL_REF_SKIP:` | 不读，原因写进交付摘要 |

`status: draft` 的档也可用。不要改蒸馏档里的任何文件。

## 逐条适配

| 情况 | 处理 |
|------|------|
| 档案切法与本案删除测试结论不同 | 以删除测试为准（`invention/disclosure_builder.md` §7.10），跳过该条 |
| 档案是一篇多个核心，本案材料只撑一个核心（或反之） | 按本案；需拆案仍按 `patent_points_analyzer.md` |
| `unclaimed_in_chapter6: true`，本案材料没有多余实施例 | 不编实施例，跳过该条 |
| 档案里的 `claims` 独权条数、从属层、`spec`、`layout` | 交底不写权项，不用 |
| 外观 | 视图组切分可参考；不套发明第五章 |
| 领域与本案不同 | 只取切法，不取领域术语 |

## 用在哪里

| 档案内容 | 交底位置 |
|----------|----------|
| `disclosure.point_split`、`points_per_disclosure` | 第五章 5.1 / 5.2 的切分与核心数 |
| `claims.never_in_independent` | 哪类特征默认归 5.2（数值范围、可选支路等），仍过删除测试 |
| `disclosure.unclaimed_in_chapter6` | 第六章是否保留未升为保护点的实施例（材料有才写） |
| `apply.when_writing_disclosure` | Step 7 成文时的短指令 |
| 观察节 | 同上，只作参考，不当规则 |

样本里的方案、参数、件号、产品名一律不进本案。

## 交付

适配后的每一条按下表归类。判定标准是假设不读本档案、只按本包规则写，这一处的写法是否相同。这一步由你自行判断，不要拿去问用户。

| 分类 | 判断 |
|------|------|
| 改变了本稿 | 不读档案会写成别的样子 |
| 与默认一致 | 不读档案也会这样写 |
| 跳过 | 适配时判为不合适 |

定稿回复里、方向摘要之后、`## 交付后请确认` 之前，写一到两行「蒸馏参考」。只有「改变了本稿」的条目写成已使用：

```
蒸馏参考：example-batch-job-scheduler 改变了本稿：5.1 总构思写出派发去向（points_per_disclosure）；与本包默认一致：必要与优选切分、数值归 5.2；未使用：文风（交底不套申请文风）。
```

没有条目改变本稿时写「蒸馏参考：读取了 <档案>，各条与本包默认做法一致，未改变本稿写法」。档案全部跳过时写「蒸馏参考：未使用 <档案>（原因）」。用户要参考的专利只有公开号、没有本地全文时写「蒸馏参考：未使用 <公开号>（没有本地全文）」。用户没提参考时不写这一行。
