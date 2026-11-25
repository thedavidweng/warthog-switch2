#!/usr/bin/env python3
"""Rewrite Xbox ABI sources for Switch 2's LP64 compiler."""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chupathingyce"))
from tools.lp64_rewrite import read, rewrite

STATIC_INLINE = re.compile(r"\bstatic(\s+)(?:__inline|_inline)\b")
STATIC_FORCEINLINE = re.compile(r"\bstatic(\s+)__forceinline\b")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    text = rewrite(read(args.source))
    text = re.sub(r"__declspec\s*\(\s*align\s*\(\s*(\d+)\s*\)\s*\)",
                  r"__attribute__((aligned(\1)))", text)
    text = re.sub(r"__declspec\s*\(\s*(noinline|noreturn)\s*\)",
                  r"__attribute__((\1))", text)
    text = STATIC_INLINE.sub(r"static\1__inline__", text)
    text = STATIC_FORCEINLINE.sub(r"static\1__inline__ __attribute__((always_inline))", text)
    text = f'#line 1 "{args.source.as_posix()}"\n' + text
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.is_file() or read(args.output) != text:
        with args.output.open("w", encoding="latin-1", newline="") as output:
            output.write(text)


if __name__ == "__main__":
    main()
