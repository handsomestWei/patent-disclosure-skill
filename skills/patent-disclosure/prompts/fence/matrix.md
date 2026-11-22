# 保护型 1+N · 技术功效矩阵

突围已落盘。做**手段 × 功效**矩阵，用来看哪一格值得立项、哪一格已经挤。

## 格子

- 行：`means`（来自分解的模块/结构/步骤，用手段词）  
- 列：`effects`（交底里写过的技术效果，用功效词）  
- 格：`density` 只能是 `dense` | `sparse` | `unchecked`

**未检索不得标空白，也不得写成蓝海。** 没查的格子必须 `unchecked`。

## 填密度（旁路专用，主路径 Step 5 不动）

对「手段词 + 功效词」：主路径已走 A0 则同样用该 MCP；否则本包 `tools/crawl/cnipa_epub_search.py`，**一词一页**。

```bash
python skills/patent-disclosure/tools/crawl/cnipa_epub_search.py --type invention 手段词 功效词
```

读 MCP 命中或 `EPUB_NOTE:` / `EPUB_HITS_JSON:`：命中多且方案接近 → `dense`；有区别空间 → `sparse`；检索失败或没跑 → `unchecked`。不要把首篇 1.1 对比清单整段复制进矩阵。

`dense` 的格子后面**不得** `write_this_round`。可以写进方案，但这一轮先放下。

落盘 `outputs/{案件}/fence/matrix.yaml`：

```yaml
version: 1
means:
  - id: m1
    label: 双轴铰链锁合
effects:
  - id: e1
    label: 单手开合仍保持预紧
cells:
  - mean: m1
    effect: e1
    density: sparse
    node_id: P1   # 立项后回填；此时可空
```

校验：

```bash
python skills/patent-disclosure/tools/fence/check_layout.py --matrix outputs/{案件}/fence/matrix.yaml
```

成功须见 `LAYOUT_OK:matrix`。然后 **`Read` `plan.md`**。
