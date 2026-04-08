# 项目文档扫描（Step 2）

## 目标

按优先级扫描并提取**可专利化**内容。**根据当前项目结构调整扫描路径**。

## 优先级表

| 优先级 | 文档类型 | 关注内容 |
|--------|----------|----------|
| 1 | 专利相关文档 | 专利点分析、已有交底书、专利申报建议、创新点汇总 |
| 2 | 详细设计/方案文档 | 详细设计、方案讨论、流程图、完整流程、技术对比分析 |
| 3 | 核心实现代码 | 算法与策略实现、业务逻辑与流程编排、数据处理与转换、规则引擎与决策逻辑、接口与集成设计、状态机与调度机制、性能优化与缓存策略、安全与权限控制等（依项目领域灵活识别） |
| 4 | 系统设计文档 | 系统设计、架构说明、模块划分、数据流与控制流 |

## 扫描目标目录模版

执行时按项目实际目录填写：

```
[项目根目录]/
├── [专利或文档目录]/     ← 专利点分析、交底书、申报建议
├── [设计文档目录]/       ← 详细设计、方案讨论、流程图、技术对比
├── [代码目录]/           ← 算法实现、业务逻辑、规则引擎、接口与集成、调度机制等
└── [根目录]/             ← 系统设计、架构说明、模块与数据流
```

## 执行提示

- 大仓库先用搜索 / 语义检索定位关键文件，再精读。
- 记录**引用路径或文件名**，便于在交底书中写「参见某设计」时脱敏表述。
- 若原材料为 **Word（.docx）** 或 **PowerPoint（.pptx）**：**已接入外部 [MiniMax Skills](https://github.com/MiniMax-AI/skills)（如 `minimax-docx`、`pptx-generator`）时，优先用其读取/导出**，再扫描；**否则**用本技能仓库 **`tools/docx_to_md.py`** / **`tools/pptx_to_md.py`**（见 `SKILL.md`「Office 原材料提取顺序」）；老版 `.doc` / `.ppt` 需先另存为 OOXML 格式。

## Office 文档（.docx / .pptx）：必先转换再读

Agent **不得**因「只能舒适读取文本」而**遗漏**项目内的 Word / PPT：**必须先转为 Markdown 再纳入扫描**，不能只扫 `.md` 与源码。

1. **发现**：在扫描目录内 **`Glob` 或列举** `*.docx`、`*.pptx`（含子目录，如 `docs/sample_*.docx`）。
2. **转换（本仓库脚本）**：对每个文件执行（路径按实际替换；`${CLAUDE_SKILL_DIR}` 为技能根）：

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/tools/docx_to_md.py -i "<路径>/<名>.docx" -o "<同目录或 docs>/<名>.md"
   python3 ${CLAUDE_SKILL_DIR}/tools/pptx_to_md.py -i "<路径>/<名>.pptx" -o "<同目录或 docs>/<名>.md"
   ```

   需已 `pip install -r requirements.txt`。输出旁会生成 **`{md 主名}_media/`**，内为嵌入图，**以生成的 `.md` 正文与图片引用为扫描依据**。
3. **再读**：**`Read`** 上述新生成的 `.md`（及必要时扫一眼 `_media` 文件名用于脱敏引用），与原有 `.md`、代码**同等对待**，摘要进专利点材料表。
4. **解析重点**：表格、编号列表、**PPT 每页标题与正文**、**Word 修订区以外的正文**、**备注**（`pptx_to_md` 会写入「备注」小节）——均属可专利化叙述来源。

## 图片与裸图目录（跳过单独识图）

- **`sample_assets/`** 等目录下的 **独立 `.png` / `.jpg` / `.webp` 等**：**不作为** Step 2 必须逐个打开、OCR 或描述的对象（与 Word/PPT 内嵌图**通常重复**时更不必重复读图）。
- **例外**：用户**点名**某图片路径，或某图**未**出现在任何已转换 Office 的 `_media` 中且对专利点明显关键时，再按需处理。
- Word/PPT 转换后，嵌入图已在 **`![](相对路径)`** 中体现，**以 Markdown 文本扫描为主**即可。

## 示例案件 `knowledge/docs/`（练习时勿漏）

若扫描路径包含 **`examples/example_batch_job_scheduler/knowledge/`**（或同构案件目录），须覆盖：

| 路径 | 动作 |
|------|------|
| `docs/architecture.md` | 直接 Read |
| `docs/sample_architecture_review.docx` | **先** `docx_to_md.py` → 再 Read 生成的 `.md` |
| `docs/sample_scheduler_deck.pptx` | **先** `pptx_to_md.py` → 再 Read 生成的 `.md` |
| `docs/sample_assets/*.png` | **跳过**单独精读（内容已由 Office 内嵌图 + 转换 MD 覆盖） |
| `pkg/scheduler/*.go` | Read |
