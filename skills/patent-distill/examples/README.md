# 专利蒸馏示例

使用前先把全文 PDF 下载到本地，再把本地路径交给 `classify_distill.py`。本目录不附带全文。

## 第二十六届中国专利金奖（2026）

### 信息源

专利号、专利名称、专利权人来自国家知识产权局官网：

- 授奖决定：国家知识产权局《关于第二十六届中国专利奖授奖的决定》（国知发运字〔2026〕26 号），2026-08-28，<https://www.cnipa.gov.cn/art/2026/8/28/art_75_207884.html>
- 获奖名单页：2026-09-02，<https://www.cnipa.gov.cn/art/2026/9/2/art_3701_207973.html>
- 金奖项目名单 PDF（决定的附件 1，30 项）：<https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&filename=b7393bee46894ad386857d009cf97d0d.pdf&showname=%E7%AC%AC%E4%BA%8C%E5%8D%81%E5%85%AD%E5%B1%8A%E4%B8%AD%E5%9B%BD%E4%B8%93%E5%88%A9%E9%87%91%E5%A5%96%E9%A1%B9%E7%9B%AE%E5%90%8D%E5%8D%95.pdf>

授权公告号不是授奖决定正文里的栏。下表的授权公告号，是用名单中的专利号于 2026-11-26 在 Google Patents 检索后，取返回的中国发明授权文献号。名称、专利权人仍以国知局名单为准。

全文下载两个入口都写在表里：

- 国知局专利公布公告：<http://epub.cnipa.gov.cn/patent/{授权公告号}>
- Google Patents 中文详情：<https://patents.google.com/patent/{授权公告号}/zh>

公布公告页打不开时，打开 <http://epub.cnipa.gov.cn/> ，用申请号（专利号去掉 ZL）检索后再下载。

### 金奖 30 项

专利权人栏在名单有多名权利人时写第一权利人并加「等」，完整名单以附件 PDF 为准。

| 序号 | 专利号 | 授权公告号 | 专利名称 | 专利权人 | 国知局 | Google |
|------|--------|------------|----------|----------|--------|--------|
| 1 | ZL202211440033.9 | CN115720365B | 用于无线通信的方法和设备 | 中兴通讯股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN115720365B) | [详情](https://patents.google.com/patent/CN115720365B/zh) |
| 2 | ZL202111017143.X | CN113649687B | 一种基于层间差异的激光加工后壁组合防护方法及系统 | 西安交通大学 | [公布公告](http://epub.cnipa.gov.cn/patent/CN113649687B) | [详情](https://patents.google.com/patent/CN113649687B/zh) |
| 3 | ZL202110814664.1 | CN113595093B | 一种新能源电站无功电压自动控制方法、装置及存储介质 | 南方电网科学研究院有限责任公司等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN113595093B) | [详情](https://patents.google.com/patent/CN113595093B/zh) |
| 4 | ZL202110633003.9 | CN113314261B | 柔性直流海缆 | 中天科技海缆股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN113314261B) | [详情](https://patents.google.com/patent/CN113314261B/zh) |
| 5 | ZL202110264992.9 | CN112977554B | 基于便携式安全终端的轨道交通资源处理方法及系统 | 卡斯柯信号有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112977554B) | [详情](https://patents.google.com/patent/CN112977554B/zh) |
| 6 | ZL202110211198.8 | CN112831013B | 一种功能化聚氨酯及其制备方法和应用 | 中国科学院长春应用化学研究所等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112831013B) | [详情](https://patents.google.com/patent/CN112831013B/zh) |
| 7 | ZL202080036185.5 | CN114207105B | 用于检测核酸空间信息的阵列及检测方法 | 深圳华大生命科学研究院等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN114207105B) | [详情](https://patents.google.com/patent/CN114207105B/zh) |
| 8 | ZL202080028115.5 | CN113661547B | 核电厂严重事故的应对安全系统及其控制方法 | 中广核研究院有限公司等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN113661547B) | [详情](https://patents.google.com/patent/CN113661547B/zh) |
| 9 | ZL202011542637.5 | CN112540831B | 虚拟可信环境加载、运行方法、数据处理及安全处理装置 | 海光信息技术股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112540831B) | [详情](https://patents.google.com/patent/CN112540831B/zh) |
| 10 | ZL202011238787.7 | CN112360466B | 一种适用于软土层的下沉式竖井掘进机 | 中铁十五局集团有限公司等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112360466B) | [详情](https://patents.google.com/patent/CN112360466B/zh) |
| 11 | ZL202011043657.8 | CN112360501B | 临时支护与钻注一体化锚杆复合支护系统及施工方法 | 中煤科工开采研究院有限公司等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112360501B) | [详情](https://patents.google.com/patent/CN112360501B/zh) |
| 12 | ZL202011017592.X | CN112023603B | 适合摆动/启停复杂工况的船舶尾气洗涤净化系统及方法 | 浙江大学 | [公布公告](http://epub.cnipa.gov.cn/patent/CN112023603B) | [详情](https://patents.google.com/patent/CN112023603B/zh) |
| 13 | ZL201911403452.3 | CN111191777B | 一种神经网络处理器及其控制方法 | 深圳云天励飞技术股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN111191777B) | [详情](https://patents.google.com/patent/CN111191777B/zh) |
| 14 | ZL201910872892.7 | CN110723316B | 一种 SGCMG 的框架角速度确定方法 | 北京控制工程研究所 | [公布公告](http://epub.cnipa.gov.cn/patent/CN110723316B) | [详情](https://patents.google.com/patent/CN110723316B/zh) |
| 15 | ZL201910535447.1 | CN110264540B | 一种并行单像素成像方法 | 北京航空航天大学 | [公布公告](http://epub.cnipa.gov.cn/patent/CN110264540B) | [详情](https://patents.google.com/patent/CN110264540B/zh) |
| 16 | ZL201811438582.6 | CN109593126B | 多肽、其生产方法和用途 | 山西锦波生物医药股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN109593126B) | [详情](https://patents.google.com/patent/CN109593126B/zh) |
| 17 | ZL201810392841.X | CN110416047B | 射频阻抗匹配的方法及装置、半导体处理设备 | 北京北方华创微电子装备有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN110416047B) | [详情](https://patents.google.com/patent/CN110416047B/zh) |
| 18 | ZL201810114605.1 | CN108124374B | 连续波慢引出同步加速器 | 中国科学院近代物理研究所 | [公布公告](http://epub.cnipa.gov.cn/patent/CN108124374B) | [详情](https://patents.google.com/patent/CN108124374B/zh) |
| 19 | ZL201810046574.0 | CN110049386B | 通信网络及相关设备 | 华为技术有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN110049386B) | [详情](https://patents.google.com/patent/CN110049386B/zh) |
| 20 | ZL201780096225.3 | CN111344105B | 一种原位合成金属覆层药芯银钎料及其制备方法、焊接方法和连接体 | 中国机械总院集团郑州机械研究所有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN111344105B) | [详情](https://patents.google.com/patent/CN111344105B/zh) |
| 21 | ZL201780080278.6 | CN110177810B | 抗 PCSK9 抗体及其用途 | 信达生物制药（苏州）有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN110177810B) | [详情](https://patents.google.com/patent/CN110177810B/zh) |
| 22 | ZL201710018512.4 | CN106708051B | 基于二维码的导航系统和方法、导航标记物及导航控制器 | 北京极智嘉科技股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN106708051B) | [详情](https://patents.google.com/patent/CN106708051B/zh) |
| 23 | ZL201618005172.8 | CN117413640B | 新型链式弹药输送装置 | 南京理工大学 | [公布公告](http://epub.cnipa.gov.cn/patent/CN117413640B) | [详情](https://patents.google.com/patent/CN117413640B/zh) |
| 24 | ZL201610859906.8 | CN106501802B | 高分辨率多维协同昆虫迁飞雷达测量仪 | 北京理工大学 | [公布公告](http://epub.cnipa.gov.cn/patent/CN106501802B) | [详情](https://patents.google.com/patent/CN106501802B/zh) |
| 25 | ZL201610144243.1 | CN107196982B | 一种用户请求的处理方法和装置 | 阿里云计算有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN107196982B) | [详情](https://patents.google.com/patent/CN107196982B/zh) |
| 26 | ZL201580067116.X | CN107405593B | 一种烯烃聚合装置和烯烃聚合方法 | 中国石油化工股份有限公司等 | [公布公告](http://epub.cnipa.gov.cn/patent/CN107405593B) | [详情](https://patents.google.com/patent/CN107405593B/zh) |
| 27 | ZL201210571084.5 | CN103896768B | 一种制备乙酸甲酯的方法 | 延长中科（大连）能源科技股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN103896768B) | [详情](https://patents.google.com/patent/CN103896768B/zh) |
| 28 | ZL201180057513.0 | CN103298806B | 取代的哒嗪羧酰胺化合物 | 贝达药业股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN103298806B) | [详情](https://patents.google.com/patent/CN103298806B/zh) |
| 29 | ZL201180003990.9 | CN102686591B | 酞嗪酮类衍生物、其制备方法及其在医药上的应用 | 江苏恒瑞医药股份有限公司 | [公布公告](http://epub.cnipa.gov.cn/patent/CN102686591B) | [详情](https://patents.google.com/patent/CN102686591B/zh) |
| 30 | ZL200810233583.7 | CN101402944B | 一种 EV-71 病毒毒种、人用灭活疫苗及其制备方法 | 中国医学科学院医学生物学研究所 | [公布公告](http://epub.cnipa.gov.cn/patent/CN101402944B) | [详情](https://patents.google.com/patent/CN101402944B/zh) |

### 试跑

可先下载序号 1、9、13、25 四件授权公告。脚本会按案件各写一份思路观察，不把这四份并成文风。

```bash
python skills/patent-distill/tools/classify_distill.py a.pdf b.pdf c.pdf d.pdf
```
