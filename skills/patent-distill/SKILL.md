---
name: patent-distill
description: "专利蒸馏：把多份申请合并成一份文风；按案件从交底与权要的对照抽出权要选择思路。"
user-invocable: false
---

# 专利蒸馏

## 用途

申请文件合并成一份文风。每个案件单独一份策略观察和 `playbook.yaml`。文风只学怎么写。思路只学这一案怎么切保护点。

## 何时用

专利蒸馏、蒸文风、蒸思路、`/专利蒸馏`、`/patent-distill`。

## 输入

工作区内的交底书、申请文件或公开全文。脚本判断文书角色和专利类型。申请文件合并文风；思路按案件拆开。只有公开号、没有文件则停。金奖示例与下载入口见 `examples/README.md`，使用前先把全文下载到本地。

## 步骤

1. **`Read`** `prompts/guardrails.md` → `prompts/intake.md`
2. `tools/classify_distill.py` 读入文件并建档。退出码 3 时只补问 `DISTILL_ASK` 那一项，带上回答重跑
3. 有 `DISTILL_STYLE` 则 **`Read`** `prompts/style_distill.md`，写批次根目录的 `style.md`、`sections/application.md`、`samples.md`
4. 每一行 `DISTILL_CASE` **`Read`** `prompts/strategy_distill.md`，只写该案的 `策略观察.md` 与 `playbook.yaml`
5. `tools/validate_distill.py --dir <批次目录>`，见到 `DISTILL_OK` 再交付
6. 对话末块按 `prompts/delivery_confirm.md`。文风样本超过 4 份时，只在这段总结里提示参考上限，输入阶段照常全部合并

```bash
python skills/patent-distill/tools/classify_distill.py 交底.md 申请.md
python skills/patent-distill/tools/validate_distill.py --dir outputs/patent-distill/<档案id>
```

枚举以 `references/contract.yaml` 为准。机读前缀：`DISTILL_ROLE:` / `DISTILL_TYPE:` / `DISTILL_TRACKS:` / `DISTILL_ASK:` / `DISTILL_DIR:` / `DISTILL_PROFILE:` / `DISTILL_OK:` / `DISTILL_ERROR:`。

## 护栏

- 细则 `prompts/guardrails.md`。脚本只用本包 `tools/`。
- 不代下载全文。`playbook.yaml` 不抄样本事实。观察档保持 `draft`。

## 产出物

`outputs/patent-distill/{批次}/`：`batch.yaml`；有申请文件时根目录是合并文风。`cases/{案件}/` 各有一份思路档案。对话末块标题 **交付后请确认**。
