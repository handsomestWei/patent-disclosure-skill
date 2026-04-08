# docs / 设计说明与示例 Office 附件

## Markdown

| 文件 | 说明 |
|------|------|
| `architecture.md` | 批任务调度架构文字说明（与交底书一致） |

## 示例 Word / PPT（含嵌入图）

用于演练 **`tools/docx_to_md.py`**、**`tools/pptx_to_md.py`** 或外部 MiniMax Office 技能；与 `architecture.md` 口径一致，均为虚构示例。

**Step 2 扫描约定**（见 `prompts/project_scan.md`）：Agent **须**先将下表 `.docx`/`.pptx` **转为 `.md` 再 Read**，不可只扫 `architecture.md` 而忽略 Office；**勿**对 `sample_assets/*.png` 单独做识图（与内嵌图重复，以转换后的 Markdown 为准）。

| 文件 | 说明 |
|------|------|
| `sample_architecture_review.docx` | 虚构纪要 Word，内嵌 2 张 PNG → 转换后读 `.md` + `_media/` |
| `sample_scheduler_deck.pptx` | 虚构评审 PPT，多页含嵌入图 → 同上 |
| `sample_assets/sample_fig_modules.png` | 模块关系示意（与 Word/PPT 内嵌图一致；**跳过单独扫描**） |
| `sample_assets/sample_fig_queue.png` | 队列与节点示意（**跳过单独扫描**） |
