# 申请文件 · 蒸馏参考（旁路）

用户点名蒸馏档（`outputs/patent-distill/` 下的目录或档案 id），或经根 `SKILL.md`「组合路由」带来档案路径时才用。没有就跳过本文件，不要自己去 `outputs/patent-distill/` 里找。

蒸馏档只给写法与切法，不给技术事实。本案事实仍只来自交底。

## 读取

材料门禁通过后运行，可多次 `--ref`：

```bash
python skills/patent-application/tools/distill_ref.py --ref <档案目录或档案id> --type <invention|utility_model|design> --stage application
```

| 输出 | 读什么 |
|------|--------|
| `DISTILL_REF_STYLE: … use` | `style.md`、`sections/application.md` |
| `DISTILL_REF_CASE: … use` | 该案 `playbook.yaml` 的 `claims`、`spec`；`DISTILL_REF_APPLY` 两句指令 |
| `DISTILL_REF_CASE: … observe` | 该案 `策略观察.md` 的「观察」节，只作参考；「推测」节不读 |
| `… skip reason=…` / `DISTILL_REF_SKIP:` | 不读，原因写进交付摘要 |

`status: draft` 的档也可用。不要改蒸馏档里的任何文件。

## 逐条适配

脚本只做了机械筛选。写之前逐条判断能否用在本案，不合适就跳过该条，继续写。

| 情况 | 处理 |
|------|------|
| 与交底 5.1 / 5.2 的划分冲突（例如要把 5.2 的点升进独权） | 以交底为准，跳过该条 |
| `claims.leave_in_spec` 与交底 5.2 | 只决定数值例、替代方案留在说明书；交底 5.2 已列且有材料支持的优选点，仍按 `claim_strategy.md` 进从属，不因档案减少从属退路 |
| 依赖本案没有的对象（例如要求方法加系统两条独权，交底第五章没有系统） | 跳过该条 |
| 与本包护栏或各步 prompt 冲突（背景写法、步骤编号、附图标号、公式位置、摘要字数） | 以本包为准，跳过该条 |
| 领域与本案不同 | 文风只取章节口气与句式，不取领域术语 |
| 档案里的 `disclosure`、`layout`、`when_writing_disclosure` | 申请文件不用 |

## 用在哪一步

| 档案内容 | 步骤 |
|----------|------|
| `claims`：独权粒度、独权条数、从属层、留在说明书的内容、不进独权的内容 | `claim_strategy.md` 排 `claim_tree` 时作偏好 |
| `apply.when_writing_claims`；`sections/application.md` 的权要口气 | `claims_builder.md` |
| `spec`：支持规则、是否多写实施例、附图对应；`apply.when_writing_spec` | `specification_builder.md` |
| `style.md`；`sections/application.md` 的背景、实施方式、附图节 | 说明书各部分口气与附图说明 |
| 观察节 | 同上，只作参考，不当规则 |

外观申请只取文风里简要说明与视图命名的口气，思路档由脚本跳过。

样本里的方案、参数、件号、产品名、权要原句一律不进本案。

## 记录与交付

适配后的每一条按下表归类。判定标准是假设不读本档案、只按本包规则写，这一处的写法是否相同。这一步由你自行判断，不要拿去问用户。

| 分类 | 判断 |
|------|------|
| 改变了本稿 | 不读档案会写成别的样子 |
| 与默认一致 | 不读档案也会这样写 |
| 跳过 | 适配时判为不合适 |

在 `application_plan.yaml` 写 `distill_refs`（合同见 `references/schemas/application_plan.schema.yaml`），每个档案一条，按上表三类分别列出条目，跳过的写原因。

交付回复里，四件套路径之后、`## 交付后请确认` 之前，写一到两行「蒸馏参考」。只有「改变了本稿」的条目写成已使用：

```
蒸馏参考：example-batch-job-scheduler 改变了本稿：独权不写未定义的「可派发」（never_in_independent）；与本包默认一致：文风、从属分层；未使用：方法加系统两条独权（交底第五章没有系统对象）。
```

没有条目改变本稿时写「蒸馏参考：读取了 <档案>，各条与本包默认做法一致，未改变本稿写法」。档案全部跳过时写「蒸馏参考：未使用 <档案>（原因）」。用户要参考的专利只有公开号、没有本地全文时写「蒸馏参考：未使用 <公开号>（没有本地全文）」。用户没提参考时不写这一行。
