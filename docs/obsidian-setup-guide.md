# Obsidian 使用与插件配置简介（Windows · 专利通俗解读）

本文说明两件事：

1. **你需要做的**：在 Windows 安装 Obsidian、（可选）从社区插件市场装增强插件。  
2. **技能已自动做的**：CSS 样式、核心插件 Bases、索引 / Bases 文件、关系图配色——**解读入库时写入，用户不必再装、不必再跑初始化脚本。**

相关文件：`prompts/obsidian_plugin_guide.md`、`INSTALL.md`。

---

## 1. Windows 下载与安装 Obsidian

### 1.1 下载

1. 打开官网：<https://obsidian.md/download>  
2. 选择 **Windows** → **Download for Windows**（或 **Universal**）。  
3. **请只用官网 / 官方 GitHub Releases**，避免第三方改装包。

### 1.2 安装与开库

1. 双击 `.exe` 按向导安装（一般无需管理员权限）。  
2. 打开 Obsidian，**创建新库**或**打开文件夹作为库**（例如 `C:\Users\<用户名>\Documents\Obsidian Vault`）。  
3. 把库路径告诉技能（或设环境变量），例如：

```powershell
$env:PATENT_READER_OBSIDIAN_VAULT = "D:\你的库路径"
# 可选持久化：
python tools/patent_reader/check_obsidian_env.py --set "D:\你的库路径" --setx
```

### 1.3 与本技能

- **不强制装 Obsidian**：无库时解读可落到 `outputs/patent_reader/`。  
- **有库时**：用技能解读并入库后，笔记一般在 `Research/Patents/`；库级样式与索引由入库自动写好。入库后在 Obsidian 按 **Ctrl+R** 重载即可看到效果。

---

## 2. 技能自动配置（无需你操作）

解读笔记**写入 Obsidian 库时**会自动：

| 项目 | 结果 |
|------|------|
| CSS 片段 `patent-reader` | 复制到 `.obsidian/snippets/` 并启用；笔记带 `cssclasses: patent-reader` |
| 核心插件 **Bases** | 写入 `.obsidian/core-plugins.json` 开启 |
| `patents.base`、解读索引、术语索引 | 写入 `Research/Patents/`（及术语目录） |
| 关系图彩色 Groups | 写入 `.obsidian/graph.json`（无需社区插件）；过滤器排除图片、`.json`、权项锚点/说明书段落旁路 |

Callout 观感（自动生效）：紫=著录/权要，绿=应用场景，橙=推测/公开线索，蓝=附图与 tip。

> 你**不需要**手动复制 CSS，也**不需要**为「配库」再跑 `setup_obsidian_vault.py`。

---

## 3. 社区插件（可选；须在 App 内安装）

技能**不能**代装社区插件（Obsidian 安全限制）。未装时笔记仍可正常阅读；装了更「好看」、索引表更灵活。

### 3.1 打开市场

1. **设置** → **社区插件**  
2. 关闭「限制模式 / 安全模式」  
3. 点 **浏览**

### 3.2 检索 → 安装 → 启用

对下表每个插件：搜索英文名 → **安装** → **启用** → 全部完成后 **Ctrl+R**。

| 插件（搜索名） | 作用 | 安装页 |
|----------------|------|--------|
| **Dataview** | 索引页动态表回退 | <https://obsidian.md/plugins?id=dataview> |
| **Colored Tags** | 标签上色 | <https://obsidian.md/plugins?id=colored-tags> |
| **Colored Bases Properties** | Bases 属性 pill 上色 | <https://obsidian.md/plugins?id=colored-bases-properties> |
| **Iconize** | 侧栏图标 | <https://obsidian.md/plugins?id=iconize> |
| **Supercharged Links** | 双链按属性上色 | <https://obsidian.md/plugins?id=supercharged-links> |

推荐至少装 **Dataview**；其余按需。关系图多色**不依赖**这些插件。

### 3.3 建议打开验收

| 页面 | 看什么 |
|------|--------|
| `Research/Patents/_专利解读索引.md` | Bases / Dataview |
| `Research/Patents/<公开号>/*_解读_*.md` | 解读与旁注配色 |
| 同目录 `*_图谱.canvas` | 单篇图谱 |
| `Research/Patents/_专利关联.canvas` | 多篇关联（若已有） |
| 左侧 **关系图** | 多色节点 |

---

## 4. 清单（用户侧）

- [ ] 安装 Obsidian 并打开/创建库  
- [ ] 配置库路径（或让技能探测）  
- [ ] 用技能解读入库 → **Ctrl+R**  
- [ ] （可选）社区市场安装 Dataview 等  

---

## 5. 常见问题

**Q：社区插件搜不到？**  
需联网；已关限制模式，并点「浏览」进市场。

**Q：Bases / CSS / 关系图颜色没有？**  
先确认已用技能**入库过**至少一篇，再 **Ctrl+R**。Bases 在**核心插件**里（不在社区市场）。关系图看右侧 Groups，与 Colored Tags 无关。

**Q：不能装社区插件？**  
无妨：自动配置的 CSS + Bases + 原生关系图已足够阅读。
