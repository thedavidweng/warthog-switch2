"""Compile the deko3d renderer's dumped shaders with UAM on the PC.

The proof of DEKO3D.md's phase 4: every shader the deko3d image's GLSL
generators (port/switch/guest/nv2a_vsh_dk.c, nv2a_psh_dk.c) produce for the
game's real shaders must compile with UAM, deko3d's shader compiler. The
shaders are the folder the deko3d image writes when debug.gpu_dump_shaders
names one (sdmc:/halo_dk_shaders on the console; pull it over FTP, the way
tools/switch_logs.py does):

    python3 tools/dk_shader_check.py /path/to/halo_dk_shaders

Every .vert is compiled with `uam -s vert FILE -o /dev/null`, every .frag
with -s frag. Failures are reported with UAM's message and the file; at the
end, the counts per stage and the warnings UAM printed, counted by kind.
Any failure exits 1, so this can gate a change to the generators.
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

UAM_CANDIDATES = ("/opt/devkitpro/tools/bin/uam",)
USAGE = "usage: dk_shader_check.py [--target switch2] [shader folder]"


def find_uam():
    """devkitPro's uam package, on the PATH or where it installs."""
    on_path = shutil.which("uam")
    if on_path:
        return on_path
    for candidate in UAM_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(usage=USAGE)
    parser.add_argument("--target", choices=("switch", "switch2"), default="switch")
    parser.add_argument("folder", nargs="?",
                        default="/tmp/halo-logs/halo_dk_shaders")
    args = parser.parse_args()
    folder = Path(args.folder)
    if args.target == "switch2":
        return audit_switch2_cache(folder)
    uam = find_uam()
    if not uam:
        print("uam not found: install devkitPro's uam package (dkp-pacman -S uam)")
        return 2
    if not folder.is_dir():
        print("no shader folder at %s" % folder)
        return 2

    files = sorted(folder.glob("*.vert")) + sorted(folder.glob("*.frag"))
    if not files:
        print("no .vert or .frag files in %s" % folder)
        return 2

    counts = Counter()
    warnings = Counter()
    failures = 0
    for path in files:
        stage = "vert" if path.suffix == ".vert" else "frag"
        result = subprocess.run([uam, "-s", stage, str(path), "-o", "/dev/null"],
                                capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            failures += 1
            print("FAIL %s:" % path.name)
            for line in output.splitlines():
                print("    %s" % line)
            continue
        counts[stage] += 1
        for line in output.splitlines():
            match = re.search(r"warning[:\s](.*)", line, re.I)
            if match:
                warnings[match.group(1).strip()] += 1

    print("compiled: %d vertex, %d fragment; %d failed" %
          (counts["vert"], counts["frag"], failures))
    for kind, count in warnings.most_common():
        print("warning x%d: %s" % (count, kind))
    return 1 if failures else 0


def audit_switch2_cache(folder):
    """Validate persistent Ampere DKSH and pack records without loading them."""
    files = sorted(folder.rglob("*.dksh")) + sorted(folder.rglob("*.pack"))
    if not files:
        print("no Switch 2 Ampere cache files in %s" % folder)
        return 2
    failures = 0
    for path in files:
        data = path.read_bytes()
        if path.suffix == ".dksh":
            valid = len(data) >= 32 and data[:4] == b"DKSH"
            valid = valid and int.from_bytes(data[24:28], "little") == 200
        else:
            valid = len(data) >= 8 and data[:4] == b"DKPK"
            offset = 8
            while valid and offset < len(data):
                if len(data) - offset < 24 or data[offset:offset + 4] != b"DKPR":
                    valid = False
                    break
                size = int.from_bytes(data[offset + 16:offset + 20], "little")
                valid = size > 0 and offset + 24 + size <= len(data)
                offset += 24 + size
        if not valid:
            failures += 1
            print("FAIL %s: invalid Ampere cache record" % path)
        else:
            print("PASS %s" % path.name)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
