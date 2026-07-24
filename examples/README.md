# 示例案件目录

本目录提供**可随仓库提交的演练材料**。

| 路径 | 说明 |
|------|------|
| `example_batch_job_scheduler/` | 虚构场景「分布式批任务调度与资源感知」；**仅含 `knowledge/` 原材料**，用于交底书主流程 Step 2 扫描演练 |
| `example_patent_reader/` | **专利通俗解读**示例：仓库只保留 [README.md](example_patent_reader/README.md) 中的 **CDN 镜像下载链接**；PDF 等材料本地自备（已 gitignore） |

冒烟用极简 TXT 见 `tests/fixtures/patent_reader_sample.txt`。

## 如何使用 `example_patent_reader`（阅读模式）

按 [example_patent_reader/README.md](example_patent_reader/README.md) 下载镜像 PDF 到 `source/` 后，再以本地路径触发解读；主示例 `CN119961390A`，另备 `CN119961396A` 可用于关联 / 同域对照测试。

## 如何使用 `example_batch_job_scheduler` 跑出效果

全流程产物（`patent_points.md`、`prior_art_notes.md`、`disclosure_preview.md`、带时间戳的交底书 `.md`/`.docx` 等）由技能在 **`outputs/{案件标识}/`** 生成；命名与版本规则见 **`disclosure_builder.md` §7.3**、**`iteration_context.md`**。

### 方式 A：只看原材料（不跑 Agent）

打开 `example_batch_job_scheduler/knowledge/`，阅读 `docs/README.md`、`docs/architecture.md`、`pkg/scheduler/*.go` 等，理解**扫描输入长什么样**。

### 方式 B：在 Agent 里全流程演练（推荐）

前提：已在 Cursor / Claude Code 等环境中加载本仓库技能（见仓库根目录 [INSTALL.md](../INSTALL.md)）。技能入口与步骤见 [SKILL.md](../SKILL.md)。

1. **指定「项目」路径**

   `examples/example_batch_job_scheduler/knowledge/`

2. **用自然语言触发技能并写明边界**（可复制改写后发给 Agent）：

   ```text
   请按 patent-disclosure-skill 全流程执行：
   - 项目扫描目录：examples/example_batch_job_scheduler/knowledge/
   - 技术主题：分布式批任务调度、异构集群、资源感知与限频重排队（可参考 knowledge 内文档与代码）
   ```

3. **查新说明（重要）**

   查新细则见 `prompts/prior_art_search.md`。演练时著录项可为练习占位，结构须符合该 prompt。

4. **验收「效果」**

   - 打开你指定的输出目录（如 `outputs/某练习目录/`，整目录不提交 Git），检查是否生成专利点、查新笔记、摘要预览、交底书（**Markdown + Word**，文件名含 **案件名 + 时间戳**）。
   - 定稿须经 `tools/mermaid_render.py`（需 Node.js、`tools` 下可选 `npm install`，以及 `pip install -r requirements.txt`）。Word 失败时按脚本 stderr 手动执行 `md_to_docx.py`。详见 `tools/README.md`。

5. **版本与迭代**

   交付与迭代命名见 **`disclosure_builder.md` §7.3 第 5 点**；修订对话记录见 **`iteration_context.md`**。可选另存 `versions/` 非强制。

6. **迭代模式（按意图，无需固定关键词）**

   与 [SKILL.md](../SKILL.md) 一致：只要用户明显是在**已有交底书**上**补充材料**或**纠错/改表述**，Agent 即应 **`Read`** `prompts/iteration_context.md` 与 `prompts/merger.md` 或 `prompts/correction_handler.md`。

   示例话术：

   ```text
   在现有交底书 outputs/.../一种XXX_时间戳.md 上：
   - 合并附录里的新实施例（偏 merger）；或修正 3.5 与正文公式不一致（偏 correction_handler）
   ```