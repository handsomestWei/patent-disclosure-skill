# 交接合同（路径，不是摘要）

跨交底 / 申请包时，**只允许**把下列内容写入 `docket.yaml` 与对话中的派工说明。

## 必传

- `case_id`
- `patent_type`（invention / utility_model / design）
- 本轮 `phase` 与 `round`
- **目录或文件的工作区相对路径**（交底目录、交底 md、申请目录、问题清单、材料目录）
- 本轮允许处理的 **issue id 列表**（如 `I-03,I-07`）及 disposition
- 用户点名或经根路由「组合路由」产出的蒸馏档路径（有则传，记在 `paths.distill_refs`）；交底手与申请手都传

## 禁止传

- 把交底第三章「概括成要点」代替原文路径
- 把独权「改写后」交给下一手而不给申请目录
- 「请补全合理结构 / 常见连接方式」等诱导编造
- 子 agent brief、聊天长摘要当技术事实

进入交底或申请包之后：该包 **`Read` 自己的 `SKILL.md`**，并以磁盘上的 md / yaml / 图为准。协调者回到案卷时 **`Read` 新产物路径**，不要凭记忆核对。

## 派工后回案卷

1. 把新路径写进 `docket.yaml` 的 `paths.*`
2. `python skills/patent-docket/tools/validate_docket.py --yaml …`
3. `python skills/patent-docket/tools/emit_tracker.py --yaml …`
4. 再 `Read` 下一 phase 对应 prompt
