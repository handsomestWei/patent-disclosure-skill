# 专利附图出图（生图后端 · 公共方法）

交底与申请文件**所有绘制类附图**都按本文出图：交底 3.2 系统框图 / 3.4 流程图、实用新型结构线稿（含单件与件号引出）、外观视图线稿、申请发明附图（框图 / 流程图）。出第一张图前 **`Read` 本文**。

不在本文范围（不是"绘制"，照旧）：CAD/STEP 投影、解读包 PDF 抽图、专利地图、公式 PNG、外观申请的原样复制、点名源图 `source_image`。

下文 `tools/` 指**当前子技能自己的** `tools/`（整仓为 `skills/patent-disclosure/tools/` 或 `skills/patent-application/tools/`）。本文件在两包同文，改一处须同步另一处（`patent-application/tests/test_design_view_sync.py` 会比对）。

## 一句话

先定后端 → 出一张样图给用户看 → 一图一 job 批量出图 → 逐图读图 QA → 局部问题 edit 修 → `figure_jobs.py record` 登记。生图失败或两轮修不好，**回退上游本地渲染**，交付不中断，并在「交付后请确认」里点名哪几张是降级图。

## 1. 后端（出第一张图前定，本案固定）

| 后端 | 是什么 | 何时用 |
|------|--------|--------|
| `builtin` | 宿主内置生图 / 改图工具（例如 Codex `image_gen`、OpenClaw `image_generate`） | **优先**。能调用就用 |
| `cli` | `tools/image_api.py`（GPT Image，默认 `gpt-image-2.5-flare`） | 宿主没有内置工具、内置工具缺本图必需能力（如必须带参考图改图），或用户点名 API |
| `local` | 上游原有本地渲染：`mermaid_render.py`、`render_invention_figures.py`、`structure_callout_overlay.py` | 前两者都不可用，或用户 / `PATENT_SKILL_FIGURE_BACKEND=local` 指定 |

```bash
python tools/figure_backend.py --case-dir outputs/{案件}
```

- 看 JSON：`backend` 非空说明本案已确认，直接用，**不要再问**。`ask_user: true` 才走下面的确认。
- **先自查**宿主有没有可调用的内置生图工具（看工具列表，不要凭"我在某个 Agent 里"推断）。脚本查不到宿主工具，只报 `cli_ready`。
- 对用户说清：查了什么、准备用哪个后端、为什么需要或不需要 CLI。示例：

  > 我检查到当前环境可调用内置生图工具，准备用它出专利附图，不走本地 API。生图失败的图会回退本地渲染并在交付时标出。可以先出 1 张样图吗？

  > 我检查后没有可用的内置生图工具，准备用本技能的 CLI 出图后端（读 `~/.patent-skill/.env`）。可以先出 1 张样图吗？

- 用户确认后：`python tools/figure_backend.py --case-dir outputs/{案件} --set builtin|cli|local --confirmed`。之后**不得**为方便中途换后端。
- `cli` 报 `deps_missing`：征得同意后 `python -m pip install -r tools/requirements-image.txt`。报 `api_key_unset` 或调用返回鉴权 / 模型错误时，才请用户给 key，并用 `python tools/image_runtime.py config --api-key "…" [--base-url …] [--model …]` 写入。配置只在本技能目录，不读其它技能的配置。自检：`python tools/image_runtime.py doctor --check-api`。
- 用户拒绝生图或两种后端都不可用：`--set local --confirmed`，后续一律按上游原流程，本文第 2–6 节跳过。
- 案卷包调度时，后端与样图确认属于"该问的问题"，并入当轮提问，不另起一轮。

## 2. 样图门

后端确认后先出**一张**代表图：

- 发明交底：3.2 系统框图
- 实用新型：主视图结构线稿（轮廓层）
- 外观：主视图线稿
- 申请发明附图：主流程图（摘要附图）

给用户看，确认后再批量出图。确认后记录：

```bash
python tools/figure_backend.py --case-dir outputs/{案件} --sample <样图路径> --sample-fig <fig_id> --accept
```

同一案件迭代时样图已 accepted 的，不再重复样图门。

## 3. 建 job（一图一 job）

```bash
# 交底 mermaid（先写好含 mermaid 围栏的草稿 md）
python tools/figure_jobs.py prepare --case-dir outputs/{案件} --from-md "outputs/{案件}/草稿.md"
# 线稿门禁写出的 jobs（design / structure / 单件 compose）；结构线稿另建件号引出 job
python tools/figure_jobs.py prepare --case-dir outputs/{案件} --from-lineart-jobs outputs/{案件}/lineart_assist/structure_lineart_jobs.json --with-callouts
# 申请发明附图
python tools/figure_jobs.py prepare --case-dir <申请产出> --from-invention-yaml <申请产出>/figures/invention_figures.yaml
```

- 每个 job 写在 `{case}/figure_jobs/{fig_id}.json`，字段包括 `prompt`、`text_verbatim`（图内须逐字出现的文字）、`input_images`（参考图及角色）、`size`、`quality`、`out` 和 `fallback`。
- prompt 由 `references/figure_prompt_templates.yaml` 拼出（黑白、白底、无图号无视图名、只画清单内的件等），**不要**在对话里另写一套口径。
- 迭代时重跑 `prepare`：来源没变（sha1 相同）且已登记的图保留，不重出；改过的块重置为 `pending`。

## 4. 出图

**builtin**：
- 把 job 的 `prompt` 原样交给内置工具，`size` 能设就设。
- 有 `input_images` 时，先让每张参考图进入对话上下文（本地图先用看图工具打开），prompt 里按角色标注，例如「图 1：产品参考，保持比例与开口」。
- 宿主内置工具的落盘路径不固定，登记时用 `--image` 传入。

**cli**：

```bash
python tools/image_api.py job --job outputs/{案件}/figure_jobs/{fig_id}.json
```

- 有 `input_images` 时自动走 edit（真正的图生图）；没有就走 generate。
- 出图慢、要并发时可分派子 Agent，一张图一个，但**登记只由主流程做**。
- `image_gen.md` 的 `describe_then_txt2img` 只在 edit 也不可用时使用。

**件号引出 job**（`callout_*`）依赖对应轮廓图：轮廓图登记后再出。

## 5. 逐图 QA（Read 生成图，逐项过）

- **文字**：`text_verbatim` 逐字核对，中文错字、漏字、多字都算不过。步骤号、判断分支文字一并核对。
- **结构**：
  - 流程图框数与独权（或交底步骤）一致，顺序一致。
  - 框图模块、分组、箭头与来源一致，不多不少。
- **黑白**：
  - 白底纯黑线，无彩色、无灰阶填充、无阴影。
  - 图内无图号、图题、视图名、水印。
  - 申请附图登记后看 `post_result.color_ratio` / `gray_ratio`，明显大于 0 时重出，不要硬转。
- **实用新型件号**：
  - 只用 `structure_schema.parts` 里的号，每号一次。
  - 引出线末端落在**该名称**的件的墨线上（易混对：腔体↔腔内件、轴↔转子）。
  - 轮廓与轮廓层原图一致，**改了轮廓即不过**。
- **外观**：按 `references/design_view_cnipa.md` 核对：正投影或立体图角色正确、各视比例一致、无尺寸线、中心线、阴影线。

**修复**：
- 局部问题（个别错字、一条箭头、一个件号）：用后端的 edit 改图（cli 为 `image_api.py edit --image <图> --prompt "只改……其余不变" --out <新图>`），**最多两轮**。
- 整体不对：收紧 prompt 重出。
- 仍不过：

```bash
python tools/figure_jobs.py block --case-dir outputs/{案件} --fig {fig_id} --reason "……"
```

然后按 job 的 `fallback` 回退本地渲染，渲染完：

```bash
python tools/figure_jobs.py fallback --case-dir outputs/{案件} --fig {fig_id} --reason "已用 xxx 本地渲染"
```

## 6. 登记与入文

QA 通过：

```bash
python tools/figure_jobs.py record --case-dir outputs/{案件} --fig {fig_id} [--image <内置工具生成图>] --qa-note "文字逐字核对通过"
```

- 申请发明附图在登记时自动转真黑白、按内容裁切，写出 `figures/图N.png`、`图N.svg`，abstract 另写 `摘要附图.png`。
- 交底定稿：照旧用 `mermaid_render.py`，**加** `--ai-figures outputs/{案件}/figure_jobs.json`。sha1 命中的块直接用生成图；未登记或已过期的块本地渲染，`MERMAID: ai_figure_miss` 会报数。mermaid 围栏在 md 里照旧保留，作为结构规格与回退源。
- 线稿 job 的 `out` 就是门禁 job 的 `output_path`，登记后按原流程写回 `figure_plan`。

交付前：

```bash
python tools/figure_jobs.py status --case-dir outputs/{案件}
```

- 退出码 2（有 `pending` / `blocked`）时**不得**称附图完成。
- `fallback_local` 列表写进「交付后请确认」，例如「图 2 流程图生图两轮文字仍有错，已回退本地渲染」。
- 只在对话里说"已出图"不算完成，以 `figure_jobs.json` 为准。

## 护栏

- 不承诺生成图"已符合国知局正式附图规范"。附图仍须人工复核。
- 生图不得引入来源里没有的模块、步骤、部件或外形特征；不确定的进 `uncertain`，不画、不写进权要。
- 不在图里写图号；图号只在正文与附图说明。
- 用户给的 key 只写进 `image_runtime.py config`，不写进案件目录、交底或对话摘要。
