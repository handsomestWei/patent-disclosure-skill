# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "figure_check.py"


def run_check(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write_case(tmp_path: Path, body: str) -> Path:
    case_dir = tmp_path / "case"
    image_dir = case_dir / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "图示01_系统架构图.png").write_bytes(b"fake")
    (image_dir / "图示02_流程状态图.png").write_bytes(b"fake")
    md = case_dir / "一种测试方法_20260629120000.md"
    md.write_text(body, encoding="utf-8")
    return md


def test_ch5_rep_figure_with_ch13_match_passes(tmp_path: Path) -> None:
    """Chapter 5 embeds representative figure; same image in Chapter 13 → OK."""
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1"系统架构图"。该图展示了系统的核心架构。

![图示1 系统架构图](images/图示01_系统架构图.png)

完整图示说明及附图标记见第 13 章。

### 11. 所有的实施方式

如图1所示，第一处理模块（101）与数据采集模块（102）连接。

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）和数据采集模块（102）的连接关系。

图中关键附图标记：101-第一处理模块，102-数据采集模块。

![图示2 流程状态图](images/图示02_流程状态图.png)

图示2：流程状态图。该图展示了系统从启动到完成的状态流转过程。

图中关键附图标记：201-启动状态，202-处理状态，203-完成状态。
""",
    )

    result = run_check(md)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "FIGURE_CHECK_OK" in result.stdout


def test_ch5_rep_figure_without_ch13_match_fails(tmp_path: Path) -> None:
    """Chapter 5 image that doesn't exist in Chapter 13 → error."""
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

![图示1 系统架构图](images/图示99_仅在第5章.png)

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）。

图中关键附图标记：101-第一处理模块。
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "chapter 5 representative figure has no chapter 13 match" in result.stdout


def test_outside_image_not_in_ch5_fails(tmp_path: Path) -> None:
    """Image in chapter other than 5 or 13 → error."""
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1"系统架构图"，完整图示说明及附图标记见第 13 章。

### 11. 所有的实施方式

![图示1 系统架构图](images/图示01_系统架构图.png)

如图1所示，第一处理模块（101）与数据采集模块（102）连接。

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）。

图中关键附图标记：101-第一处理模块。
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "outside chapter 13" in result.stdout


def test_undefined_figure_reference_fails(tmp_path: Path) -> None:
    """External text reference to a figure not in Chapter 13 → error."""
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1"系统架构图"，完整图示说明及附图标记见第 13 章。

### 11. 所有的实施方式

如图2所示，第一处理模块（101）与数据采集模块（102）连接。

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）。

图中关键附图标记：101-第一处理模块。
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "undefined external figure reference: 图2" in result.stdout


def test_missing_caption_and_file_fails(tmp_path: Path) -> None:
    """Missing caption or image file → error."""
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1"系统架构图"，完整图片、图示说明及附图标记见第 13 章。

### 13. 附图

![图示1 系统架构图](images/图示99_不存在.png)
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "missing image file" in result.stdout
    assert "missing caption for 图1" in result.stdout
