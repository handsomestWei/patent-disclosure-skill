<div align="center">

# 中国专利.skill

> 专利点挖掘与交底书（发明/实用/外观）编写，已有交底改写成申请文件，交底到申请可以一起做，公布公告著录检索，通俗解读专利，对照审查口径出政策简报，辅助审查答复。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-mermaid%20%2B%20CNIPA-2EAD33.svg)](https://playwright.dev/)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)

<br>

有设计文档和代码，但**专利点还没梳**？交底书要**框图 + 可改 Word**？<br>
定稿后还要**多轮补材料、纠错**并留下修改追溯？<br>
公开专利晦涩难懂，想**快速看懂权要与落地语境**？

[初衷](#初衷) · [运行效果](#运行效果) · [子技能列表](#子技能列表) · [支持作者](#支持作者) · [参考文档](#参考文档) · [安装说明](INSTALL.md) · [技能入口](SKILL.md)

</div>

---

## 初衷

### 专利交底书编写

> **做了多年核心研发，专利发明人那一栏从没写过我的名字。**

代码是自己敲的，方案是自己扛的，轮到交底书却卡在「专利点怎么挖、查新怎么写、框图和 Word 怎么一次交得出去」。本技能把这一环打通：覆盖发明 / 实用新型 / 外观设计，结构图与外观图都能读懂、写进交底；从项目材料梳出可申请的点，查新、脱敏、成文、迭代另存——让真正干活的人，也能把技术贡献写进可交付的交底书里。

### 专利通俗解读

> **不止一篇。**

公开专利常把阅读门槛抬得很高：权要绕、术语密、落地语境散落在说明书与附图里。本技能把单篇读成通俗笔记与图谱，并入库 Obsidian；依托双链、图谱、插件与 Bases 等生态，陆续解读的专利可以沉淀成**只属于自己的私有专利知识库**——权要、术语、线索与附图彼此勾连，越读越厚。再叠上 [Obsidian CLI](https://help.obsidian.md/cli) 与库内外连接能力，检索、批处理、和外部工具接力都更容易：从单篇通俗笔记，走向可检索、可关联、可继续生长的个人专利情报层，把沉睡在 PDF 里的技术细节重新点亮。库厚了之后，还能在这层之上做**专利比对、挖掘与分析**——同族对照、技术路线梳理、差异点扫描，把「读懂」推进到「用起来」。

---

## 运行效果

### 专利交底书编写

<table width="100%" border="1" cellpadding="12" cellspacing="0">
<tr>
<th width="50%" align="center">初版生成<br><sub>首次落盘交付</sub></th>
<th width="50%" align="center">迭代更新<br><sub>多版本并存 + 对话记录</sub></th>
</tr>
<tr>
<td width="50%" valign="top" align="center">
<img src="docs/效果例-初版生成.jpg" alt="初版生成：outputs 目录下的时间戳交底书、mermaid 图目录等" width="100%" />
</td>
<td width="50%" valign="top" align="center">
<img src="docs/效果例-迭代更新.jpg" alt="迭代更新：新时间戳文件与交底书修订对话记录" width="100%" />
</td>
</tr>
</table>

### 实用新型 / 外观 · 看图与出图

<table width="100%" border="1" cellpadding="12" cellspacing="0">
<tr>
<th width="33%" align="center">外观线稿<br><sub>从产品图自动提炼造型轮廓</sub></th>
<th width="33%" align="center">实用新型线稿<br><sub>从结构图自动生成轮廓与部件序号引出</sub></th>
<th width="34%" align="center">CAD 三维模型投影<br><sub>从工程模型自动提取等轴测等多视角</sub></th>
</tr>
<tr>
<td width="33%" valign="top" align="center">
<img src="docs/效果例-外观专利线稿.png" alt="外观辅助线稿：产品造型黑白线稿示意" width="100%" />
</td>
<td width="33%" valign="top" align="center">
<img src="docs/效果例-实用新型专利线稿含部件序号引出线.png" alt="实用新型辅助线稿：结构线稿与部件序号引出线" width="100%" />
</td>
<td width="34%" valign="top" align="center">
<img src="docs/效果例-cad提取等轴测投影图.png" alt="CAD 三维模型等轴测投影：从工程模型自动提取多视角示意" width="100%" />
</td>
</tr>
</table>

### 专利通俗解读

<table width="100%" border="1" cellpadding="12" cellspacing="0">
<tr>
<th width="50%" align="center">Obsidian 关系图<br><sub>知识图谱与多色节点</sub></th>
<th width="50%" align="center">解读 Canvas<br><sub>叙事故事线 · 术语 · 公开线索</sub></th>
</tr>
<tr>
<td width="50%" valign="top" align="center">
<img src="docs/效果例-obs图谱.jpg" alt="Obsidian 关系图：解读笔记、术语与 Canvas 知识图谱" width="100%" />
</td>
<td width="50%" valign="top" align="center">
<img src="docs/效果例-解读.jpg" alt="专利解读 Canvas：叙事、权要、术语与公开线索图谱" width="100%" />
</td>
</tr>
</table>

---

## 子技能列表

<!-- 技能单行（防 code 在连字符处折行）；名称/详情收紧；触发可换行；剩余给能力。整表 width=100%，不要撑出横向滚动条 -->
<table width="100%">
<colgroup>
<col width="22%">
<col width="10%">
<col>
<col width="18%">
<col width="6%">
</colgroup>
<thead>
<tr>
<th align="left" nowrap>技能</th>
<th align="left" nowrap>名称</th>
<th align="left">能力</th>
<th align="left">触发</th>
<th align="left" nowrap>详情</th>
</tr>
</thead>
<tbody>
<tr>
<td nowrap><a href="skills/patent-disclosure/README.md"><code style="white-space:nowrap">patent-disclosure</code></a></td>
<td nowrap>交底书编写</td>
<td>不会写专利也没关系：材料丢进来，挖出真正能保护的点、查一圈在先技术，直接变成能交差的交底书（发明 / 实用新型 / 外观分套模板）</td>
<td>「交底书」</td>
<td nowrap><a href="skills/patent-disclosure/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-application/README.md"><code style="white-space:nowrap">patent-application</code></a></td>
<td nowrap>申请文件</td>
<td>交底别再停在「给所里看的草稿」——一口气改成权要、说明书、摘要和黑白附图，说不清的进问题清单，不卡死整套文件</td>
<td>「申请文件」· 「申请底稿」</td>
<td nowrap><a href="skills/patent-application/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-docket/README.md"><code style="white-space:nowrap">patent-docket</code></a></td>
<td nowrap>案卷会稿</td>
<td>角色扮演交底工程师 vs 专利代理师：自主多轮规划工作流，材料一丢就出交底和申请，清单最多对打三轮，缺事实就问、绝不瞎编</td>
<td>「交底申请一起做」· 「从零出交底和申请」</td>
<td nowrap><a href="skills/patent-docket/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-reader/README.md"><code style="white-space:nowrap">patent-reader</code></a></td>
<td nowrap>通俗解读</td>
<td>专利全文读不下去：公开号或 PDF 丢进来，换成普通人能看懂的笔记和图谱；推进 Obsidian 后能串起多件专利关联、画出专利地图</td>
<td>「读专利」</td>
<td nowrap><a href="skills/patent-reader/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-oa/README.md"><code style="white-space:nowrap">patent-oa</code></a></td>
<td nowrap>审查答复辅助</td>
<td>审查意见别对着发懵：拆条款问答、起草答复稿；个人从业经验和实务书专家技巧蒸馏进库，RAG 检索增强辅助答复</td>
<td>「审查答复」· 「审查意见」</td>
<td nowrap><a href="skills/patent-oa/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-search/README.md"><code style="white-space:nowrap">patent-search</code></a></td>
<td nowrap>著录检索</td>
<td>人名、公司、分类号照查；更能扔一张产品图或一段权要，倒推出检索式去翻公布公告</td>
<td>「著录检索」</td>
<td nowrap><a href="skills/patent-search/README.md">详情</a></td>
</tr>
<tr>
<td nowrap><a href="skills/patent-exam-policy/README.md"><code style="white-space:nowrap">patent-exam-policy</code></a></td>
<td nowrap>政策简报</td>
<td>对照国知局官网近期政策消息出人话简报，分析技能里哪些交底技巧、申请书式可能过时，审查口径一变就能跟上</td>
<td>「政策简报」· 「政策雷达」</td>
<td nowrap><a href="skills/patent-exam-policy/README.md">详情</a></td>
</tr>
</tbody>
</table>

---

## 环境注意：国知局公布站 WAF 退避策略

`epub.cnipa.gov.cn`（中国专利公布公告站）部署了 WAF / 反爬，可能对部分 IP 段、数据中心出口 IP 或高频请求返回 `Page.goto Timeout`（默认 120s）或 403 / 503。这是站点侧拦截，**不是脚本 bug**——不要因此反复重装 playwright / chromium，也不要在同一 IP 上短时间多次重试（可能触发更严的限速）。

**退避策略**：

- **单次 `Page.goto` 超时（120s 默认）→ 本会话不再重试**，直接进入 `prior_art_search.md` **§B WebSearch 降级**，检索流程不中断。
- **多 IP 出口**（VPN / 代理 / 多区域出口）可尝试切换至香港或海外节点后重试一次；切换节点 ≠ 多次重试，每个出口 IP 只给一次机会。
- 浏览器 UA 与 playwright 默认即可；本机 Chrome / Edge / 自带 Chromium 均可，无需额外伪装。
- **备用简化**：把 `--type` 检索词压缩为 1 个词 + 1 个分类号（如 `--type design --class 26-05 台灯`），缩短搜索词以降低 WAF 命中阈值。

被拦时可在 docs/run-log 注明「本次 IP 段被拦」，便于复盘与后续切换出口。

---

## 支持作者

如果这个 Skill 对您有帮助，可以请我喝杯咖啡☕随缘支持，感谢感谢🙏🙏

<table width="70%" border="1" cellpadding="12" cellspacing="0">
<tr>
<th width="40%" align="center">随缘支持</th>
<th width="60%" align="center">Star History</th>
</tr>
<tr>
<td width="40%" valign="middle" align="center">
<img src="docs/thanks.jpg" alt="随缘支持" width="200" />
</td>
<td width="60%" valign="middle" align="center">
<img alt="Star History Chart" src="https://raw.githubusercontent.com/handsomestWei/patent-disclosure-skill/star-history/star-history.svg" width="100%" />
</td>
</tr>
</table>

---

## 参考文档

- [技能入口与 Agent 流程](SKILL.md)（交底 / 申请文件 / 案卷会稿 / 著录检索 / 解读 / 政策简报 / 审查答复）
- [详细安装说明](INSTALL.md)
- [Obsidian 安装与可选社区插件（Windows）](skills/patent-reader/docs/obsidian-setup-guide.md)

---

<div align="center">

MIT License © [handsomestWei](https://github.com/handsomestWei/)

</div>
