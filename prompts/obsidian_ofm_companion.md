# Obsidian Flavored Markdown 伴生规范（专利解读写笔记时 Read）

> 与 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 的 `obsidian-markdown` 对齐子集。若环境已安装该技能，写笔记前可额外 **`Read`** 其 `SKILL.md`；**未安装时**以本文件为准即可。

## 写笔记前

与 `assets/patent_note_template.md`、`references/patent_obsidian_format.md` 一并使用。

## 必用 Callout 类型

| 语法 | 位置 |
|------|------|
| `> [!patent-meta] 著录项` | `#` 标题下、导航后 |
| `> [!patent-claim] 权利要求 N` | 第四节各独立权前（可选包裹引用块） |
| `> [!grounding] 应用场景` | 第九节全文 |
| `> [!warning]- 公开检索线索` | 第十节 B（`-` 默认折叠） |
| `> [!figure] 图 N …` | 第六节附图占位（无图时） |

## Frontmatter

必须含：`cssclasses: [patent-reader]`、`ipc`、`evidence_scope`、`confidence_speculative`（有附录 B 中/低置信线索时为 `true`）。

标签：

- `patents/<领域>`
- `patent/evidence/full` | `abstract` | `partial`
- `patent/speculative`（有推测附录时）

## 权利要求树

入库脚本用 `claim_tree.json` 生成第三节：**一张树形表**（`◆/├─/└─` + 权号 + 本项新增）。  
结构与内容合一，避免 mermaid 与表各讲一遍。`claim_mermaid.mmd` 可留作可选，默认不进正文。

## 嵌套与折叠

- 推测内容**仅**放在 `[!warning]-` 内
- 冗长从属权枝可用 `[!note]-` 折叠

## Canvas

入库后笔记导航须链到 `{{公开号}}_图谱.canvas`。

## 说明书段落引用

- 写 `说明书 0002` / `说明书 0002–0004`，勿写裸 `[0002]`
- 入库改成块锚单链：`#^p0002` / `#^r0002-0004`；**悬停预览**依赖核心插件「页面预览」（设置 → 核心插件 → 页面预览）

## 禁止

- HTML 块替代 callout（可移植性差）
- 在第九节写 URL
- 依赖仅社区插件才有的语法（Dataview 只写在索引页，不写解读正文）
- **用户可见标题**加说明性括号（如「若能从原文读出」「故事线」「专利内依据」「可选 mermaid」）；写作约束写在 prompt，不写进交付标题
- 交付正文出现脚本名（`*.py`）、流水线字段（`context_anchor.*`）、内部附图文件名（`page_*_xref_*`）
