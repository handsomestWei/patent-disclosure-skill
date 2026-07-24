# 专利通俗解读 · 示例 PDF（镜像下载）

本目录材料**不入库**，请自行下载到 `source/` 后做解读 / 关联测试。

> **说明**：下列示例专利**仅用于本技能的功能测试与效果演示**，不代表技术优劣、权利状态或商业立场，亦不构成任何推荐或评价。

## 下载方式（推荐）

通用入口（技能已固化，勿另写脚本）：

```bash
python tools/patent_reader/fetch_patent_pdf.py --pub CN119961396A -o examples/example_patent_reader
# → examples/example_patent_reader/source/CN119961396A.pdf
```

源优先级与备选说明：`references/patent_pdf_sources.yaml`。

## Google Patents CDN（已知镜像直链 · 与 yaml 同步）

| 公开号 | 用途 | PDF 镜像 |
|--------|------|----------|
| `CN119961390A` | 主示例（政法领域语言大模型问答；软件/RAG 类解读） | https://patentimages.storage.googleapis.com/58/1b/9b/07a9f35635df34/CN119961390A.pdf |
| `CN119961396A` | 近似专利（税务 AI 智能体；关联测试 / 同域对照） | https://patentimages.storage.googleapis.com/3f/29/d0/a2461c5080d73d/CN119961396A.pdf |
| `CN114552122A` | **按图裁切解读**：文字层附图页含可选中「图1」「图2」，适合 caption+bbox 裁切后写入 Obsidian | https://patentimages.storage.googleapis.com/c2/6c/51/75412585086edf/CN114552122A.pdf |

建议本地文件名：

- `source/CN119961390A.pdf`
- `source/CN119961396A.pdf`
- `source/CN114552122A.pdf`

### 按图裁切（CN114552122A）

提供该 PDF 做通俗解读时，技能会按 `patent_plain_reader.md` **自动**跑附图抽取：有可选中图注则按图号裁切写入「特征—附图对照」；扫描件则回退整页预览。无需手动执行抽取脚本。
