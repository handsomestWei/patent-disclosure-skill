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


def test_figure_check_accepts_matching_chapter13_figures(tmp_path: Path) -> None:
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1“系统架构图”，完整图片、图示说明及附图标记见第 13 章。

### 11. 所有的实施方式

如图1所示，第一处理模块（101）与数据采集模块（102）连接。

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）和数据采集模块（102）的连接关系。

#### 附图说明

| 图号 | 图名 | 说明 |
|------|------|------|
| 图1 | 系统架构图 | 说明系统架构 |

#### 附图标记表

| 附图标记 | 名称 | 说明 |
|----------|------|------|
| 101 | 第一处理模块 | 执行处理 |
| 102 | 数据采集模块 | 采集数据 |
""",
    )

    result = run_check(md)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "FIGURE_CHECK_OK" in result.stdout


def test_figure_check_rejects_undefined_external_figure_and_outside_image(tmp_path: Path) -> None:
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

![图示1 系统架构图](images/图示01_系统架构图.png)

### 11. 所有的实施方式

如图2所示，第一处理模块（101）与数据采集模块（102）连接。

### 13. 附图

![图示1 系统架构图](images/图示01_系统架构图.png)

图示1：系统架构图。该图用于说明第一处理模块（101）。

#### 附图说明

| 图号 | 图名 | 说明 |
|------|------|------|
| 图1 | 系统架构图 | 说明系统架构 |

#### 附图标记表

| 附图标记 | 名称 | 说明 |
|----------|------|------|
| 101 | 第一处理模块 | 执行处理 |
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "outside chapter 13" in result.stdout
    assert "undefined external figure reference: 图2" in result.stdout


def test_figure_check_rejects_missing_caption_and_missing_image_file(tmp_path: Path) -> None:
    md = write_case(
        tmp_path,
        """# 专利技术交底书

### 5. 代表性附图

代表性附图为图1“系统架构图”，完整图片、图示说明及附图标记见第 13 章。

### 13. 附图

![图示1 系统架构图](images/图示99_不存在.png)

#### 附图说明

| 图号 | 图名 | 说明 |
|------|------|------|
| 图1 | 系统架构图 | 说明系统架构 |

#### 附图标记表

| 附图标记 | 名称 | 说明 |
|----------|------|------|
| 101 | 第一处理模块 | 执行处理 |
""",
    )

    result = run_check(md)

    assert result.returncode == 1
    assert "missing image file" in result.stdout
    assert "missing caption for 图1" in result.stdout
