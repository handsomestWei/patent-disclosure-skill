# 申请文件 · 录入

执行前 **`Read`** `prompts/guardrails.md`。

## 触发

申请文件、申请底稿、申报材料、权利要求书、说明书五部分、把交底改成申请、`/申请底稿`、`/patent-apply`。

已有申请四件套上改独权、附图、说明书、点名补图：走 `iteration_context.md`，不要从门禁空写。

## 发明母案与分案

用户点名规划、撰写或核验发明分案时，先 **`Read`** `divisional.md`。规划或核验可先依据已有材料交付范围表和缺口清单。已有申请上改稿时先定位上一版目录，再复核本轮涉及的分案内容。下方门禁用于继续写四件套。

## 场景补充

未命中则跳过，不要当主流程。

| 场景 | 何时读 | 读什么 |
|------|--------|--------|
| AI 实施细节 | 用户点名 AI 实施细节、模型输入输出或训练步骤；或发明分案且交底是模型或智能体参与的技术方案 | `references/ai_implementation.md` |

## 交底路径（强制）

必须给出交底产出目录（常见 `outputs/{案件标识}/`）。给的是文件则取其父目录。无路径则只问一次，仍没有则终止。迭代时可沿用上一版 `application_plan.yaml` 的 `case_dir`。

不要把仓库 `examples/*/knowledge/` 当成交底产出。

## 下一步

1. **`Read`** `material_gate.md`，运行 `tools/material_gate.py --case-dir <目录>`
2. `ok=0` → 终止并引导交底技能
3. `ok=1` 后：`invention` / `utility_model` → `claim_strategy.md`；`design` → `design_application.md`
