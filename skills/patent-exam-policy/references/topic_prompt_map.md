# 观点主题 → 交底包文件（技能进化旁路用）

写 E* 或「对交底写法的影响」时**先查交底表**，不要凭记忆现编路径。  
写「对申请文件写法的影响」时查**申请表**。路径均相对仓库根。  
解读 / 检索 / 审查答复、以及申请侧的请求书 / 费减 / 客户端包，不在两表内：只进简报「另议」。  
**申请表只供简报说明，不进技能进化白名单**（默认不改 `skills/patent-application/`）。

## 交底（可进 E*）

| 主题 | 交底文件 |
|------|----------|
| 充分公开、可实施、实施例粒度 | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`invention/template_reference.md`、`disclosure_self_check.md` |
| 创造性叙事、与现有技术的差异化 | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`utility_model/patent_points.md`、`prior_art_search.md` |
| AI / 算法 / 大数据申请客体、智力活动规则 | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`invention/template_reference.md` |
| 伦理、五条一款、违法采集 / 歧视决策 | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`disclosure_self_check.md` |
| 查新口径、现有技术表述（交底 Step 5） | `skills/patent-disclosure/prompts/prior_art_search.md`（**不要**改 `skills/patent-search/`） |
| 实用新型保护点、实用新型明显创造性 | `skills/patent-disclosure/prompts/utility_model/patent_points.md`、`utility_model/disclosure_builder.md` |
| 外观设计要点、视图、明显区别 | `skills/patent-disclosure/prompts/design/patent_points.md`、`design/disclosure_builder.md`、`fill_appearance_schema.md` |
| 局部外观与GUI、图形用户界面 | `skills/patent-disclosure/prompts/design/patent_points.md`、`design/disclosure_builder.md`、`fill_appearance_schema.md`、`design_lineart_assist.md` |
| 相似外观、成套/合案 | `skills/patent-disclosure/prompts/design/patent_points.md`、`design/disclosure_builder.md` |
| 专利法与实施细则（书式、期限、客体） | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`utility_model/disclosure_builder.md`、`design/disclosure_builder.md`、`disclosure_self_check.md` |
| 附图、件号、figure_plan、线稿 | `skills/patent-disclosure/prompts/image_gen.md`、`figure_generation.md`、`fill_structure_schema.md`、`fill_appearance_schema.md`、`structure_lineart_assist.md`、`design_lineart_assist.md`、`references/schemas/figure_plan.schema.yaml` |
| 降低套话、书式与代理人可读 | `skills/patent-disclosure/prompts/invention/disclosure_builder.md`、`skills/patent-disclosure/prompts/disclosure_preview.md` |
| 迭代合并 / 纠正与另存 | `skills/patent-disclosure/prompts/merger.md`、`correction_handler.md`、`iteration_context.md` |
| 交底包入口、类型默认 | `skills/patent-disclosure/SKILL.md`、`prompts/intake.md` |

一题可对应多文件；E* 只列**准备改的那几份**，勿整目录扫射。  
交底表无对应行则影响面标 `仅背景`，不要硬编 E*。

## 申请文件（仅简报说明）

| 主题 | 申请文件（仅说明） |
|------|-------------------|
| 权要书式、独权/从属、「所述」前置 | `skills/patent-application/prompts/claims_builder.md`、`claim_strategy.md` |
| 说明书充分公开、实施例与权要对照 | `skills/patent-application/prompts/specification_builder.md`、`consistency.md` |
| 摘要字数、宣传语 | `skills/patent-application/prompts/guardrails.md`、`specification_builder.md` |
| 发明/实用新型附图、黑白线框 | `skills/patent-application/prompts/figures.md` |
| 外观视图、图幅、图照片不混 | `skills/patent-application/prompts/design_application.md`、`references/design_view_cnipa.md`、`prompts/issues.md` |
| AI / 算法申请客体（权要表述） | `skills/patent-application/prompts/claim_strategy.md`、`claims_builder.md` |
| 实用新型明显创造性（权要口径） | `skills/patent-application/prompts/claim_strategy.md` |
| 降低套话、申请书式可读 | `skills/patent-application/prompts/guardrails.md`、`specification_builder.md` |

申请表无对应行、又不是权要/说明书/摘要/附图书式：进「另议」，影响面填 `申请`。
