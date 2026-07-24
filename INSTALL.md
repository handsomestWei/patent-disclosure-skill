# 安装说明

本技能遵循 [AgentSkills](https://agentskills.io) 常见布局：仓库根目录即技能根目录，内含 `SKILL.md`。

## Claude Code

在 **git 仓库根目录** 下安装：

```bash
mkdir -p .claude/skills
git clone <本仓库 URL> .claude/skills/patent-disclosure-skill
```

或使用本地路径复制到 `.claude/skills/patent-disclosure-skill`。

运行时环境通常会设置 **`CLAUDE_SKILL_DIR`** 指向该技能目录；`SKILL.md` 中的 `${CLAUDE_SKILL_DIR}/prompts/...` 即解析到此路径。

## Cursor

Cursor 支持 [Agent Skills](https://www.cursor.com/docs/context/skills) 约定：每个技能是一个**子文件夹**，内含根级 `SKILL.md`（`name` 字段须与文件夹名一致，本仓库为 `patent-disclosure-skill`）。可将**本仓库完整内容**（含 `prompts/`、`tools/` 等）放在下列位置之一，重启 Cursor 后在 **Settings → Rules** 中查看是否已被发现；亦可用 Agent 输入 `/` 后选择技能名。

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

若未使用上述 `skills/` 布局，也可**直接用 Cursor 打开本仓库根目录**作为工作区；此时将 **`CLAUDE_SKILL_DIR`** 理解为「包含 `SKILL.md` 的目录」，prompts 路径为 `./prompts/*.md`，与 `SKILL.md` 示例命令中的 **`${CLAUDE_SKILL_DIR}`** 同义。

为与 Claude Code 迁移一致，Cursor 也会扫描 **`~/.claude/skills/`**、项目内 **`.claude/skills/`** 等路径；详见 Cursor 官方文档与当前版本设置项。

## 可选依赖

若仅使用交底书 Markdown 流程，不必安装 Python。

若需使用 **`tools/md_to_docx.py`**（Markdown → Word）、**`tools/docx_to_md.py`**（Word → Markdown + 图片）或 **`tools/pptx_to_md.py`**（PPT → Markdown + 图片，供扫描）：

```bash
pip install -r requirements.txt
```

交底书定稿须同时产出 **.md + .docx**，且将 **mermaid**（**3.2 系统框图**与 **3.4 流程图**）经 **`tools/mermaid_render.py`** 转为 PNG 嵌入。**mermaid** 须 **Node.js**：在 **`tools/`** 执行 **`npm install`**（含 **`puppeteer`**）；若 **`mmdc`** 报找不到 Chrome，再执行 **`npx puppeteer browsers install chrome-headless-shell`**。详见 **`tools/README.md`**。

## 可选：国知局公布公告站抓取（Step 5 查新优先路径）

若需使用 **`tools/cnipa_epub_search.py`**（一步，推荐）或 **`tools/cnipa_epub_crawler.py`** / **`tools/cnipa_epub_parse.py`**（[epub.cnipa.gov.cn](http://epub.cnipa.gov.cn/)，见 `prompts/prior_art_search.md`）：

```bash
pip install -r tools/requirements-cnipa.txt
python -m playwright install chromium
```

**Windows 终端中文**：`cnipa_epub_search.py` / `cnipa_epub_crawler.py` 已对 stdout/stderr 尝试 **UTF-8**（`reconfigure`）。若仍乱码，可在运行前执行 **`chcp 65001`**，或设置环境变量 **`PYTHONUTF8=1`**，以便复制 **`EPUB_HITS_JSON:`** 一行给 Agent 时不误判为失败。

与主流程 `requirements.txt` **独立**；未安装时 Step 5 仍可按该 prompt 降级为 **WebSearch**（如 Google 学术）。

## 强烈建议：专利通俗解读 + Obsidian 库

**强烈建议安装并配置 Obsidian**，才能完整体验索引、Canvas 知识图谱、术语网、关系图配色与公开线索旁注。无库时可降级到 `outputs/patent_reader/`，效果会弱一截。

对话开始前由 Agent 运行探测（也可手动）：

```bash
python tools/patent_reader/check_obsidian_env.py
# 自动接受唯一/当前打开的库：
python tools/patent_reader/check_obsidian_env.py --auto-accept
# 手动指定并持久化（+ Windows 用户环境变量）：
python tools/patent_reader/check_obsidian_env.py --set "C:\Users\你\Documents\Obsidian Vault" --setx
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
pip install -r tools/patent_reader/requirements.txt   # PDF：pymupdf
```

**首次使用**：解读**入库时会自动**初始化库（CSS、Bases、索引、关系图配色）。用户只需安装 Obsidian、配置库路径，并（可选）在社区插件市场安装 Dataview 等——步骤与插件清单见 **`docs/obsidian-setup-guide.md`**。交付后 Agent 按 **`prompts/obsidian_plugin_guide.md`** 引导可选插件。

工具链见 **`tools/patent_reader/README.md`**。
