"""公开检索线索实现（对外统一从 vault.clue_vault 导入）。

- vocab：读取 references/clue_vocab.yaml
- model：线索数据、筛选、文件名与链接
- summary：摘要清洗与降级抓取
- matching：线索 ↔ 权项 / 特征 / 术语弱匹配
- annotate：解读笔记各节旁注注入
- render：clues/ 笔记、索引、附录 B、Canvas 数据
"""
