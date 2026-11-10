# 申请文件工具

| 脚本 | 前缀 | 退出码 |
|------|------|--------|
| `material_gate.py` | `APPLICATION_GATE:` | 0 齐全；2 缺材料；1 用法错误 |
| `audit_claims.py` | `APPLICATION_CLAIMS:` | 0 无 ERROR；1 有 ERROR |
| `plan_figures.py` | `APPLICATION_FIG_PLAN:` | 0 无 ERROR；1 有 ERROR |
| `check_numeral_register.py` | `APPLICATION_NUMERALS:` | 0 无 ERROR；1 有 ERROR |
| `render_invention_figures.py` | `APPLICATION_FIG:` | 0 已出 SVG；PNG 失败不单独当致命（看 png_fail）；`--only N` 只出个别图（生图回退用） |
| `figure_backend.py` / `figure_jobs.py` / `image_api.py` / `image_runtime.py` / `bw_normalize.py` | `FIGURE_BACKEND:` / `FIGURE_JOB:` / `IMAGE_API:` / `IMAGE_RUNTIME:` / `BW_NORMALIZE:` | 出图后端（见 `prompts/figure_generation.md`）；`figure_jobs.py status` 有 pending / blocked 退出码 2 |
| `check_support.py` | `APPLICATION_SUPPORT:` | 0 无 ERROR；1 有 ERROR |
| `compose_application_figure.py` | `APPLICATION_FIG:` | 0 已出 SVG（PNG 看 png=）；**仅实用新型 / 发明点名图**；外观禁用 |
| `iteration_dialog_log.py` | `LOG_FILE=` | 0 已追加 |
| `check_design_views.py` | `VIEW_CHECK:` | 0 已写清单（不合格不挡交付） |
| `emit_application_docx.py` | `DOCX:` / `APPLICATION_DOCX:` / `LATEX_DELIM:` | 0 全部写出；某文件行内公式写成普通括号则该文件 `DOCX: ok=0 reason=latex_delim`，总退出码 1 |

```bash
python skills/patent-application/tools/material_gate.py --case-dir outputs/{案件}
python skills/patent-application/tools/render_invention_figures.py \
  --plan outputs/patent-application/{案}/figures/invention_figures.yaml \
  --out-dir outputs/patent-application/{案}/figures
python skills/patent-application/tools/audit_claims.py outputs/patent-application/{案}/权利要求书.md
python skills/patent-application/tools/plan_figures.py \
  --claims outputs/patent-application/{案}/权利要求书.md \
  --out outputs/patent-application/{案}/figures/figure_plan.yaml
python skills/patent-application/tools/check_support.py --dir outputs/patent-application/{案}
python skills/patent-application/tools/compose_application_figure.py \
  --source <线稿或场景图> --fig 3 --out-dir outputs/patent-application/{案}/figures
python skills/patent-application/tools/check_design_views.py \
  --case-dir outputs/{案件} \
  --out outputs/patent-application/{案}/视图检查清单.md
python skills/patent-application/tools/emit_application_docx.py --dir outputs/patent-application/{案}
```

宣传语词库：`references/promo_terms.yaml`（`lexicon.py` 加载；权要与摘要共用）。增删词条不必改脚本。  
`check_design_views.py` 与 `references/design_view_cnipa.md` 是交底包副本，禁止只改一边。出图后端各脚本、`image_providers/`、`references/figure_prompt_templates.yaml`、`prompts/figure_generation.md` 同样是交底包副本。测试 `tests/test_design_view_sync.py` 会比对。
