#!/usr/bin/env python3
"""Lay out the Switch build and your maps for the SD card.

    python3 tools/switch_package.py --maps /path/to/your/maps --out ~/Downloads/warthog-switch

writes OUT/switch/ChupaThingyCE/ with the program (build/switch/halo.nro) and
the game (build/switch/halo_guest.elf), from `ninja switch`; the Switch's own
menu files (build/switch/menus, tools/switch_menus.py) as menus/; internet
play's broker list (the game's port/assets/network/brokers.txt); and maps/
with the maps folder's *.map and loading.tga from your own copy of Halo. Copy the
`switch/` folder to the SD card's root (sd:/switch/ChupaThingyCE/).

The maps are never part of the build or of a release: they come from a disc
you own. With no --maps, only the build is laid out, and the game unpacks a
disc image it finds on the card itself (port/switch/README.md, "Game data").

    python3 tools/switch_package.py --target switch2 --out /tmp/warthog-card

lays out the Switch 2 build instead: OUT/switch/warthog/ with warthog.nro from
`ninja switch2`, the broker list, and the menu files when the build writes
them. The current Switch 2 startup program has no guest image, so --guest
is the original Switch's alone.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def local_or_root(path: Path) -> Path:
    local = Path.cwd() / path
    return local if local.exists() else ROOT / path


BUILD = local_or_root(Path("build/switch"))
BUILD_SWITCH2 = local_or_root(Path("build/switch2"))
BROKERS = local_or_root(Path("chupathingyce/port/assets/network/brokers.txt"))
# the folder on the card: HOST_ROOT in port/switch/host/host.h
CARD_FOLDER = Path("switch") / "ChupaThingyCE"
# the folder on the card: CARD_DIR in port/switch2/build.py
CARD_FOLDER_SWITCH2 = Path("switch") / "warthog"


def place(source: Path, destination: Path) -> None:
    """a hard link where the file system allows one, a copy elsewhere"""
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=("switch", "switch2"), default="switch",
                        help="which console's build to lay out (default: switch)")
    parser.add_argument("--nro", type=Path, help="the program (default: the target's build)")
    parser.add_argument("--guest", type=Path, help="the game (default: the target's build)")
    parser.add_argument("--maps", type=Path, help="your copy of Halo's maps folder (its *.map and loading.tga)")
    parser.add_argument("--out", type=Path, required=True, help="the folder to lay the card out in")
    parser.add_argument("--release-dir", type=Path, help="write Switch 2 release archives here")
    parser.add_argument("--flavor", choices=("debug", "release"), help="Switch 2 build flavor")
    args = parser.parse_args()

    if args.release_dir and (args.target != "switch2" or args.maps or not args.flavor):
        parser.error("--release-dir requires --target switch2 and --flavor, without --maps")
    if args.target == "switch2":
        return package_switch2(args)
    return package_switch(args)


def package_switch2(args: argparse.Namespace) -> int:
    """OUT/switch/warthog/: the program, and what ships beside it

    The current startup program has no guest image to copy. Menu files are
    included when the build writes them.
    """
    nro = args.nro or BUILD_SWITCH2 / "warthog.nro"
    if not nro.is_file():
        print(f"no {nro}: run ninja switch2 first", file=sys.stderr)
        return 1
    symbols = [BUILD_SWITCH2 / name for name in ("warthog.elf", "warthog.elf.map", "warthog.nacp")]
    if args.release_dir and any(not path.is_file() for path in symbols):
        print("missing Switch 2 symbol files; run ninja switch2 first", file=sys.stderr)
        return 1
    app_dir = args.out.expanduser() / CARD_FOLDER_SWITCH2
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nro, app_dir / "warthog.nro")
    shutil.copy2(ROOT / "LICENSE", app_dir / "LICENSE")
    (app_dir / "THIRD-PARTY-NOTICES.txt").write_text(third_party_notices(), encoding="utf-8")
    packaged = [app_dir / "warthog.nro", app_dir / "LICENSE", app_dir / "THIRD-PARTY-NOTICES.txt"]
    if BROKERS.is_file():
        shutil.copy2(BROKERS, app_dir / "brokers.txt")
        packaged.append(app_dir / "brokers.txt")
    menus = sorted(path for path in (BUILD_SWITCH2 / "menus").rglob("*.xml")) \
        if (BUILD_SWITCH2 / "menus").is_dir() else []
    for path in menus:
        destination = app_dir / "menus" / path.relative_to(BUILD_SWITCH2 / "menus")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        packaged.append(destination)
    if args.release_dir:
        from switch2_audit import audit_package
        problems = audit_package(args.out.expanduser())
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        args.release_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"warthog-switch2-{args.flavor}"
        archive_path = args.release_dir / f"{prefix}.zip"
        symbols_path = args.release_dir / f"{prefix}-symbols.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(packaged):
                archive.write(path, (CARD_FOLDER_SWITCH2 / path.relative_to(app_dir)).as_posix())
        with zipfile.ZipFile(symbols_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in symbols:
                archive.write(path, path.name)
        problems = audit_package(archive_path, args.flavor, symbols_path)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        sums = args.release_dir / "SHA256SUMS.txt"
        old = sums.read_text(encoding="utf-8").splitlines() if sums.exists() else []
        names = {archive_path.name, symbols_path.name}
        lines = [line for line in old if line.split("  ", 1)[-1] not in names]
        lines += [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
                  for path in (archive_path, symbols_path)]
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{app_dir}: warthog.nro" + (f", {len(menus)} menu files" if menus else ""))
    return 0


def third_party_notices() -> str:
    record = json.loads((ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
    entries = [record["upstream"], record["submodules"]["chupathingyce"]]
    entries += list(record["dependencies"].values())
    lines = ["Third-party components and pinned source revisions", ""]
    for entry in entries:
        lines.append(f'{entry["repository"]}  {entry["commit"]}  {entry["license"]}')
    ref = record["references"]["dolphin_nx"]
    lines += ["""drako3d
Copyright (C) 2018-2020 fincs
Copyright (C) 2026 PalindromicBreadLoaf

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any
damages arising from the use of this software.

Permission is granted to anyone to use this software for any
purpose, including commercial applications, and to alter it and
redistribute it freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you
   must not claim that you wrote the original software. If you use
   this software in a product, an acknowledgment in the product
   documentation would be appreciated but is not required.
2. Altered source versions must be plainly marked as such, and
   must not be misrepresented as being the original software.
3. This notice may not be removed or altered from any source
   distribution.

uam2_lic
License for all files not included in subprojects/:

Copyright (C) 2018-2020 fincs
Copyright (C) 2026 PalindromicBreadLoaf

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any
damages arising from the use of this software.

Permission is granted to anyone to use this software for any
purpose, including commercial applications, and to alter it and
redistribute it freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you
   must not claim that you wrote the original software. If you use
   this software in a product, an acknowledgment in the product
   documentation would be appreciated but is not required.
2. Altered source versions must be plainly marked as such, and
   must not be misrepresented as being the original software.
3. This notice may not be removed or altered from any source
   distribution.

UAM2 is derived from UAM by fincs, and builds on sources from the Mesa 3-D
graphics library.
The default Mesa license is reproduced below:

Copyright (C) 1999-2007  Brian Paul   All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

For more precise licensing information, check out the header of each source
code file in the subprojects/mesa/ directory, or visit this website:
    https://docs.mesa3d.org/license.html

ounce_devkit
MIT License

Copyright (c) 2026 the ounce-devkit contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

SDL2
Copyright (C) 1997-2026 Sam Lantinga

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.

libkaihen_lic
Copyright (c) 2026 kaiHEN contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

libounce LICENSE.md
Copyright 2017-2018 libnx Authors

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE."""]
    lines += ["", f'NaGaa95/dolphin-nx {ref["commit"]}: nx2_platform.{{c,h}} and '
              "nx2_gameshare.{c,h}: SPDX-License-Identifier: MIT",
              "Mesa (NAK and GLSL compiler): MIT; included in UAM2.",
              "nanosvg: Zlib; included in the upstream Switch port.",
              "libkaihen is the ISC-licensed client library of kaihen.",
              "", (ROOT / "port/switch/third_party/nanosvg/LICENSE.txt").read_text(encoding="utf-8"),
              "", "This project is not affiliated with or endorsed by Nintendo, Microsoft, Bungie, "
              "343 Industries / Halo Studios, ChupathingyCE, or ouncebrew.",
              "No Nintendo SDK code or commercial game assets are included.", ""]
    third_party = ROOT / "chupathingyce/port/third_party"
    for name in ("expat/COPYING", "tomlc17/LICENSE", "kcp/LICENSE", "qrcodegen/LICENSE",
                 "musl-math/COPYRIGHT", "mbedtls/LICENSE", "miniupnpc/LICENSE", "zlib/LICENSE"):
        lines += [f"\n{name}\n", (third_party / name).read_text(encoding="utf-8")]
    monocypher = (third_party / "monocypher/monocypher.h").read_text(encoding="utf-8").splitlines()
    lines += ["\nmonocypher/monocypher.h\n", "\n".join(monocypher[:43])]
    return "\n".join(lines)


def package_switch(args: argparse.Namespace) -> int:
    """OUT/switch/ChupaThingyCE/: the program, the guest image and your maps"""
    nro = args.nro or BUILD / "halo.nro"
    guest = args.guest or BUILD / "halo_guest.elf"
    menus_folder = BUILD / "menus"
    for path in (nro, guest):
        if not path.is_file():
            print(f"no {path}: run ninja switch first", file=sys.stderr)
            return 1
    maps = []
    if args.maps:
        folder = args.maps.expanduser()
        maps = sorted(folder.glob("*.map")) + [p for p in [folder / "loading.tga"] if p.is_file()]
        if not any(p.name == "ui.map" for p in maps):
            print(f"no ui.map in {folder}", file=sys.stderr)
            return 1

    app_dir = args.out.expanduser() / CARD_FOLDER
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nro, app_dir / "halo.nro")
    shutil.copy2(guest, app_dir / "halo_guest.elf")
    if BROKERS.is_file():
        shutil.copy2(BROKERS, app_dir / "brokers.txt")
    menus = sorted(path for path in menus_folder.rglob("*.xml")) if menus_folder.is_dir() else []
    for path in menus:
        destination = app_dir / "menus" / path.relative_to(menus_folder)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    if maps:
        (app_dir / "maps").mkdir(exist_ok=True)
        for path in maps:
            place(path, app_dir / "maps" / path.name)
    print(f"{app_dir}: halo.nro, halo_guest.elf, {len(menus)} menu files" +
          (f" and {len(maps)} map files" if maps else " (no maps)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
