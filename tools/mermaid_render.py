#!/usr/bin/env python3
"""
将 Markdown 中的 **mermaid**（`` ```mermaid`` ``）围栏块逐块渲染为 PNG，
并在输出 Markdown 中用 ``![](相对路径)`` 替换原代码块，便于 ``md_to_docx.py`` 将图嵌入 Word。

**Mermaid 渲染后端（``mmdc``）**检测顺序见 ``_find_mmdc_invocation``：
1. ``tools/node_modules``（``npm install`` 官方 ``@mermaid-js/mermaid-cli``）；
2. **PATH 上的 ``mmdc``**（通常为 ``npm install -g @mermaid-js/mermaid-cli``）；
3. **Node.js + npx** 临时拉取 ``@mermaid-js/mermaid-cli``（无本地安装时）。

交底书 **3.2 系统框图**与 **3.4 流程图**均使用 fenced mermaid；**不要** ASCII「文字箭头」流程图或框图。

**降级**：某一围栏 ``mmdc`` 生图失败时**不中断**：该处**保留原** `` ```mermaid`` … `` ``` `` 围栏；其余块照常渲染。仍写出 .md 并**照常尝试** ``md_to_docx.py``（Word 中失败块以代码块形式出现）。

用法：
  python tools/mermaid_render.py -i draft.md -o disclosure.md
  # 默认在同目录生成 disclosure.docx；失败时 stderr 会给出可复制的 md_to_docx 命令
  python tools/mermaid_render.py -i draft.md -o out/disclosure.md --docx out/custom.docx
  python tools/mermaid_render.py -i draft.md -o disclosure.md --no-docx   # 仅 Markdown

写出 .md 后**默认**调用 ``md_to_docx.py``；Word 失败不导致进程失败（退出码 0），并提示手动转换。
"""
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _local_mmdc() -> tuple[list[str], bool] | None:
    """``tools/npm install`` 后可用 ``node_modules/.bin/mmdc``，避免每次 npx 拉包。"""
    here = Path(__file__).resolve().parent
    if sys.platform == "win32":
        cand = here / "node_modules" / ".bin" / "mmdc.cmd"
    else:
        cand = here / "node_modules" / ".bin" / "mmdc"
    if cand.is_file():
        return [str(cand)], False
    return None


def _find_mmdc_invocation() -> tuple[list[str], bool]:
    """
    返回 (argv 前缀, use_shell)。
    Windows 上 npx 常为 .ps1，无独立 .exe，需 shell=True 调用 ``npx ...``。
    PATH 中的 ``mmdc`` 一般为 npm 全局安装的官方 CLI。
    """
    local = _local_mmdc()
    if local:
        return local
    mmdc = shutil.which("mmdc")
    if mmdc and Path(mmdc).suffix.lower() not in (".ps1",):
        return [mmdc], False
    if sys.platform == "win32":
        return ["npx", "-y", "@mermaid-js/mermaid-cli", "mmdc"], True
    return ["npx", "-y", "@mermaid-js/mermaid-cli", "mmdc"], False


def _render_one_mermaid(mermaid_source: str, png_path: Path, mmdc_base: list[str], *, use_shell: bool) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(mermaid_source.strip() + "\n")
        tmp_path = Path(tmp.name)
    try:
        if use_shell:
            parts = [
                *mmdc_base,
                "-i",
                str(tmp_path),
                "-o",
                str(png_path),
                "-b",
                "white",
            ]
            cmd = " ".join(shlex.quote(p) for p in parts)
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
        else:
            cmd = [
                *mmdc_base,
                "-i",
                str(tmp_path),
                "-o",
                str(png_path),
                "-b",
                "white",
            ]
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            raise RuntimeError(f"mmdc 失败 (exit {r.returncode}): {err[:2000]}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


_MMD_START = re.compile(r"^```mermaid\s*$", re.IGNORECASE)
_MMD_END = re.compile(r"^```\s*$")


def render_markdown_mermaid(
    md_text: str,
    *,
    out_md_path: Path,
    assets_rel: str,
) -> tuple[str, int, int]:
    """
    返回 (新 markdown 全文, 成功转为 PNG 的块数, 生图失败而保留围栏的块数)。
    资源目录为 out_md_path.parent / assets_rel。
    失败的块原样写回 `` ```mermaid`` … `` ``` ``，不抛错。
    """
    lines = md_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    ok = 0
    failed = 0
    block_idx = 0
    assets_dir = out_md_path.parent / assets_rel
    mmdc_base, use_shell = _find_mmdc_invocation()

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
            block_idx += 1
            fname = f"fig_{ok + 1:03d}.png"
            png_path = assets_dir / fname
            try:
                _render_one_mermaid("".join(body), png_path, mmdc_base, use_shell=use_shell)
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
            out.append("\n")
            out.append(f"![图示 {ok}]({rel})\n")
            out.append("\n")
            continue
        out.append(line)
        i += 1

    return "".join(out), ok, failed


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


def try_write_docx(out_md: Path, docx_out: Path) -> bool:
    """
    调用同目录下的 md_to_docx.py。成功返回 True；失败打印警告与手动命令，返回 False。
    """
    tools_dir = Path(__file__).resolve().parent
    md_script = tools_dir / "md_to_docx.py"
    base_dir = out_md.parent
    docx_out.parent.mkdir(parents=True, exist_ok=True)

    if not md_script.is_file():
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
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("警告：生成 Word 超时（300s）。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False
    except OSError as e:
        print(f"警告：无法启动 md_to_docx：{e}", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    if r.returncode != 0:
        print(f"警告：md_to_docx 失败（退出码 {r.returncode}）。", file=sys.stderr)
        err = (r.stderr or r.stdout or "").strip()
        if err:
            print(err[:2000], file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    print(f"已写入 Word: {docx_out}", file=sys.stderr)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Markdown 内 mermaid 围栏 → PNG，默认再生成同名 Word"
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
    args = p.parse_args(argv)

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

    new_md, n_ok, n_fail = render_markdown_mermaid(
        md,
        out_md_path=out_path,
        assets_rel=args.assets_dir.strip("/\\") or "mermaid_figures",
    )

    out_path.write_text(new_md, encoding="utf-8")
    parts = [f"已写入 {out_path}（mermaid：{n_ok} 处已转为 PNG"]
    if n_fail:
        parts.append(f"，{n_fail} 处生图失败已保留 fenced 源码")
    parts.append("）")
    print("".join(parts), file=sys.stderr)
    if n_fail:
        print(
            "[mermaid_render] 已继续生成 Markdown"
            + (" 并将尝试 Word" if not args.no_docx else "")
            + "；请检查 Node/mmdc 或修正语法后重跑本脚本。",
            file=sys.stderr,
        )

    if args.no_docx:
        return 0

    docx_path = (
        args.docx.resolve()
        if args.docx is not None
        else out_path.with_suffix(".docx")
    )
    try_write_docx(out_path, docx_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
