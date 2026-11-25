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
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "switch"
BUILD_SWITCH2 = ROOT / "build" / "switch2"
BROKERS = ROOT / "chupathingyce" / "port" / "assets" / "network" / "brokers.txt"
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
    args = parser.parse_args()

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
    app_dir = args.out.expanduser() / CARD_FOLDER_SWITCH2
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nro, app_dir / "warthog.nro")
    if BROKERS.is_file():
        shutil.copy2(BROKERS, app_dir / "brokers.txt")
    menus = sorted(path for path in (BUILD_SWITCH2 / "menus").rglob("*.xml")) \
        if (BUILD_SWITCH2 / "menus").is_dir() else []
    for path in menus:
        destination = app_dir / "menus" / path.relative_to(BUILD_SWITCH2 / "menus")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    print(f"{app_dir}: warthog.nro" + (f", {len(menus)} menu files" if menus else ""))
    return 0


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
