# 专利申请文件

把已有交底改写成申请文件；须**点名**并给出**交底产出目录**。
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
<tr><td nowrap width="1%"><strong>专利类型</strong></td><td>发明 / 实用新型出权利要求书、说明书、摘要和黑白附图；外观走外观申请文件</td></tr>
<tr><td nowrap width="1%"><strong>交底材料</strong></td><td>须指定交底产出目录；缺交底书 / schema / 线稿则终止，引导先补交底</td></tr>
<tr><td nowrap width="1%"><strong>权利要求</strong></td><td>从属按层展开并与实施例对照；权要写法两式择优（<code>numbered</code> 步骤N 编号 / <code>unnumbered</code> 不编号+实施例 S1），全稿同口径并记入 <code>application_plan.claim_style</code></td></tr>
<tr><td nowrap width="1%"><strong>附图图型</strong></td><td>按权要选定剖视/爆炸/流程/框图/多状态，写入产出 <code>figures/figure_plan.yaml</code></td></tr>
<tr><td nowrap width="1%"><strong>问题清单</strong></td><td>内容争议写入问题清单，不阻塞主文件；交付末尾提醒</td></tr>
<tr><td nowrap width="1%"><strong>迭代</strong></td><td>已有产出上改稿则另存新时间戳目录</td></tr>
</tbody>
</table>

使用示例：「申请文件，交底在 outputs/…」——指向已交付的 `outputs/{案件标识}/`材料目录。
