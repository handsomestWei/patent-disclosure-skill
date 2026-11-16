# 派工交底

适用 `phase`：`bootstrap_disclosure`、`dispatch_disclosure`、`wait_disclosure`、`wait_disclosure_fix`。

先 **`Read` `references/handoff_contract.md`**。

## 读哪个交底入口

**只 `Read` `skills/patent-disclosure/SKILL.md`**，然后完全按该包步骤执行（初稿 Step 1–8，或迭代 `iteration_context.md` → `merger.md` / `correction_handler.md`）。

| 本包 phase | 交底侧 |
|------------|--------|
| `bootstrap_disclosure` | 全流程初稿（intake 起） |
| `dispatch_disclosure` / `wait_disclosure_fix` | 迭代纠正或合并；**禁止**无必要重跑专利点分析 |

把本轮 `issues` 里 `disposition: disclosure_fix` 且 `open` 的 **id 列表**交给交底手，并写明：只补清单指出的事实缺口；材料没有的标未决，不要编。

## 协调者在交底执行期间

不另写交底正文。交底包交付后：

1. 记录新时间戳 md/docx 到 `paths.disclosure_dir`、`paths.disclosure_md`
2. `phase`: 初稿为 `wait_disclosure` → 随即 `bootstrap_application`；纠正为 `wait_disclosure_fix` → 必须 `dispatch_application`
3. 校验 + emit tracker
4. **`Read` `prompts/dispatch_application.md`**（纠正后不可 round_close）

出图后端与样图确认（`figure_generation.md` 第 1–2 节）属于该问的问题：并入当轮 `ask_human`，确认后本案固定，后续轮次不再问。

材料门禁失败（缺 schema/线稿）：写 `ask_human` 或保持交底包终止说明，案卷 `terminal_blocked` 或 `ask_human`，不要改去申请包硬写。
