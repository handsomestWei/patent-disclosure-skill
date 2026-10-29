# 申请文件 · 件号 / 模块标记核对

实用新型：`id` 与 `structure_schema.parts` 同一套。  
发明系统框图与系统权要均不使用（10）（20）件号：`parts` 可空，只登记 `figures`（图 1 框图、图 2 流程）。  
发明流程图步骤（步骤1…或特征句）不要登记成 parts。

```bash
python skills/patent-application/tools/check_numeral_register.py \
  --register <产出>/件号登记表.yaml \
  --claims <产出>/权利要求书.md \
  --spec <产出>/说明书.md
```

实用新型再加 `--schema` 与 `--figure-plan`。发明无结构 schema 则不要传 `--schema`。点名场景图登记在 `figures`，`kind: source_image`，`disclosure_only: false`。

交付前再跑：

```bash
python skills/patent-application/tools/check_support.py --dir <产出> --case-dir <交底目录>
```

`APPLICATION_NUMERALS: ok=0` 先改表或正文。`check_support` 会并入串号 / 未登记号 / 同名不同号，并写出 `标号核对.md`。警告进问题清单。
