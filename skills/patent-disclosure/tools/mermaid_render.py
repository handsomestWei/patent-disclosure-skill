#!/usr/bin/env python
"""
将 Markdown 中的 **mermaid** 围栏转为 PNG，再写定稿 `.md` 并默认生成 Word。

**公式**：默认 **不** 调用 ``math_render.py``（避免强制 matplotlib）。Word 公式走 OMML；失败留原文。用户确认后可用 ``--math`` 预渲染公式 PNG。**Mermaid** 围栏块逐块渲染为 PNG，**保留** `` ```mermaid`` … `` ``` `` 源码，并在其后追加 HTML 注释
``<!-- ![图示](相对路径) -->``（预览不显示图），便于 ``md_to_docx.py`` 将图嵌入 Word（Word **仅**嵌 PNG，不写 mermaid 代码块）。

**Mermaid 渲染后端**：Playwright + 仓库内置 ``vendor/mermaid.min.js``。与国知局查新共用
``browser.py``（系统 Chrome → Edge → 自带 Chromium）。**不**调用 Node / mmdc / ``npx``。

交底书 **3.2 系统框图**与 **3.4 流程图**均使用 fenced mermaid；**不要** ASCII「文字箭头」流程图或框图。

**降级**：某一围栏生图失败时**不中断**：该处**保留原** `` ```mermaid`` … `` ``` `` 围栏；其余块照常渲染。仍写出 .md 并**照常尝试** ``md_to_docx.py``（Word 中失败块以代码块形式出现）。无可用浏览器时同样保留围栏，不阻塞 Markdown 交付。

**行内公式分隔符**：出 Word 前用 ``latex_delimiters.py`` 扫描。若写成 ``(M_{\\mathrm{total}})`` 这类普通括号包 LaTeX，则 **仍写 .md、跳过 Word**（``LATEX_DELIM: hits=`` / ``DOCX: ok=0 reason=latex_delim``）。须改成 ``\\(...\\)`` 后对**当次时间戳 md**重跑，禁止用未改正的 ``draft.md`` 出交付 Word。

**清晰度**：默认视口 1400×1050、``device_scale_factor=2``。可用 ``--mmdc-scale`` / ``--mmdc-width`` / ``--mmdc-height``（历史参数名，语义不变）。

用法：
  python tools/mermaid_render.py -i draft.md -o disclosure.md
  python tools/mermaid_render.py -i draft.md -o out/disclosure.md --docx out/custom.docx
  python tools/mermaid_render.py -i draft.md -o disclosure.md --no-docx
  python tools/mermaid_render.py -i draft.md -o disclosure.md --math   # 公式 PNG，须 matplotlib
  python tools/mermaid_render.py -i draft.md -o disclosure.md --ai-figures outputs/case/figure_jobs.json

**生图引用**（``--ai-figures``，可选）：围栏源码 sha1 命中 ``figure_jobs.py`` 已登记（recorded）的生成图时，
直接复制该图作为本块 PNG，不启动浏览器；未命中（含迭代改过 mermaid 的过期图）按上述 Playwright 本地渲染。
不传该参数时行为不变。流程见 ``prompts/figure_generation.md``。
"""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from browser import install_chromium_hint, install_package_hint, launch_chromium, playwright_installed
from latex_delimiters import find_bare_paren_latex, format_hits_report
from stdio_utf8 import ensure_utf8_stdio, run as run_utf8

_MERMAID_JS = _HERE / "vendor" / "mermaid.min.js"

_STAGE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
html, body { margin: 0; background: #fff; }
#stage { display: inline-block; padding: 16px; background: #fff; }
</style>
</head>
<body>
<div id="stage"></div>
</body>
</html>
"""

_RENDER_JS = """async ({ src, rid }) => {
  try {
    mermaid.initialize({
      startOnLoad: false,
      theme: "default",
      securityLevel: "strict",
      fontFamily: '"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",Arial,sans-serif',
      flowchart: { htmlLabels: true, useMaxWidth: false }
    });
    const { svg } = await mermaid.render(rid, src);
    document.getElementById("stage").innerHTML = svg;
    return null;
  } catch (e) {
    return String(e && e.message ? e.message : e);
  }
}
"""


class _PlaywrightMermaid:
    """一场定稿共用一个浏览器。"""

    def __init__(self, *, scale: float, width: int, height: int) -> None:
        self.scale = scale
        self.width = width
        self.height = height
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._block_i = 0

    def __enter__(self) -> "_PlaywrightMermaid":
        if not _MERMAID_JS.is_file():
            raise RuntimeError(f"缺少内置 mermaid：{_MERMAID_JS}")
        if not playwright_installed():
            raise RuntimeError("未安装 Playwright。" + install_package_hint())
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            self._browser, _label = launch_chromium(self._pw, headless=True)
            self._context = self._browser.new_context(
                viewport={"width": self.width, "height": self.height},
                device_scale_factor=self.scale,
            )
            self._page = self._context.new_page()
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        for closer in (self._context, self._browser):
            if closer is not None:
                try:
                    closer.close()
                except Exception:
                    pass
        self._context = None
        self._browser = None
        self._page = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def __exit__(self, *exc: object) -> None:
        self.close()

    def render_one(self, mermaid_source: str, png_path: Path) -> None:
        if self._page is None:
            raise RuntimeError("浏览器未启动")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        self._block_i += 1
        page = self._page
        page.set_content(_STAGE_HTML, wait_until="domcontentloaded")
        page.add_script_tag(path=str(_MERMAID_JS))
        page.wait_for_function("() => typeof mermaid !== 'undefined'", timeout=30_000)
        err = page.evaluate(
            _RENDER_JS,
            {"src": mermaid_source.strip(), "rid": f"mmd{self._block_i}"},
        )
        if err:
            raise RuntimeError(err)
        page.locator("#stage").screenshot(path=str(png_path), type="png", timeout=60_000)


_MMD_START = re.compile(r"^```mermaid\s*$", re.IGNORECASE)
_MMD_END = re.compile(r"^```\s*$")
_MERMAID_HIDDEN_COMMENT_RE = re.compile(
    r"<!--\s*!\[([^\]]*)\]\(([^)]+)\)\s*-->"
)
_STEP_NODE_RE = re.compile(
    r"(?P<id>[A-Za-z]+\d+)\s*"
    r"(?P<lbr>\[|\(|\{)"
    r"(?:"
    r'(?P<q>["\'])(?P<qlabel>.*?)(?P=q)'
    r"|"
    r"(?P<ulabel>[^\]\)\}]+)"
    r")"
    r"(?P<rbr>\]|\)|\})"
)
_STEP_SHAPE_PAIR = {"[": "]", "(": ")", "{": "}"}


def _label_shows_step_id(label: str, nid: str) -> bool:
    text = label.strip()
    if text == nid:
        return True
    if text.startswith(nid) and (
        len(text) == len(nid) or text[len(nid)] in " \u3000:：.-/、"
    ):
        return True
    return False


def _quote_mermaid_label(text: str) -> str:
    if '"' not in text:
        return f'"{text}"'
    if "'" not in text:
        return f"'{text}'"
    return '"' + text.replace('"', "'") + '"'


def ensure_step_ids_in_visible_labels(src: str) -> tuple[str, int]:
    """把 S1[采集…] 写成 S1["S1 采集…"]，使 PNG 可见步骤号。id 本身不出图。"""

    n_fix = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal n_fix
        nid = match.group("id")
        lbr = match.group("lbr")
        rbr = match.group("rbr")
        if _STEP_SHAPE_PAIR.get(lbr) != rbr:
            return match.group(0)
        label = match.group("qlabel")
        if label is None:
            label = match.group("ulabel") or ""
        if _label_shows_step_id(label, nid):
            return match.group(0)
        n_fix += 1
        return f"{nid}{lbr}{_quote_mermaid_label(f'{nid} {label.strip()}')}{rbr}"

    out_lines: list[str] = []
    for raw in src.splitlines(keepends=True):
        core = raw.rstrip("\r\n")
        nl = raw[len(core) :]
        stripped = core.lstrip()
        if stripped.startswith("%%") or stripped.startswith("subgraph "):
            out_lines.append(raw)
            continue
        out_lines.append(_STEP_NODE_RE.sub(repl, core) + nl)
    return "".join(out_lines), n_fix


def _is_mermaid_figure_comment(alt: str, src: str) -> bool:
    s = src.strip().replace("\\", "/")
    if "mermaid_figures" in s:
        return True
    a = alt.strip()
    return a.startswith("图示") or a.startswith("图 ")


def render_markdown_mermaid(
    md_text: str,
    *,
    out_md_path: Path,
    assets_rel: str,
    mmdc_scale: float = 2.0,
    mmdc_width: int = 1400,
    mmdc_height: int = 1050,
    render_one: Callable[[str, Path], None] | None = None,
) -> tuple[str, int, int]:
    """
    返回 (新 markdown 全文, 成功转为 PNG 的块数, 生图失败而保留围栏的块数)。
    ``render_one`` 仅供测试注入；默认 Playwright + 内置 mermaid.js。
    """
    lines = md_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    ok = 0
    failed = 0
    block_idx = 0
    assets_dir = out_md_path.parent / assets_rel

    own_renderer: _PlaywrightMermaid | None = None
    renderer_error: str | None = None
    if render_one is None:
        try:
            own_renderer = _PlaywrightMermaid(
                scale=mmdc_scale, width=mmdc_width, height=mmdc_height
            )
            own_renderer.__enter__()
            render_one = own_renderer.render_one
        except Exception as e:
            renderer_error = str(e)
            if "无法启动浏览器" in renderer_error or "Executable" in renderer_error:
                renderer_error = f"{renderer_error} {install_chromium_hint()}"
            print(f"[mermaid_render] 无法启动出图（将保留 mermaid 源码）：{renderer_error}", file=sys.stderr)

    try:
        while i < len(lines):
            line = lines[i]
            if _MMD_START.match(line):
                fence_open = line
                i += 1
                body: list[str] = []
                while i < len(lines) and not _MMD_END.match(lines[i]):
                    body.append(lines[i])
                    i += 1
                closing = lines[i] if i < len(lines) else "```\n"
                if i < len(lines):
                    i += 1

                joined = "".join(body)
                fixed, n_fix = ensure_step_ids_in_visible_labels(joined)
                if n_fix:
                    print(
                        f"[mermaid_render] 第 {block_idx + 1} 个围栏：{n_fix} 处步骤号已写入可见标签"
                        "（S1[文案] → S1[\"S1 文案\"]，否则 PNG 看不到序号）",
                        file=sys.stderr,
                    )
                    if joined.endswith("\n") and not fixed.endswith("\n"):
                        fixed += "\n"
                    body = fixed.splitlines(keepends=True)

                j = i
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines):
                    cm = _MERMAID_HIDDEN_COMMENT_RE.match(lines[j].strip())
                    if cm and _is_mermaid_figure_comment(cm.group(1), cm.group(2)):
                        if n_fix == 0:
                            out.append(fence_open)
                            out.extend(body)
                            if not closing.endswith("\n"):
                                closing = closing + "\n"
                            out.append(closing)
                            while i < j:
                                out.append(lines[i])
                                i += 1
                            out.append(lines[i])
                            i += 1
                            ok += 1
                            continue

                block_idx += 1
                fname = f"fig_{ok + 1:03d}.png"
                png_path = assets_dir / fname
                try:
                    if render_one is None:
                        raise RuntimeError(renderer_error or "无可用 mermaid 渲染器")
                    render_one("".join(body), png_path)
                except Exception as e:
                    failed += 1
                    print(
                        f"[mermaid_render] 第 {block_idx} 个 mermaid 围栏生图失败（已保留源码）：{e}",
                        file=sys.stderr,
                    )
                    out.append(fence_open)
                    out.extend(body)
                    if not closing.endswith("\n"):
                        closing = closing + "\n"
                    out.append(closing)
                    continue
                ok += 1
                rel = f"{assets_rel.strip('/')}/{fname}".replace("\\", "/")
                out.append(fence_open)
                out.extend(body)
                if not closing.endswith("\n"):
                    closing = closing + "\n"
                out.append(closing)
                out.append(f"<!-- ![图示 {ok}]({rel}) -->\n")
                if n_fix:
                    k = i
                    while k < len(lines) and lines[k].strip() == "":
                        k += 1
                    if k < len(lines):
                        cm_old = _MERMAID_HIDDEN_COMMENT_RE.match(lines[k].strip())
                        if cm_old and _is_mermaid_figure_comment(
                            cm_old.group(1), cm_old.group(2)
                        ):
                            i = k + 1
                continue
            out.append(line)
            i += 1
    finally:
        if own_renderer is not None:
            own_renderer.close()

    return "".join(out), ok, failed


class _AiFigureRenderer:
    """``render_one`` that prefers recorded generated figures, else renders locally on demand."""

    def __init__(self, manifest: Path, *, scale: float, width: int, height: int) -> None:
        self.manifest = manifest
        self._kw = {"scale": scale, "width": width, "height": height}
        self._local: _PlaywrightMermaid | None = None
        self._error: str | None = None
        self.hits = 0
        self.misses = 0

    def render_one(self, mermaid_source: str, png_path: Path) -> None:
        import shutil

        from figure_jobs import recorded_image_for_mermaid

        image = recorded_image_for_mermaid(self.manifest, mermaid_source)
        if image is not None:
            png_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image, png_path)
            self.hits += 1
            return
        self.misses += 1
        if self._error:
            raise RuntimeError(self._error)
        if self._local is None:
            try:
                local = _PlaywrightMermaid(**self._kw)
                local.__enter__()
            except Exception as e:
                self._error = f"{e} {install_chromium_hint()}"
                raise RuntimeError(self._error) from e
            self._local = local
        self._local.render_one(mermaid_source, png_path)

    def close(self) -> None:
        if self._local is not None:
            self._local.close()
            self._local = None


def _print_manual_docx_hint(out_md: Path, docx_out: Path, base_dir: Path, md_script: Path) -> None:
    print(
        "提示：可手动将上述 Markdown 转为 Word（需已 pip install -r requirements.txt）：",
        file=sys.stderr,
    )
    if md_script.is_file():
        parts = [
            sys.executable,
            str(md_script),
            "-i",
            str(out_md),
            "-o",
            str(docx_out),
            "--base-dir",
            str(base_dir),
        ]
        print("  " + " ".join(shlex.quote(p) for p in parts), file=sys.stderr)
    else:
        print(
            "  python tools/md_to_docx.py -i <上述.md> -o <输出.docx> --base-dir <.md 所在目录>",
            file=sys.stderr,
        )


def try_write_docx(out_md: Path, docx_out: Path, *, math_render: bool = False) -> bool:
    """
    调用同目录下的 md_to_docx.py。成功返回 True；失败打印警告与手动命令，返回 False。
    """
    tools_dir = Path(__file__).resolve().parent
    md_script = tools_dir / "md_to_docx.py"
    base_dir = out_md.parent
    docx_out.parent.mkdir(parents=True, exist_ok=True)

    if not md_script.is_file():
        print("DOCX: ok=0 error=missing_script", file=sys.stderr)
        print("警告：未找到 md_to_docx.py，跳过 Word。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    cmd = [
        sys.executable,
        str(md_script),
        "-i",
        str(out_md),
        "-o",
        str(docx_out),
        "--base-dir",
        str(base_dir),
    ]
    if math_render:
        cmd.append("--math-render")
    try:
        r = run_utf8(
            cmd,
            capture_output=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("DOCX: ok=0 error=timeout", file=sys.stderr)
        print("警告：生成 Word 超时（300s）。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False
    except OSError as e:
        print("DOCX: ok=0 error=spawn", file=sys.stderr)
        print(f"警告：无法启动 md_to_docx：{e}", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out, file=sys.stderr)
    if err:
        print(err, file=sys.stderr)

    if r.returncode != 0:
        print(f"DOCX: ok=0 exit={r.returncode}", file=sys.stderr)
        print(f"警告：md_to_docx 失败（退出码 {r.returncode}）。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    print("DOCX: ok=1", file=sys.stderr)
    print(f"已写入 Word: {docx_out}", file=sys.stderr)
    return True


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Markdown 内 mermaid 围栏 → PNG（Playwright），默认再生成同名 Word"
    )
    p.add_argument("-i", "--input", required=True, type=Path, help="含 mermaid 围栏的 .md")
    p.add_argument("-o", "--output", required=True, type=Path, help="输出 .md（图片引用）")
    p.add_argument(
        "--assets-dir",
        default="mermaid_figures",
        help="mermaid 生成 PNG 的相对子目录（默认 mermaid_figures）",
    )
    p.add_argument(
        "--docx",
        type=Path,
        default=None,
        metavar="PATH",
        help="输出 .docx 路径（默认与 -o 同主文件名、扩展名 .docx）",
    )
    p.add_argument(
        "--no-docx",
        action="store_true",
        help="不生成 Word，仅输出替换图片后的 Markdown",
    )
    p.add_argument(
        "--math",
        action="store_true",
        help="用 matplotlib 预渲染 LaTeX 公式 PNG（默认跳过；须另装 matplotlib）",
    )
    p.add_argument(
        "--no-math",
        action="store_true",
        help=argparse.SUPPRESS,  # 旧开关；现默认已跳过公式 PNG
    )
    p.add_argument(
        "--math-assets-dir",
        default="math_figures",
        help="公式 PNG 相对 -o 输出 .md 的子目录（默认 math_figures）",
    )
    p.add_argument(
        "--mmdc-scale",
        type=float,
        default=2.0,
        metavar="N",
        help="device_scale_factor（默认 2；越大越清晰但文件更大）",
    )
    p.add_argument(
        "--mmdc-width",
        type=int,
        default=1400,
        metavar="PX",
        help="渲染视口宽度像素（默认 1400）",
    )
    p.add_argument(
        "--mmdc-height",
        type=int,
        default=1050,
        metavar="PX",
        help="渲染视口高度像素（默认 1050）",
    )
    p.add_argument(
        "--ai-figures",
        type=Path,
        default=None,
        metavar="JSON",
        help="figure_jobs.json：围栏 sha1 命中已登记生成图则直接引用，未命中回退本地渲染",
    )
    args = p.parse_args(argv)
    if args.mmdc_scale <= 0:
        print("错误：--mmdc-scale 须为正数", file=sys.stderr)
        return 1
    if args.mmdc_width < 400 or args.mmdc_height < 400:
        print("错误：--mmdc-width / --mmdc-height 建议不小于 400", file=sys.stderr)
        return 1

    in_path = args.input.resolve()
    if not in_path.is_file():
        print(f"错误：找不到输入 {in_path}", file=sys.stderr)
        return 1

    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        md = in_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        md = in_path.read_text(encoding="utf-8", errors="replace")

    math_ok = math_fail = 0
    want_math = bool(getattr(args, "math", False))
    if want_math:
        try:
            from math_render import render_markdown_math

            md, math_ok, math_fail = render_markdown_math(
                md,
                out_md_path=out_path,
                assets_rel=getattr(args, "math_assets_dir", "math_figures"),
            )
            if math_ok or math_fail:
                parts_m = [f"公式：{math_ok} 处已转为 PNG"]
                if math_fail:
                    parts_m.append(f"，{math_fail} 处失败已保留原文")
                print("[mermaid_render] " + "".join(parts_m), file=sys.stderr)
        except ImportError:
            print(
                "[mermaid_render] 未安装 matplotlib，跳过公式 PNG"
                "（用户确认后：pip install matplotlib）",
                file=sys.stderr,
            )

    ai_renderer: _AiFigureRenderer | None = None
    if args.ai_figures is not None:
        ai_renderer = _AiFigureRenderer(
            args.ai_figures.resolve(),
            scale=args.mmdc_scale,
            width=args.mmdc_width,
            height=args.mmdc_height,
        )
    try:
        new_md, n_ok, n_fail = render_markdown_mermaid(
            md,
            out_md_path=out_path,
            assets_rel=args.assets_dir.strip("/\\") or "mermaid_figures",
            mmdc_scale=args.mmdc_scale,
            mmdc_width=args.mmdc_width,
            mmdc_height=args.mmdc_height,
            render_one=ai_renderer.render_one if ai_renderer else None,
        )
    finally:
        if ai_renderer is not None:
            ai_renderer.close()
    if ai_renderer is not None:
        print(
            f"MERMAID: ai_figure_hit={ai_renderer.hits} ai_figure_miss={ai_renderer.misses}",
            file=sys.stderr,
        )

    out_path.write_text(new_md, encoding="utf-8")
    print(f"MERMAID: ok={n_ok} fail={n_fail}", file=sys.stderr)
    parts = [f"已写入 {out_path}（mermaid：{n_ok} 处已转为 PNG"]
    if n_fail:
        parts.append(f"，{n_fail} 处生图失败已保留 fenced 源码")
    parts.append("）")
    print("".join(parts), file=sys.stderr)
    if n_fail:
        print(
            "[mermaid_render] 已继续生成 Markdown"
            + (" 并将尝试 Word" if not args.no_docx else "")
            + "；框图 PNG 可在浏览器可用后重跑本脚本。禁止为出图执行 npm/npx。",
            file=sys.stderr,
        )

    if args.no_docx:
        print("DOCX: skip=1", file=sys.stderr)
        return 0

    delim_hits = find_bare_paren_latex(new_md)
    if delim_hits:
        print(format_hits_report(delim_hits), file=sys.stderr)
        print("DOCX: ok=0 reason=latex_delim", file=sys.stderr)
        print(
            "警告：已跳过 Word。改正行内公式分隔符后，对上述已写出的定稿 .md 重跑本脚本"
            "（或 md_to_docx.py），不要用未改正的草稿出交付 .docx。",
            file=sys.stderr,
        )
        return 0

    docx_path = (
        args.docx.resolve()
        if args.docx is not None
        else out_path.with_suffix(".docx")
    )
    try_write_docx(out_path, docx_path, math_render=want_math)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
