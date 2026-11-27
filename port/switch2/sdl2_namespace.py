"""Isolate SDL2's exported names from the SDL3 platform interface."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nm", required=True)
    parser.add_argument("--objcopy", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = subprocess.check_output(
        [args.nm, "--defined-only", args.archive], text=True
    )
    symbols = sorted({
        fields[-1]
        for line in output.splitlines()
        if (fields := line.split()) and fields[-1].startswith("SDL_")
        and len(fields) >= 2 and len(fields[-2]) == 1
    })
    if not symbols:
        raise ValueError("SDL2 archive defines no SDL_ symbols")
    Path(args.symbols).write_text(
        "".join(f"{name} sdl2_host_{name}\n" for name in symbols),
        encoding="utf-8",
    )
    subprocess.run(
        [args.objcopy, f"--redefine-syms={args.symbols}", args.archive, args.output],
        check=True,
    )


if __name__ == "__main__":
    main()
