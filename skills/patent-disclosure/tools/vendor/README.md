# 内置 mermaid（供 Playwright 出图，无需 Node / mmdc）

| 文件 | 版本 | 来源 |
|------|------|------|
| `mermaid.min.js` | **11.4.1** | https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js |

与历史 `@mermaid-js/mermaid-cli` 11.4.x 同系列。出图由 `tools/mermaid_render.py` 经 Playwright 加载本文件，**禁止**运行时从 CDN 再拉。

**许可证**：`mermaid.min.js` 为 [MermaidJS](https://github.com/mermaid-js/mermaid) 发布，**MIT License**（© 2014–2024 MermaidJS，全文见本目录 [`LICENSE.mermaid`](LICENSE.mermaid)）。上游 dist 压缩文件未内嵌版权横幅，随包携带本许可即满足 MIT 再分发要求；再分发本技能时须连同本文件一起发布。

升级时请同步改本表版本号，并替换 `mermaid.min.js`。
