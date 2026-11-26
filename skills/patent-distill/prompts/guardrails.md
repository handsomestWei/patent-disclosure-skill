# 专利蒸馏 · 护栏

先读本文件，再读 `intake.md`。

## 范围

- 只写工作区 `outputs/patent-distill/{档案id}/`。
- 不下载公开专利。用户只给公开号、没有本地全文时，停下，请用户提供 PDF、Markdown 或 Word 路径。

## 材料

三类由 `classify_distill.py` 写入 `profile.yaml` 的 `inputs[].role`，不要先让用户选：

| 用户手里的文件 | role | 说明 |
|----------------|------|------|
| 交底书 | `disclosure` | 归入同案思路，用来对照后来的权要 |
| 申请文件（权要、说明书、摘要、附图底稿或递交稿） | `application` | 文风样本。同一专利类型的多份申请合并成一份文风。口语里的「申请书」若是请求书表格，改收四件套正文 |
| 公开单行本 | `publication`；发明公布用 `publication_a`，授权用 `publication_b` | 按公开号并成一个案件的思路。一份 PDF 是一份文本 |

申请文件合并文风。思路按案件分目录，一案一份 `playbook.yaml`。`strength` 为 `observe` 的思路档保持 `draft`。

## 两种产物不要混

- 文风：句子节奏、章节口气、忌语。不写样本里的结构、参数、权要原文。
- 思路：点清单、权要选择、披露未请求保护的点。机器读 `playbook.yaml`，人读 `策略观察.md`。
- `playbook.yaml` 只写可复用切法，禁止样本权要原文、数值、件号、产品名、推测结论。

## 事实与推测

观察必须能指回材料里的位置（交底章节、权项号、说明书段落）。看不出「为什么不申请」就写入 `策略观察.md` 的「推测」，不要写进 `playbook.yaml`。

没有同族或周边案时 `layout.enabled: false`。没有授权文本时，时间轴不要写审查意见。

## 收口

填完跑：

```bash
python skills/patent-distill/tools/validate_distill.py --dir outputs/patent-distill/{档案id}
```

`DISTILL_OK` 之前不要交付。对话末块用 `delivery_confirm.md`。
