# 国知局公布站 GUI 批量下载专利全文 PDF（windows-computer-use MCP）

> **来源**：2026-10 实测批量下载 21 篇发明公布（CN…A）全部成功（约 30–40 分钟），流程与踩坑已按实操逐条沉淀。
> **工具**：**只用 windows-computer-use MCP**（原 pi-computer-use 技能已卸载，其 `act_ui`/`observe_ui`/`expand_ui`/`search_ui` ref 工具不再可用；本手册全部改用 MCP 等价工具，见 §2 工具映射）。
> **用途**：检索出公开号清单（如 `outputs/patent-search/_consolidated.csv`）后，用真人浏览器在国知局公布站（cnipa）逐篇下载全文 PDF。是 `patent_pdf_sources.yaml` 中 `computer_use_mcp`（primary_download）的具体操作手册。
> **前提**：优先于技能脚本 `fetch_patent_pdf.py`（Google Patents 连不上/遇瑞数 WAF/验证码、或需国知局单行本时必走本途径）。
> **合规**：专利全文 PDF 为**法定公开信息**；真人浏览器逐篇 GUI 下载属**正常人工访问**（比 headless 脚本更接近人工），过验证码是真人输入、非绕过技术措施。**使用边界**：保持人工节奏、控制单次数量，勿自动化批量抓取（本手册 21 篇为实测人工批量）；下载件仅限**个人研究与内部流程**，勿再分发/转售/商业建库，商业用途走官方/授权渠道；不绕过登录/付费访问控制（付费/账号库不在本链路）。

---

## 0. 工具加载（MCP 是 deferred 暴露）

windows-computer-use MCP 在 `~/.pi/agent/mcp.json` 配置，`exposure: deferred`——**不自动注入**，用前先 `tool_search` 加载：

```text
tool_search(query="windows computer use automation windows")     # 加载 automation_windows / get_window_state
tool_search(query="windows computer use elements click set_text")  # 加载 automation_elements
tool_search(query="windows computer use keyboard hotkey mouse")    # 加载 automation_keyboard / automation_mouse
tool_search(query="windows computer use approve automation")       # 加载 approve_automation
```

> 若工具名报"未定义"，先 `tool_search` 再调用；本手册全部工具均属 MCP，**不再引用** `act_ui`/`observe_ui`/`search_ui`/`expand_ui`/`inspect_ui`/`read_text`/`wait_for`/`find_roots`（这些是已卸载的 pi-computer-use）。

---

## 1. 环境准备（一次性）

1. **Chrome 已启动并已登录国知局检索系统**（cnipa，用户常已登录）。确认标签页固定为：
   - `1 = 常规检索`（搜索框所在）
   - `2 = 检索结果`（点检索后出现）
   - `3 = 文献浏览`（点公开号后自动跳转/打开）
2. **已批准自动化**：`approve_automation(duration_minutes=60)`（长任务建议覆盖整批，本批次 21 篇约 40 分钟；到期后 MCP 动作会被 HITL 拦截，需重新批准）。
3. **拿 Chrome 窗口句柄**：`automation_windows` `operation=list`（或 `find` title="Google Chrome"）→ 记下 `window_handle`（本批为 1769702）。后续所有 `get_window_state`/`automation_elements` 都用它。
4. **确认窗口尺寸稳定**：本批为 1920×1032。下列坐标以此为准；**若窗口缩放/DPI 变化，坐标会漂移，一律改用 `get_window_state` 拿元素 `element_index` 再 `automation_elements` 操作**（绝对坐标只作快速路径）。

---

## 2. 工具映射（pi-computer-use → windows-computer-use MCP）

| 原 pi-computer-use（已卸载） | 现用 windows-computer-use MCP |
|---|---|
| `observe_ui(root=@r1)` | `get_window_state(window_handle=…)` → 返回 `snapshot_id` + `elements[]`（每个带 `element_index`/`control_type`/`title`/`rect`） |
| `search_ui(role=edit)` | `get_window_state` 的 `elements[]` 里找 `control_type="Edit"`（或用 `automation_elements list`） |
| `expand_ui` | 不需要——`get_window_state` 已给全树（用 `max_depth` 控制） |
| `inspect_ui` | `automation_elements(operation=info, element_index=…)` |
| `act_ui(setText, ref=@e47, text=…)` | `automation_elements(operation=set_text, element_index=…, text=…)`（pywinauto ValuePattern，**同样绕开输入法**） |
| `act_ui(click, ref=@下载图标)` | `automation_elements(operation=click, element_index=…)`（或 `automation_mouse click x y`） |
| `act_ui(keypress ctrl+1)` | `automation_keyboard hotkey ["ctrl","1"]` |
| `find_roots` | `automation_windows list/find`（拿 HWND） |
| `read_text` | `automation_visual extract_text`（OCR）或元素 `title`/`text` |

---

## 3. 每篇稳定操作序列（实测 21 次全成功；工具已换 MCP）

> 核心原则：**用 `get_window_state` 拿 `element_index` 再 `automation_elements` 精确操作**（ref 思路保留，但走 MCP）；绝对坐标仅作快速路径；**每步等待要足、不连点**。

### 步骤 A：切到常规检索
```text
automation_keyboard hotkey ["ctrl","1"]   # 切到「常规检索」标签页
```

### 步骤 B：定位搜索框（拿 element_index）
```text
get_window_state(window_handle=…, capture_mode="ax")   # 返回 snapshot_id + elements[]
# 在 elements[] 里找 control_type="Edit" 且 title 含「请输入关键词」→ 记 element_index（本批 e47 对应）
```

### 步骤 C：输入公开号 —— **必须 set_text，勿用键盘/剪贴板**（见 P1 输入法乱码）
```text
automation_elements(set_text, window_handle=…, element_index=<搜索框>, text="CN119986841A")
```
> **输入前检查检索框残留**（见 P2）：`automation_elements(info, element_index=<搜索框>)` 看当前 value。set_text 是**替换语义**，直接设目标值即可；若确需手动清空，`automation_elements(set_text, text="")` 先清空再设目标。

### 步骤 D：点击检索按钮（快速路径坐标 ~(1400,452)；优先 element_index）
```text
automation_mouse click x=1400 y=452        # 检索按钮（本批坐标）
# 或 automation_elements(click, title="检索", window_handle=…)
sleep 5                                    # 检索结果页加载（等待要足）
```

### 步骤 E：点击公开号链接 —— **点公开号文字本身，勿点整行**（见 P3）
```text
automation_mouse click x=280 y=672          # 公开号链接（本批实测：get_window_state 公开号 ListItem at (234,670)，点 (280,672) 成功）
# 也可 automation_elements click title="CN119986841A"（但 title 可能匹配多个，需 get_window_state 确认 element_index）
sleep 6                                     # 文献浏览跳转（等待要足）
```

### 步骤 F：切到文献浏览标签页
```text
automation_keyboard hotkey ["ctrl","3"]     # 切到「文献浏览」
```

### 步骤 G：**确认文献浏览页显示目标公开号**（见 P4 防重复下载）
```text
get_window_state(window_handle=…, capture_mode="ax")
# 看 Informative Elements 里「公开号（公开）」后的值 == 目标公开号（本批 CN119986841A 确认成功）
```
> 若仍显示上一篇公开号 → **不要点下载**，回检索结果页（Ctrl+2）重新点公开号，或重做步骤 C–E。

### 步骤 H：点击「全文图像」—— **必须点，PDF 视图才进来**（见 P5）
```text
# 全文图像是 ListItem，automation_elements click 对 ListItem 不可用（实测报错），一律用坐标：
automation_mouse click x=843 y=304          # 全文图像（本批实测：get_window_state 全文图像 ListItem at (795,294)，点 (843,304) 成功）
sleep 4                                     # 全文图像视图加载（等待要足）
# 确认：get_window_state 里「全文图像」class_name=activeli 且出现 Document "全文图像浏览"
```

### 步骤 I：点击工具栏**下载图标**（见 P5，不是左侧"下载"蓝色文字）
```text
# title="下载" 会匹配 2 个（左侧批量下载文字 + 工具栏下载图标），automation_elements click 有歧义失败；
# 用坐标区分：工具栏下载图标本批实测 at (1245,328)（class toolbarButton download，顶部工具栏），点 (1259,342)：
automation_mouse click x=1259 y=342        # 工具栏下载图标（本批实测成功，触发真实下载）
sleep 5                                     # 下载完成（等待要足）
# 左侧批量下载"下载"文字在 (142,337)（class el-button...medium），勿点。
```

### 步骤 J：校验下载成功（见 P8 重名）
```bash
ls -la ~/Downloads/CN119986841A*            # 允许匹配 "(1).PDF" 等重名后缀；大小 > 500KB 即成功
```

### 步骤 K：关闭下载气泡 + 复制到项目目录
```text
automation_keyboard hotkey ["escape"]       # 关闭「近期的下载记录」气泡
```
```bash
cp ~/Downloads/CN119986841A.PDF outputs/patent-pdf/CN119986841A.PDF
```

> 回到步骤 A，处理下一篇。**每篇约 1.5–2 分钟**（含等待），21 篇约 30–40 分钟。

---

## 4. 关键踩坑与应对（按重要性）

| 编号 | 现象 | 根因 | 应对 |
|------|------|------|------|
| **P1** | 用 `automation_keyboard type`/剪贴板输入公开号产生**乱码**（如 `CN119986841A` 变 `CN19986841A`、追加乱码） | Windows 中文输入法（微软拼音）在焦点切换时干扰；Ctrl+A/Delete/Home/End/Shift 清空均可能失败 | **一律用 `automation_elements(set_text)` 直接设置 value**（pywinauto ValuePattern，绕开输入法），这是唯一可靠方法 |
| **P2** | 检索框残留上次字符，拼出 `CNxxxCNyyy` 或检索结果异常 | 换篇时检索框未清空 | set_text 前先 `automation_elements(info)` 看当前 value；set_text 为替换语义，直接设目标值；若手动键盘输入必须先 Ctrl+A→Delete |
| **P3** | 点击检索结果**整行**（ListItem）不跳转，文献浏览不刷新 | 跳转只挂在**公开号文字链接**上，整行/标题无跳转 | **点击公开号文字本身**（`CNxxxxx`，坐标 ~(300,680)），不要点整行或发明名称 |
| **P4** | 文献浏览标签页仍显示**上一篇**（旧内容），直接点下载图标会**重复下载** | 点击公开号后文献浏览不自动刷新；或 Ctrl+3 切到的是旧页 | **下载前必须** `get_window_state` 确认「公开号（公开）」== 目标；不符则回检索结果（Ctrl+2）重新点公开号 |
| **P5** | 点了左侧**"下载"蓝色文字**（属文献浏览列表批量下载）却没下到单行本 | 真正的下载按钮是**中部工具栏的下载图标**（全文图像视图内，鼠标悬浮显示"下载"） | **点工具栏 `toolbarButton "下载"` 图标**（本批坐标 (1259,342)，get_window_state 显示 at (1245,328)），不是左侧列表"下载"文字（at (142,337)）；且**必须先点「全文图像」**让 PDF 视图进来 |
| **P6** | 检索结果为空 / 文献浏览空白 / 下载 0 字节 | **等待不足**或**点击频次过快**（连点触发重复标签/重复下载） | 等待：检索后 5s、跳转后 6s、全文图像加载后 4s、下载后 5s；**每步一次点击，不连点** |
| **P7** | 坐标点击落到错误位置 | 窗口缩放/DPI 变化，绝对坐标漂移 | **坐标不固定**；优先 `get_window_state` 拿 `element_index` 再 `automation_elements`；绝对坐标仅作已知窗口尺寸下的快速路径 |
| **P8** | `~/Downloads` 出现 `CNxxx (1).PDF`、`CNxxx (2).PDF` | Chrome 对重名自动加序号 | 校验用 `ls ~/Downloads/{pub}*`（含括号后缀）；按公开号去重，不要按文件名精确匹配 |
| **P9** | MCP 动作被拦（HITL） | `approve_automation` 时长到期 | 长任务开始批准足够时长（≥整批），接近到期重新 `approve_automation` |
| **P10** | 文献浏览页异常/坐标反复失败 | 页面结构异常、弹窗遮挡 | **不要反复重试超 1–2 次**；停止并查验（见 §5） |

---

## 5. 出错时的查验与应对（有序）

1. **先查文件是否其实已下载**：`ls ~/Downloads/{pub}*`。若已存在（含括号后缀）→ 视为成功，跳过。
2. **确认当前标签页**：`automation_windows` `get_active`（或看窗口标题）。正确应为「常规检索/检索结果/文献浏览」之一；错则 Ctrl+1/2/3 切回。
3. **`get_window_state` 文献浏览页**：确认当前显示的公开号（「公开号（公开）」值）与当前「全文图像/著录项目」activeli 状态。
4. **核对检索结果页**：`get_window_state` 看是否 1 条记录、公开号是否匹配；0 条 → 重做步骤 B–D（可能检索词没设对/按钮没点中）。
5. **上述均无效 → 及时向用户求助**（见 §6），**不要盲目连点**。

---

## 6. 位置问题完不成时 → 及时求助（不硬扛）

- **何时求助**：元素/坐标定位反复失败 ≥2 次、文献浏览持续不刷新、页面异常（验证码/弹窗/登录失效）、检索结果与预期不符且重试无效。
- **求助内容**（向用户描述清楚，请其手动调整或确认）：
  - 当前 Chrome 窗口标题与标签页（`automation_windows` `get_active` / `list`）
  - 文献浏览页当前显示的公开号
  - 是否出现验证码/弹窗/登录过期
  - 你已尝试的动作与失败点
- **原则**：**先报告再问用户**，不要只报「连不上/定位失败」就默认无 PDF 或放弃；也不要反复点击造成重复下载或开重复标签。

---

## 7. 其他本次实操要点

- **下载位置**：Chrome 默认 `%USERPROFILE%\Downloads`（即用户下载文件夹）；批量完成后按公开号去重复制到项目 `outputs/patent-pdf/`。
- **任务要求对应**：本流程对应任务要求.txt 第 8 条（GUI 下载流程）与第 9 条（下载完成后切回检索页/检索结果页处理下一篇）。
- **全部 21 篇为发明公布（CN…A）**；外观设计（CN…S）不走此途（见 `fetch_design_views.py`，`patent_pdf_sources.yaml` 的 `design_views`）。
- **源表呼应**：本手册是 `patent_pdf_sources.yaml` 中 `computer_use_mcp` 的落地操作；`fetch_patent_pdf.py` 脚本仅作常规件备选。
