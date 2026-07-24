# Obsidian 插件与库配置引导（交付用户，不写入笔记）

## 使用时机

`write_patent_obsidian_note.py` 成功入库后，在**对话末尾**向用户出示（勿写入专利解读正文）。

## 话术模板

解读笔记已写入 Obsidian。**库级 CSS、Bases、索引与关系图配色已在入库时自动配置**；请 **Ctrl/Cmd+R** 重载后查看。

### 1. 建议打开

- `Research/Patents/_专利解读索引.md` — Bases 表（+ 可选 Dataview）
- 本次笔记与同目录 `*_图谱.canvas`
- 若已关联：`Research/Patents/_专利关联.canvas`
- **关系图**：靛=解读，青绿=Canvas，橙=术语（原生 Groups，无需插件）

### 2. 可选社区插件（须在 App 内安装，技能无法代下）

详见 **`docs/obsidian-setup-guide.md`**（安装步骤与插件表）：

| 插件 | 安装 | 作用 |
|------|------|------|
| Dataview | https://obsidian.md/plugins?id=dataview | 索引动态表 |
| Colored Tags | https://obsidian.md/plugins?id=colored-tags | 标签上色 |
| Colored Bases Properties | https://obsidian.md/plugins?id=colored-bases-properties | Bases pill |
| Iconize | https://obsidian.md/plugins?id=iconize | 侧栏图标 |
| Supercharged Links | https://obsidian.md/plugins?id=supercharged-links | 双链上色 |

步骤：设置 → 社区插件 → 关限制模式 → 浏览 → 搜索 → 安装 → 启用。

### 3. Obsidian CLI（可选，1.12+）

https://help.obsidian.md/cli — 检测到 `obsidian` 命令时入库可同步属性。

## 若用户未配置库

说明笔记在 `outputs/patent_reader/`；配置库路径后再解读入库即可自动完成库级配置。
