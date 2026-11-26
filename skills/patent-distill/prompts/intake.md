# 专利蒸馏 · 录入

执行前已读 `guardrails.md`。先跑分类，再写正文。不要先问蒸文风还是蒸思路，也不要先问专利类型。

## 触发

专利蒸馏、蒸文风、蒸思路、`/专利蒸馏`、`/patent-distill`。

## 自动判断

用户给出工作区内的文件后运行：

```bash
python skills/patent-distill/tools/classify_distill.py 文件1 文件2
```

脚本读取正文（Markdown、txt、docx；PDF 需本机有 `pypdf`）和文件名，写入 `profile.yaml` 的 `inputs`、`evidence`、`tracks`、`strategy.strength`。

| 判断 | 规则 |
|------|------|
| 交底 | 技术交底书、欲保护点、现有技术缺点 |
| 申请文件 | 权利要求书、其特征在于、技术领域 |
| 公开文本 | 国家知识产权局著录、申请公布号或授权公告号、公开号种类码。公布为 `publication_a`，授权为 `publication_b` |
| 专利类型 | 公开号末位字母优先，其次外观设计 / 实用新型 / 本发明 |
| 文风 | 申请文件，同一专利类型合并成批次根目录的一份 |
| 思路 | 每个案件一份，写在 `cases/{案件}/`。一份申请是一案；仅有一份交底和一份申请时，交底并入该案。公开文本按公开号并案 |

申请文件合并文风。思路按案件拆开。

判不出文书、判不出类型，或同一批材料分属两种专利类型时，也是退出码 3。只问 `DISTILL_ASK` 里的那一项，不要把已经判出的类型再问一遍。类型冲突就拆成两个档案。

只有公开号、没有文件：不要跑脚本，请用户提供文件。

行业仍只作建议。用户确认后才填 `industry` 与 `industry_confirmed: true`。

## 下一步

有 `DISTILL_STYLE` 就读 `style_distill.md`，写批次根目录的文风。每一行 `DISTILL_CASE` 读 `strategy_distill.md`，只写该案目录。脚本写好的 `role`、`patent_type`、`tracks`、`strength` 保持原样，用户改口后再改。
