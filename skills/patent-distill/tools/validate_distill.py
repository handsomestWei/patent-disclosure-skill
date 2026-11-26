# -*- coding: utf-8 -*-
"""校验 outputs/patent-distill/{档案}/。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from distill_validate import validate_batch
from stdio_utf8 import ensure_utf8_stdio


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="校验专利蒸馏档案")
    parser.add_argument("--dir", required=True)
    args = parser.parse_args(argv)
    directory = Path(args.dir)
    errors = validate_batch(directory)
    if errors:
        for item in errors:
            print(f"DISTILL_ERROR: {item}", file=sys.stderr)
        return 2
    print(f"DISTILL_OK: {directory.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
