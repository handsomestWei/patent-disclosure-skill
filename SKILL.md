---
name: patent-disclosure-skill
description: "中国专利技能：挖掘专利点并撰写发明/实用新型/外观设计交底书；将已有交底改写为申请文件四件套；依据发明人材料衔接交底与申请；按著录项目检索公布公告；解读专利文献；基于已入库解读生成专利地图；对照审查政策撰写简报；辅助审查意见答复；编制权利要求对照表底稿（不构成法律意见）。| China patents: mine patent points and draft invention/utility-model/design disclosures; convert an existing disclosure into application documents; sequence disclosure and application from inventor materials; search CNIPA bibliographic records; interpret patent documents; generate a patent map from an interpreted vault; prepare examination-policy briefs; assist office-action responses; and prepare claim-chart worksheets (not legal opinions)."
version: "5.1.0"
user-invocable: true
argument-hint: "[可选：项目路径 / 交底书 / 申请底稿 / 交底申请一起做 / 专利检索 / 专利号或 PDF / 专利地图 / 专利围栏 / 政策简报 / 审查答复 / 对照表]"
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 中国专利技能

按用户意图 **`Read`** 对应入口的 `SKILL.md`，再按该流程执行。**先查「路由判定表」定去向，再看「通则」。**

## 能力总览

| 能力 | 做什么 | 入口 |
|------|--------|------|
| **交底** | 挖专利点 → 查新 → 成稿 → 迭代（发明 / 实用新型 / 外观）；首篇定稿后可做保护型 1+N 专利布局 | `skills/patent-disclosure/SKILL.md` |
| **申请文件** | 已有交底 → 权要 / 说明书 / 摘要 / 附图（撰写语言/句式/附图规范见 `skills/patent-application/references/专利语句库.md`、`撰写任务流程.md`、`公布文本风格指南.md`） | `skills/patent-application/SKILL.md` |
| **案卷** | 按发明人/工程师给的材料一趟写出交底书和申请文件 | `skills/patent-docket/SKILL.md` |
| **检索** | 公布站高级查询（发明人/申请人/分类号/名称/摘要等）；单图或权要可先抽关键字再查 | `skills/patent-search/SKILL.md` |
| **解读** | 公开号 / PDF / 全文 → 通俗笔记 + 图谱 | `skills/patent-reader/SKILL.md` |
| **对照表** | 权利要求特征（默认连从权一起拆） vs 对比文件 / 产品 / 标准，逐格证据与强弱（须点名；底稿，非法律意见） | `skills/patent-chart/SKILL.md` |
| **专利地图** | 已解读入库的案例摊成五种图（语义地形） | `skills/patent-map/SKILL.md` |
| **审查答复** | 审查意见问答与草稿；库薄时引导案例入库 | `skills/patent-oa/SKILL.md` |
| **政策简报** | 对照国知局口径，说明对交底写法/本稿的影响；改技能仅为旁路 | `skills/patent-exam-policy/SKILL.md` |

## 路由判定表

「**须点名**」= 只有用户明确说出该行触发词才进入，**禁止**由写交底或读专利自动进入。

| 用户这样说 | 前置门禁（不满足就停下说明） | 进入 | 明确不要做 |
|------------|------------------------------|------|------------|
| 专利挖掘、交底书、查新、实用新型、外观设计；`/patent-disclosure`、`/交底书` | 无 | 交底包 | 查新不进入检索包 |
| 专利布局、专利围栏、族树、保护型1+N、做围栏 | 首篇交底已定稿（用户点名可强开）；须分解 → 突围 → 矩阵 → 立项说明，立项校验写入 `专利布局.md` | **交底包旁路** `prompts/fence/` | 不进专利地图。未确认立项说明，不分件写多篇 |
| 申请文件、申请底稿、申报材料；`/申请底稿`、`/patent-apply` — **须点名** | **须指定交底目录**；缺 schema / 线稿 / 交底书则停，引导先补交底 | 申请文件包 | — |
| 交底申请一起做、从零出交底和申请、一条龙、帮写交底再出申请、按清单改、会稿、案卷；`/patent-docket` — **须点名** | 状态写 `outputs/docket/`；清单缺口最多来回三轮，缺事实问人、不编 | 案卷包（再由它 `Read` 交底或申请入口） | 只写交底，或只出四件套时，不进案卷 |
| 按著录字段查公布公告、个人公开清单、以图或权要生成检索式；`/patent-search` | 无 | 检索包 | 结果不写成交底查新 |
| 读专利、给出公开号或 PDF 且目标是「读懂」；`/patent-read`、`/读专利` | 无 | 解读包（**优先**） | 不跑交底成文，不自动进对照表 |
| 对照表、claim chart、无效对照、FTO 初筛、侵权对照、标准必要、可专利性、审查答复对照；`/patent-chart` — **须点名** | 左列须有公开号 / PDF / 权要 / `claim_features.json` / 交底 5.1；缺特征清单则派解读包 | 对照表包（从权默认随独权一起拆） | 不出法律意见 |
| 专利地图、案例地图；`/专利地图`、`/patent-map` — **须点名** | 需已有解读入库的 vault | 专利地图包 | 不因读专利或写交底进入 |
| 审查意见、OA、案例入库；`/oa` — **须点名** | 库薄时先引导入库 | 审查答复包 | — |
| 政策简报、政策雷达；`/政策简报`、`/patent-brief`、`/patent-exam-policy`；「技能进化 / `/patent-evolve`」同一入口 — **须点名** | 无 | 政策简报包 | 无点名不改技能文件 |

## 通则

- **工具归属**：填表、线稿、CAD、公式、Word 出图在交底包 `prompts/` 与 `tools/`；解读填表用解读包 `prompts/fill_*`；过 WAF 的 `browser.py`、Markdown 转 Word 的 `md_to_docx.py` **各包自带副本**。
- **脚本归属**：只用当前子技能自己的 `tools/`。同一能力已有本包副本时，跑本包这一份。
- **调度视同点名**：由案卷调度申请文件视为已点名申请文件，**仍须**有交底目录。由对照表派解读 / 检索视为已点名该包。
- **子技能封面**：各 `skills/*/SKILL.md` 统一六段：用途 / 何时用 / 输入 / 步骤 / 护栏 / 产出物。细则仍 `Read` 该包 `prompts/`。根文件只做路由，不套这六段。
- **交付末块**：各子技能交付回复末块标题统一为 **交付后请确认**；跨包口令以上表为准，交底**不得**在此节把申请、案卷、专利地图、对照表列为下一步。检索与专利地图可不设此节。

## 能力自述（用户问「你能做什么 / 还能做什么」时）

按**能力总览**复述 9 项，每项一句并给出触发说法；说明**申请文件 / 案卷 / 专利地图 / 审查答复 / 政策简报 / 对照表须点名**才会进入。本节只用能力总览，不用交底的「交付后请确认」。

## 合规边界

- **本技能是内部工作底稿辅助，不构成法律意见**；不做新颖性/创造性/授权结论，不宣称已通过国知局审查或客户端格式校验。
- **在中国，代为撰写专利申请文件、代为办理专利申请、代为答复审查意见等属专利代理业务**，须由依法设立的专利代理机构及取得执业证的专利代理师办理；无资质主体以本技能产出对外提交或替他人办理，可能违反《专利代理条例》。《专利代理条例》第 9、24 条对应行政责任。
- **建议**：交底书可自行完成或交给代理师（属发明人内部素材）；**权利要求书 / 说明书 / 摘要 / 附图四件套与审查意见答复稿应经有资质专利代理师复核后使用**。
- **数据**：著录检索、解读、对照表仅用公开专利信息，限个人研究与内部流程；遵守目标站点使用条款，勿高频/批量商业抓取。
- **全文 PDF 下载**：专利全文为法定公开信息；真人浏览器 GUI 下载属正常人工访问（过验证码为真人输入、非绕过技术措施）。仅限个人研究与内部流程，保持人工节奏、控制单次数量、勿自动化批量抓取，勿再分发/商业建库，不绕过登录/付费访问控制。
- **个人信息**：发明人/申请人等著录信息仅按检索需要取用；案例库（oa）默认脱敏；Obsidian 库路径先经用户确认再写入。

## 目录

```
SKILL.md                         # 本文件：子技能路由入口
skills/patent-disclosure/        # 交底（含填表/线稿/CAD/公式/docx；围栏旁路）
skills/patent-application/       # 申请文件四件套（须显式；须指定交底目录）
skills/patent-docket/            # 案卷：交底到申请一趟串起来（须显式）
skills/patent-search/            # 著录检索
skills/patent-reader/            # 解读
skills/patent-chart/             # 对照表（须显式）
skills/patent-map/               # 专利地图（须显式；读 vault，本机页面）
skills/patent-oa/                # 审查答复
skills/patent-exam-policy/        # 政策简报（技能进化为旁路）
```

## 环境与约定

- **默认语言**：面向用户的检索清单、交底书、申请文件、案卷 TRACKER、解读和审查答复用简体中文；脚本机读前缀与 JSON 字段名保持稳定。
- **专利类型**：未显式指定时交底**默认发明**。
- **脚本路径**：相对本技能仓库根（本文件所在目录）。整仓：`python skills/patent-disclosure/tools/…`。当前工作区不是本仓库时，把技能安装目录接到命令前面。单独拷走某一子包时，该包内用 `python tools/…`。路径只写仓库相对路径。
- **用户产出**：只写当前工作区 `outputs/`（解读 `outputs/patent_reader/`，检索 `outputs/patent-search/`，对照表 `outputs/patent-chart/`，政策 `outputs/exam-policy/`，审查答复 `outputs/oa/`，申请文件 `outputs/patent-application/`，案卷 `outputs/docket/`，交底围栏 `outputs/{案件}/fence/`）。调用脚本时 cwd 用工作区根；`-o` / `-w` 用上述相对路径。

## 执行前核对

```
□ 已 Read 对应 skills/*/SKILL.md，未把本文件当成交底或申请正文
□ 去向以「路由判定表」为准；须点名的包，用户没点名就停
□ 脚本只用当前子技能自己的 tools/（见「通则」）
□ 交付回复末块标题为「交付后请确认」
```
