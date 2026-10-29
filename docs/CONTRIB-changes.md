# 贡献说明 · 本次改造记录

> 本文件记录对上游 `handsomestWei/patent-disclosure-skill` 的**本地贡献内容**，供 PR 描述 / commit message / 审阅参考使用。
> 不改变上游 MIT 许可；原作者版权声明随包保留（见根 `LICENSE` 与 `README.md` 页脚）。

## 一、新增子技能

### `skills/patent-application`（申请文件四件套）
- 把已有交底改写成权利要求书 / 说明书 / 摘要 / 附图四件套，含 `claim_tree` / `application_plan` 契约 schema、门禁、问题清单、迭代另存。
- **权要写法两式择优、按案自洽**：`claim_style: numbered`（默认，独权「步骤1，…」贯通，机器可校验）| `unnumbered`（独权分号连接不编号、实施例 S1）。两式不得混用；依据真实公布文本（如 CN119686739A / CN122949635A）沉淀风格。
- 背景技术叙述式默认，交底明确记载最近对比件时可点名一件写透。
- 校验链：`audit_claims.py`（权要结构/多引展开）、`check_support.py`（权要↔说明书↔附图对照，`--case-dir` 连交底 schema 交叉核对）、`plan_figures.py`（图型决策，剖视/爆炸/多状态无源图挂 pending）。

### `skills/patent-chart`（权利要求对照表）
- 独权/从权特征拆解，逐格比对对比文件/产品/标准，附证据与强弱；`invalidity` / `fto` / `infringement` / `oa` 场景分栏。
- 主交付 `对照表-{场景}-{时间戳}.xlsx` + `chart.json` 底稿；可选 `--md` 预览（Obsidian 阅读版，主交付仍是 xlsx）。
- **不构成法律意见**，不出授权/无效结论。

## 二、合规补强

- **专利代理业务资质**：根 `SKILL.md`「合规边界」节 + `README.md`「使用边界与合规」+ `patent-application` / `patent-oa` / `patent-docket` 三包护栏——在中国，代为撰写申请文件、代为办理申请、代为答复审查意见属专利代理业务（《专利代理条例》第 9、24 条），须由有执业许可的代理机构及执业证代理师办理；本技能产出为内部底稿，递交前应经有资质代理师复核。
- **vendored mermaid 许可**：随包新增 `vendor/LICENSE.mermaid`（MermaidJS MIT 全文），`vendor/README.md` 补许可证段——满足 MIT 再分发要求。
- **国知局礼貌访问**：`cnipa_crawler.py` 内置约 800ms 页间延迟、本机浏览器 UA、跨会话冷却；`INSTALL.md` 加合规提示（限个人研究与低频、勿高频/批量商业抓取）。
- **GUI 下载全文 PDF**：`patent_pdf_sources.yaml` / `gui_download_cnipa.md` / `patent_plain_reader.md` / `INSTALL.md` / 根 `SKILL.md` 五处一致口径——专利全文为法定公开信息，真人浏览器 GUI 下载属正常人工访问（过验证码为真人输入、非绕过技术措施）；保持人工节奏、控制单次数量、勿自动化批量；仅限个人研究与内部流程，勿再分发/商业建库，不绕过登录/付费访问控制（付费/账号库已排除在默认链路外）；**下载前置**——用户须先自行登录其国知局账户（单行本下载需登录态），技能不代登录、不接触/不保存凭据，登录态保留在用户浏览器会话，登录完成后技能才接管 GUI 操作。

## 三、校验豁口修复

- `check_support.py`：新增 `--case-dir`（交底 `structure_schema` 交叉核对）、`claim_style` 双式校验（`CLAIM_STYLE_MISMATCH` / `STEP_STYLE_UNVERIFIED`）、非渲染图型缺图 WARNING。
- `plan_figures.py`：发明也挂 `source: pending`（原只实用新型）。
- `audit_claims.py`：多引解析修复（「权利要求1或2」「权利要求1、2或3」「权利要求1至4」）。
- 测试：77 passed / 1 skipped（缺 Pillow 可选依赖）。

## 四、本目录非 git 仓库的推送提示

本目录未初始化 git。推送前：`git init` 后按 `.gitignore` 提交（`outputs/`、`disclosures/`、`tmp/`、`__pycache__/`、`.venv/` 均被忽略，且当前不存在）；**不要**提交任何用户产出目录。真实本机路径均已改为占位符（如 `%USERPROFILE%\Downloads`）；secrets 只写用户文档目录、不入仓库。
