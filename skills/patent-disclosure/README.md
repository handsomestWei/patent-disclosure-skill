# 专利交底书编写

支持 **发明**、**实用新型**、**外观设计** 三种专利类型（未指定时默认发明）。
<!-- 使用 HTML 表格：避免 GitHub 管道表把左列挤窄 -->
<table>
<colgroup>
<col width="1%">
<col>
</colgroup>
<thead>
<tr><th align="left" nowrap width="1%">能力</th><th align="left">说明</th></tr>
</thead>
<tbody>
<tr><td nowrap width="1%"><strong>专利类型</strong></td><td>发明 / 实用新型 / 外观设计<strong>分模板成文</strong></td></tr>
<tr><td nowrap width="1%"><strong>项目扫描</strong></td><td>按优先级读文档和代码；Word / PPT 会先转成 Markdown 再扫</td></tr>
<tr><td nowrap width="1%"><strong>外观线稿</strong></td><td>成文前选用或生成产品线稿，与干净实拍一并写入交底</td></tr>
<tr><td nowrap width="1%"><strong>实用结构线稿</strong></td><td>成文前选用或生成结构线稿，并叠部件序号</td></tr>
<tr><td nowrap width="1%"><strong>专利点</strong></td><td>候选点讨论与融合</td></tr>
<tr><td nowrap width="1%"><strong>查新</strong></td><td><strong>优先</strong> <a href="http://epub.cnipa.gov.cn/">国知局 · 中国专利公布公告</a>；异常或无果时再换其他检索。著录写入交底第一章</td></tr>
<tr><td nowrap width="1%"><strong>交底书成稿</strong></td><td>脱敏模版；发明用框图；实用/外观嵌结构图或视图；定稿可出 Word</td></tr>
<tr><td nowrap width="1%"><strong>交付命名</strong></td><td>按案件名和时间戳输出 Markdown 与同名 Word</td></tr>
<tr><td nowrap width="1%"><strong>自检 / 迭代</strong></td><td>逻辑与公式自检（不写入正文）；补材料或纠错会另存新文件并留下修订记录</td></tr>
<tr><td nowrap width="1%"><strong>蒸馏参考（旁路）</strong></td><td>点名蒸馏档，或说「参考某几份专利的思路」时，按其切法划分第五章必要与优选特征；和本案不合的条目跳过，交付时说明用了哪些</td></tr>
<tr><td nowrap width="1%"><strong>保护型 1+N（旁路）</strong></td><td>首篇定稿后先问要不要做布局。答应后：技术分解 → 突围路径 → 技术功效矩阵 → 立项说明（family.yaml + 专利布局.md，含立项校验表），确认后再分件写交底。只护自己的核心，本趟只出中国交底；校验看能不能拆开写，不是高价值达标</td></tr>
</tbody>
</table>

使用示例：

- 发明：[批任务调度](examples/example_batch_job_scheduler/)（扫 `knowledge/`）—「按发明写交底，项目路径 …/knowledge/」
- 实用新型：[汽车集成式电驱桥](examples/example_utility_model_ev_powertrain/) —「实用新型交底，材料在 …/example_utility_model_ev_powertrain/」
- 外观设计：[折臂台灯](examples/example_design_desk_lamp/) —「外观设计交底，材料在 …/example_design_desk_lamp/」
