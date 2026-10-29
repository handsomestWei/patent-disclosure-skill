# 安装说明

本技能遵循 [AgentSkills](https://agentskills.io) 常见布局：仓库根目录即技能根目录，内含 `SKILL.md`。

## Claude Code

在 **git 仓库根目录** 下安装：

```bash
mkdir -p .claude/skills
git clone <本仓库 URL> .claude/skills/patent-disclosure-skill
```

或使用本地路径复制到 `.claude/skills/patent-disclosure-skill`。

命令均相对**本技能仓库根**（含根级 `SKILL.md` 的目录），例如 `python skills/patent-disclosure/tools/image_gen.py`。当前工作区不是该仓库时，先定位技能安装目录再拼接。不要依赖厂商环境变量。

## Cursor

Cursor 支持 [Agent Skills](https://www.cursor.com/docs/context/skills) 约定：每个技能是一个**子文件夹**，内含根级 `SKILL.md`（`name` 字段须与文件夹名一致，本仓库为 `patent-disclosure-skill`）。可将**本仓库完整内容**（含各 `skills/patent-*` 子包）放在下列位置之一，重启 Cursor 后在 **Settings → Rules** 中查看是否已被发现；亦可用 Agent 输入 `/` 后选择技能名。

### 用户主目录（全局，所有项目可用）

| 系统 | 推荐路径 |
|------|----------|
| Windows | `%USERPROFILE%\.cursor\skills\patent-disclosure-skill\`（即 `C:\Users\<用户名>\.cursor\skills\patent-disclosure-skill\`） |
| macOS / Linux | `~/.cursor/skills/patent-disclosure-skill/` |

示例（将仓库克隆到全局技能目录）：

```bash
mkdir -p ~/.cursor/skills
git clone <本仓库 URL> ~/.cursor/skills/patent-disclosure-skill
```

Windows（PowerShell）：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills"
git clone <本仓库 URL> "$env:USERPROFILE\.cursor\skills\patent-disclosure-skill"
```

### 项目目录（仅当前仓库）

将本技能放在当前工作区下的：

`<项目根>/.cursor/skills/patent-disclosure-skill/`

（同样需包含完整仓库文件树，且 **`SKILL.md` 中 `name: patent-disclosure-skill` 与文件夹名一致**。）

### 与「仅打开文件夹」等价关系

若未使用上述 `skills/` 布局，也可**直接用 Cursor 打开本仓库根目录**作为工作区。分步指令在：

- `skills/patent-disclosure/prompts/`（交底；含 `invention/`、`utility_model/`、`design/`、填表 / 线稿，以及旁路 `fence/` 保护型 1+N）
- `skills/patent-application/prompts/`（申请文件四件套；须指定交底目录）
- `skills/patent-docket/prompts/`（交底到申请一趟串起来；须显式）
- `skills/patent-reader/prompts/`（通俗解读；含本包 `fill_*`）
- `skills/patent-map/prompts/`（专利地图；须显式）

Cursor 也会扫描 **`~/.claude/skills/`**、项目内 **`.claude/skills/`** 等路径；详见 Cursor 官方文档与当前版本设置项。

## 默认交底需要什么（发明主路径）

技能默认按**发明交底**走：定稿要 `.md` + `.docx`，3.2 / 3.4 框图要出 PNG，Step 5 优先国知局检索。这条路径**需要**：

1. **Python 3.9+**（及 pip）
2. 在技能根目录安装依赖（含 `python-docx`、`playwright` 等）：

   ```bash
   pip install -r requirements.txt
   ```

3. **本机 Google Chrome 或 Microsoft Edge**（推荐，多数电脑已有）。出图与查新共用，**不必**再装 Node / npm / mmdc。

探测是否已能启动浏览器：

```bash
python skills/patent-disclosure/tools/browser.py --probe
```

- `ok=true`：可直接定稿出图、跑国知局检索。
- 没有 Playwright 包：再执行一次上面的 `pip install -r requirements.txt`。
- 本机既无 Chrome 也无 Edge：才执行 `python -m playwright install chromium`（整机一次即可）。

无可用浏览器时，发明仍可先交 **Markdown**（mermaid 围栏保留）；Word 里框图可能先是代码块，补齐浏览器后重跑 `skills/patent-disclosure/tools/mermaid_render.py` 即可。

公式进 Word 走 **OMML**（`latex2mathml`，已在 `requirements.txt`）。**不要**为默认交底安装 matplotlib。仅当定稿 stderr 出现 `omml_text_fallback`、且用户回复「是」之后，才：

```bash
pip install matplotlib
python skills/patent-disclosure/tools/md_to_docx.py -i 定稿.md -o 定稿.docx --base-dir 定稿目录 --math-render
```

**实用新型 / 外观**定稿以各类型 `skills/patent-disclosure/prompts/utility_model|design/disclosure_builder.md` 为准：填表产出 `structure_schema`/`appearance_schema` + **`figure_plan.yaml`**，成文只嵌清单入文图（结构图或视图；docx 对实用建议、对外观可选）。不跑发明 mermaid 时，仍建议装 `requirements.txt`（扫 Word/PPT、出 docx）。

扫描目录里有 **PDF** 时再装：

```bash
pip install -r skills/patent-disclosure/tools/requirements-pdf.txt
```

仅在编辑器里**手写** Markdown、完全不跑仓库脚本时，才不必装 Python。

细则见 **`skills/patent-disclosure/tools/README.md`**。

## 可选：STEP 多视角解析（默认关闭）

扫描发现 **`.step` / `.stp`** 时，Agent **成文不中断**；交底 md+docx **落盘后再反问**是否开启。确认前**不安装** CadQuery。仅有 SolidWorks 等原生 CAD、无 STEP 时，在交付回复末尾提示导出中性格式。

先探测 `skills/patent-disclosure/tools/cad-env`（已就绪则**跳过安装**）：

```bash
python skills/patent-disclosure/tools/cad_venv.py
python skills/patent-disclosure/tools/bootstrap_cad_venv.py
python skills/patent-disclosure/tools/run_step_to_views.py --enable-step-parse -i model.step -o outputs/{案件}/cad_views
```

CadQuery 只进隔离 venv（Python **3.10–3.12**，本机已是 3.11/3.12 不必再装 3.10）。无系统 Cairo 时保留 SVG，用已有 Playwright 无头浏览器截 PNG。CAD 出图**不使用** matplotlib（matplotlib 只用于发明公式 PNG，见上文）。

与主 `requirements.txt` **独立**。细则见 `skills/patent-disclosure/prompts/project_scan.md`「CAD / STEP」、`skills/patent-disclosure/tools/README.md`。

## 外观 / 实用新型线稿（成文前必做）

不问用户。先规划再出图。仅 `PATENT_SKILL_SKIP_LINEART=1` 或用户明确不要线稿才跳过。CAD 投影不是线稿、不得入文。

```bash
python skills/patent-disclosure/tools/image_gen.py --case-dir outputs/{案件}
python skills/patent-disclosure/tools/design_lineart_gate.py --case-dir outputs/{案件} --prepare-jobs
python skills/patent-disclosure/tools/structure_lineart_gate.py --case-dir outputs/{案件} --prepare-jobs
python skills/patent-disclosure/tools/structure_lineart_compose.py --case-dir outputs/{案件}
```

流程见 `skills/patent-disclosure/prompts/image_gen.md`、`design_lineart_assist.md`、`structure_lineart_assist.md`、`structure_lineart_compose.md`。结构线稿按 `parts` 写出子 SVG 再拼总图、再 overlay 件号，禁止自创件号。

## 可选：国知局公布公告站抓取（交底查新与著录检索）

若需使用交底轻量查新 **`skills/patent-disclosure/tools/crawl/cnipa_epub_search.py`**（一词一页）或著录检索 **`skills/patent-search/tools/cnipa_search.py`**（[epub.cnipa.gov.cn](http://epub.cnipa.gov.cn/)）：

```bash
pip install -r skills/patent-disclosure/tools/crawl/requirements-cnipa.txt
python skills/patent-disclosure/tools/browser.py --probe
# 仅当 probe 显示无 Chrome/Edge 且无自带 Chromium 时：
# python -m playwright install chromium
python skills/patent-disclosure/tools/crawl/cnipa_epub_search.py --type utility_model 卡扣
# 著录检索：默认只翻 config.yaml 的 max_pages；对话或 --max-pages 可改
python skills/patent-search/tools/cnipa_search.py --inventor "发明人姓名" \
  --applicant "申请主体一" \
  --applicant "申请主体二" \
  --type all
```

检索结果落到 `outputs/patent-search/SEARCH-*.md`（版式在 `skills/patent-search/tools/emit_search_report.py`），并打印 `EPUB_SEARCH_MD` / `EPUB_SEARCH_JSON`。只有 `complete: true` 才表示已翻到末页；退出码 `3` 表示部分结果，禁止据此声称“全部”。普通查询不要默认 `--complete`。

**合规**：公布公告站为公开政府信息，脚本已内置礼貌访问（约 800ms 页间延迟、本机浏览器 UA、跨会话冷却）。请遵守目标站使用条款与 robots，**限个人研究与低频使用，勿高频/批量商业抓取**；遇验证码/WAF 时用真人浏览器（computer-use MCP）按正常人工访问处理。

**下载全文 PDF**：公布公告站**著录检索**只出清单，**不直接下全文**。全文 PDF 下载走两条途径之一（见 `skills/patent-reader/references/patent_pdf_sources.yaml`）：

- **① computer-use MCP 桌面控制**（优先；Google Patents 连不上 / 遇瑞数 WAF / 验证码 / 需国知局单行本时亦用）：**前置——用户须先自行登录其国知局账户**（单行本下载需登录态；技能不代登录、不接触/不保存凭据），登录态保留在用户浏览器会话。用真人浏览器（Chrome/Edge）在 `epub.cnipa.gov.cn/patent/{pub}` 或 Google Patents 详情页导航，点「单行本」/下载链接、过验证码后保存 PDF。真人浏览器可过 WAF，不受服务端接口不稳定限制。
- **② 技能脚本** `skills/patent-reader/tools/extract/fetch_patent_pdf.py`（备选，Google Patents 页 → CDN，快，常规件）。

**合规**：专利全文 PDF 为**法定公开信息**；真人浏览器 GUI 逐篇下载属**正常人工访问**（比 headless 脚本更接近人工、更合规），过验证码是真人输入、非绕过技术措施。请**保持人工节奏、控制单次数量，勿自动化批量抓取**；下载件仅限**个人研究与内部流程**，勿再分发/转售/商业建库，商业用途走官方/授权渠道；不绕过登录/付费访问控制（付费/账号库不在默认链路，见 `patent_pdf_sources.yaml`）。

仍失败才请用户提供 PDF。

**Windows 终端**：定稿 / 查新脚本会把 stdout、stderr 设为 UTF-8，子进程带 `PYTHONUTF8=1`。Agent **以退出码和机读前缀为准**（`EPUB_HITS_JSON:`、`EPUB_SEARCH_JSON:`、`PROBE:`、`MERMAID:`、`DOCX:`、`MATH:`）；stderr 有中文或 PowerShell `NativeCommandError` **不等于**失败。不必先 `chcp 65001`。若仍乱码，可设 **`PYTHONUTF8=1`**，且不要用 **`2>&1`** 把 JSON 混进错误流。

**Windows 终端**：定稿 / 查新脚本会把 stdout、stderr 设为 UTF-8，子进程带 `PYTHONUTF8=1`。Agent **以退出码和机读前缀为准**（`EPUB_HITS_JSON:`、`PROBE:`、`MERMAID:`、`DOCX:`、`MATH:`）；stderr 有中文或 PowerShell `NativeCommandError` **不等于**失败。不必先 `chcp 65001`。若仍乱码，可设 **`PYTHONUTF8=1`**，且不要用 **`2>&1`** 把 JSON 混进错误流。

`playwright` 已写入根目录 `requirements.txt`。若已按上文装过主依赖，**不必**再为查新单独 pip 一遍；`skills/patent-disclosure/tools/crawl/requirements-cnipa.txt` 仅在只装爬虫、不装整份主依赖时使用。未装或探测失败时，Step 5 仍可按该 prompt 降级为 **WebSearch**（如 Google 学术）。

## 可选：申请文件（须显式；须指定交底目录）

把已有交底产出改写成权利要求书、说明书、摘要与黑白附图。不另装依赖（PyYAML + 已有 python-docx / playwright）。不做 TIFF。

```bash
python skills/patent-application/tools/material_gate.py --case-dir outputs/{案件}
python skills/patent-application/tools/render_invention_figures.py \
  --plan outputs/patent-application/{案}/figures/invention_figures.yaml \
  --out-dir outputs/patent-application/{案}/figures
python skills/patent-application/tools/audit_claims.py outputs/patent-application/{案}/权利要求书.md
python skills/patent-application/tools/check_support.py --dir outputs/patent-application/{案} --case-dir outputs/{案件}
python skills/patent-application/tools/emit_application_docx.py --dir outputs/patent-application/{案}
```

缺材料时门禁退出码为 2，应先回到交底技能补齐。细则见 [skills/patent-application/SKILL.md](skills/patent-application/SKILL.md)。**合规**：本包产出为内部撰写底稿；代为撰写专利申请文件属专利代理业务，递交前应经有资质专利代理师复核（详见根 `README.md`「使用边界与合规」）。

## 可选：案卷会稿（须显式）

把交底书和申请文件串成一趟：按发明人/工程师给的材料成文，申请问题清单上的缺口最多改三轮。不另装依赖（根目录 `PyYAML`）。本包只记账和派工，正文仍由交底包、申请包来写；派工时读对方 `SKILL.md`，不要从这里调那些包的 `tools/`。缺技术事实就停下来问，不要编。

```bash
python skills/patent-docket/tools/init_docket.py --case-id {案件slug} --mode from_zero
python skills/patent-docket/tools/validate_docket.py --yaml outputs/docket/{案件slug}/docket.yaml
python skills/patent-docket/tools/emit_tracker.py --yaml outputs/docket/{案件slug}/docket.yaml
```

产物在 `outputs/docket/{案件}/`（`docket.yaml` + `TRACKER.md`），机读前缀 `DOCKET_DIR:` / `DOCKET_YAML:` / `DOCKET_OK:` / `DOCKET_ERROR:`。细则见 [skills/patent-docket/SKILL.md](skills/patent-docket/SKILL.md)。**合规**：案卷会稿调度的申请文件/答复稿为内部底稿，递交前应经有资质专利代理师复核，不替代代理机构。

## 可选：审查答复案例库（默认关闭）

显式触发「审查答复 / 案例入库 / `/oa`」后使用。配置与向量库默认在操作系统**文档**目录：`{Documents}/patent-disclosure-skill/oa/`（`PATENT_OA_HOME` 可覆盖）。**推荐**智谱 `embedding-3`；亦支持 DashScope / MiniMax / 本地 / OpenAI（`config.py set --preset …`）。

```bash
pip install -r skills/patent-oa/tools/requirements-oa.txt
# 例：智谱
# 环境变量 ZHIPUAI_API_KEY=…
python skills/patent-oa/tools/config.py recommend
python skills/patent-oa/tools/config.py set --preset zhipu
# 其他：--preset dashscope|minimax|local|openai
python skills/patent-oa/tools/ingest_case.py -i path/to/case.md
python skills/patent-oa/tools/refresh_vault.py   # 刷新 oa 索引 / Bases / 关联 Canvas
python skills/patent-oa/tools/search_cases.py --query "创造性 区别特征" --defect inventiveness --top-k 5
# 用户确认采纳某份草稿后，才出陈述正文 Word
# python skills/patent-oa/tools/emit_opinion_docx.py -i outputs/oa/案/意见陈述_时间戳.md
```

Obsidian 案例落在 `{vault}/oa/cases/history/`（另有 `pending/`、`drafts/`）。与主依赖**独立**。细则见 `skills/patent-oa/prompts/`、`skills/patent-oa/tools/README.md`、[skills/patent-oa/SKILL.md](skills/patent-oa/SKILL.md)。**合规**：意见陈述为内部草稿，代为答复审查意见属专利代理业务，递交前应经有资质专利代理师复核；案例入库默认脱敏。

## 强烈建议：专利通俗解读 + Obsidian 库

**强烈建议安装并配置 Obsidian**，才能完整体验索引、Canvas 知识图谱、术语网、关系图配色与公开线索旁注。取证与中间产物写在工作区 `outputs/patent_reader/`；无库时笔记也落在该目录，效果会弱一截。

对话开始前由 Agent 运行探测（也可手动）：

```bash
python skills/patent-reader/tools/vault/check_obsidian_env.py
# 自动接受唯一/当前打开的库：
python skills/patent-reader/tools/vault/check_obsidian_env.py --auto-accept
# 手动指定并持久化（+ Windows 用户环境变量）：
python skills/patent-reader/tools/vault/check_obsidian_env.py --set "C:\Users\你\Documents\Obsidian Vault" --setx
```

亦可仅设会话变量：

```bash
# Windows PowerShell
$env:PATENT_READER_OBSIDIAN_VAULT = "D:\Obsidian\你的库"
# 可选：库内目录，默认 Research/Patents
$env:PATENT_READER_PAPERS_DIR = "Research/Patents"
$env:PATENT_READER_GLOSSARY_DIR = "Research/术语"
```

```bash
pip install -r skills/patent-reader/tools/requirements.txt   # PDF：pymupdf
pip install -r skills/patent-map/tools/requirements.txt     # 可选：专利地图语义地形（fastembed，不含 PyTorch）
```

专利地图向量模型与加速副本默认在文档目录 `{Documents}/patent-disclosure-skill/patent-map/`（与 oa 同级，`PATENT_MAP_HOME` 可覆盖），不要下到工作区。可先跑 `python skills/patent-map/tools/ensure_model.py`。

**首次使用**：解读**入库时会自动**初始化库（CSS、Bases、索引、关系图配色）。用户只需安装 Obsidian、配置库路径，并（可选）在社区插件市场安装 Dataview 等——步骤与插件清单见 **`skills/patent-reader/docs/obsidian-setup-guide.md`**。交付后 Agent 按 **`skills/patent-reader/prompts/obsidian_plugin_guide.md`** 引导可选插件。

工具链分层见 **`skills/patent-reader/tools/README.md`**（`shared/` · `extract/` · `analyze/` · `vault/`）。常用入口：

```bash
python skills/patent-reader/tools/extract/fetch_patent_pdf.py --pub CN… -o outputs/patent_reader/RUN
python skills/patent-reader/tools/vault/write_patent_obsidian_note.py --help
```
