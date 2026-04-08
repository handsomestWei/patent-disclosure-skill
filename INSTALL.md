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

若未使用上述 `skills/` 布局，也可**直接用 Cursor 打开本仓库根目录**作为工作区；此时将 **`CLAUDE_SKILL_DIR`** 理解为「包含 `SKILL.md` 的目录」，prompts 路径为 `./prompts/*.md`，与 `SKILL.md` 正文说明一致。

为与 Claude Code 迁移一致，Cursor 也会扫描 **`~/.claude/skills/`**、项目内 **`.claude/skills/`** 等路径；详见 Cursor 官方文档与当前版本设置项。

## 可选依赖

若仅使用交底书 Markdown 流程，不必安装 Python。

若需使用 **`tools/md_to_docx.py`**（Markdown → Word）、**`tools/docx_to_md.py`**（Word → Markdown + 图片）或 **`tools/pptx_to_md.py`**（PPT → Markdown + 图片，供扫描）：

```bash
pip install -r requirements.txt
```

交底书定稿须同时产出 **.md + .docx**，且将 **mermaid**（**3.2 系统框图**与 **3.4 流程图**）经 **`tools/mermaid_render.py`** 转为 PNG 嵌入。**mermaid** 须 **Node.js**：在 **`tools/`** 执行 **`npm install`**（含 **`puppeteer`**）；若 **`mmdc`** 报找不到 Chrome，再执行 **`npx puppeteer browsers install chrome-headless-shell`**。详见 **`tools/README.md`**。

## 可选：外部 MiniMax Office Skills（优先于上述转换脚本）

若希望由 **[MiniMax-AI/skills](https://github.com/MiniMax-AI/skills)** 中的 **`minimax-docx`**、**`pptx-generator`** 等处理 Word/PPT 的读取与导出，请按上游 **`README_zh.md`** 在 Claude Code / Cursor 等环境中单独安装与配置 skills 路径。**本专利技能仓库不包含这些子技能**；配置成功后，`SKILL.md` 约定优先走外部能力，再走本仓库 `docx_to_md.py` / `pptx_to_md.py` 作为备选。
