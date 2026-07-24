# 专利解读内部自检（不写入交付笔记）

## 核对清单

- [ ] **L0 Callout**：`[!patent-meta]`、`[!grounding]`、`[!warning]-` 齐全
- [ ] **Frontmatter**：`cssclasses: patent-reader`、`ipc`、`confidence_speculative` 正确
- [ ] **权利要求树**：`claim_tree.json` 已经 Agent 校对（`review.by=agent`，父号/独立权正确，含「权1或2」类多引用）；单一树形表；「本项新增」来自 `claim_deltas.json`；勿 mermaid+表双份主展示
- [ ] **第九节无 URL**；推测仅在 `[!warning]` 内
- [ ] **附图闸门**：`insert` 图已嵌入；`placeholder` 仅 callout
- [ ] **术语网**：Canvas 术语为 file 节点或已建 stub；第五节有 wikilink
- [ ] **入库**：`write_status.json` 含 canvas / figures_inserted；索引含 Bases 嵌入
- [ ] **无实现痕迹**：正文无 `*.py`、无 `context_anchor.*`、附图说明无 `page_*_xref_*.png`
- [ ] **公开线索 L1–L4**：导航入口；一/二/七/八/九旁注；权/特征点对点；附录 B + `clues/` + Canvas；全文标「推测」、未污染说明书依据列；Agent 已写 `summary`（或明确 `fetch_failed`）
- [ ] **交付**：已向用户出示插件引导（对话末尾，勿写入解读正文）

## 发现问题的处理

改笔记后重跑 lint → 入库。
