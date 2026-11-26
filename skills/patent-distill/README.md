# 专利蒸馏

从已有申请里合并文风。思路按案件拆开，用同案交底对照权要。

<table>
<colgroup>
<col width="1%">
<col>
</colgroup>
<thead>
<tr><th align="left" nowrap width="1%">能力</th><th align="left">说明</th></tr>
</thead>
<tbody>
<tr><td nowrap width="1%"><strong>文风</strong></td><td>同一专利类型的多份申请合并成一份。记下多份共有的章节口气；只出现一次的标成不稳定</td></tr>
<tr><td nowrap width="1%"><strong>思路</strong></td><td>交底里的点对照最终权要：进独权、进从属、只留说明书，还是申请时没写。机器读 <code>playbook.yaml</code></td></tr>
<tr><td nowrap width="1%"><strong>观察和推测分开</strong></td><td>看得到的切法才能进入 playbook。动机和「为什么不申请」留在观察稿的推测节</td></tr>
<tr><td nowrap width="1%"><strong>产出</strong></td><td>目录是 <code>outputs/patent-distill/{档案}/</code></td></tr>
</tbody>
</table>

把文件路径丢进来即可。脚本识别交底、申请文件和已公开专利，并识别发明、实用新型或外观。申请文件合并为文风，思路按案件写入 `cases/`。产物 → `outputs/patent-distill/`。

示例见 [examples/README.md](examples/README.md)：第二十六届中国专利金奖 30 项的专利号、授权公告号，以及国知局授奖决定链接。使用前先从国知局公布公告或 Google Patents 把全文下载到本地。
