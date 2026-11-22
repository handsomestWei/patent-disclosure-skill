# 保护型 1+N · 确认后分件写交底

只处理用户确认里的节点 id。先改 `family.yaml` 的 `write_this_round`，使本趟核心 ≤2、外围 ≤3，且：

- `material_ok` 不为 false  
- 外围 `matrix_density` 不是 `dense`  
- 外围带 `n_class`: `scenario` | `improve` | `chain`

同一套 id 改 `专利布局.md` 的「这一轮打算写 / 先放下」，不要用脚本从 yaml 生成。再跑：

```bash
python skills/patent-disclosure/tools/fence/check_layout.py --family outputs/{案件}/fence/family.yaml
```

## 调度顺序

对每个 `write_this_round: true` 的节点**依次**写交底，不要并行糊成一份，**禁止**再走「3–5 点融合成一篇」。

主路径 Step 3–4 / Step 5 **不要重跑整案挖点**。分件查新只针对本件 `necessary_features`：按 `prompts/prior_art_search.md`（主路径已走 A0 则同样用该 MCP，否则本包 `cnipa_epub_search.py` 一词一页），写入**该篇** 1.1。**禁止**抄首篇对比清单，**禁止**调仓库内 `patent-search` 的 `tools/`。

| 节点 | 怎么写 |
|------|--------|
| `core` | 以首篇交底为基准走 `iteration_context.md` → `correction_handler.md`（或 `merger.md`）：**另存新时间戳**。第五章只留该节点 `necessary_features`；`slim_note` 里的点从独权拿掉，能支撑的放从属口径或删。类型用节点 `patent_type`，读对应 `*/disclosure_builder.md`。本件查新写该篇 1.1。 |
| `satellite`（或旧字段 `fence`） | 按 `n_class` 写这一件：`scenario` 场景/工况，`improve` 改进结构，`chain` 上下游。读该节点类型的 `disclosure_builder.md` + `template_reference.md`。查新词用本件特征。缺图/缺 schema：实用/外观按本包填表与线稿 prompt 补；材料没有则该件停、标未决，不编。 |

文件名建议：`{案件}_{节点id}_{YYYYMMDDHHmmss}.md`（及同名 docx，规则与 §7.3 相同），仍在该案件 `outputs/{案件}/` 下。  
每件写完做该类型 Step 8 自检（**不要**对分件再开一轮 1+N 旁路）。  
**不要**对布局各件自动进入申请文件或案卷。

全部预定节点完成后，对话列出：节点 id、`n_class`、类型、md 路径、核心从首篇拿掉了什么、哪件因 dense/材料不够没写。用户要改方案则回到 `plan.md`，不要无确认再开一批。
