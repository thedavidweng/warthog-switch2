"""Audit the Switch 2 build's artifacts (ticket #3).

    python3 tools/switch2_audit.py [build/switch2]

Reads the four files `ninja switch2` writes and answers the question the
release requirements ask: is this a Switch 2 program, or an original Switch
one wearing its name? It looks at the artifacts, not at the build graph:

- warthog.nro: the Switch 2 homebrew header (`HOMEBREWNRO0`, not the original
  Switch's `NRO0`), its `MOD0` and `OUN0` headers, and the asset section
  elf2nro appends (`ASET`): a JPEG icon and the 16 KiB NACP.
- warthog.nacp: the title, author and version hbmenu shows.
- warthog.elf: the `OUN0` header, and the `.debug_info` and `.symtab` a crash
  report is symbolized against.
- warthog.elf.map: the libraries the link pulled in. libounce, Drako3D and
  the UAM2 runtime are expected; anything from devkitPro's original Switch
  libnx or its GPU portlibs means the two consoles were mixed.

A problem is a sentence naming the file and what is wrong with it, so a CI
log says what to fix. `audit()` returns them; the command line prints one per
line and exits non-zero when there is any.
"""

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]

# What hbmenu shows. The title and author are fixed rather than taken from the
# environment: $USER on a build machine is whoever's account ran it, which
# would put a different publisher on every release. UPSTREAM.json supplies
# the Switch 2 release version.
NACP_TITLE = "Warthog"
NACP_AUTHOR = "thedavidweng, ChupathingyCE contributors"
NACP_SIZE = 16384
NACP_VERSION_OFFSET = 0x3060
NACP_VERSION_SIZE = 0x10


def nacp_version() -> str:
    """The NACP display version of this Switch 2 release."""
    record = json.loads((ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
    version = record["switch2_version"]
    if not version or len(version) >= NACP_VERSION_SIZE:
        raise ValueError(f"UPSTREAM.json's version {record['upstream']['version']!r} is not an NACP display version")
    return version


# The NRO's own header, at offsets libnx's nro.h gives: the first 4 bytes are
# unused, then the branch, then the magic at 0x10.
NRO_MAGIC_OFFSET = 8
NRO_MAGIC = b"HOMEBREWNRO0"
NRO_MOD0_OFFSET_FIELD = 4
NRO_SIZE_OFFSET = 0x18
ASET_HEADER_SIZE = 0x38

# The libraries a Switch 2 link uses, by the map's spelling of their members.
REQUIRED_LIBRARIES = ("libounce.a", "libdrako3d.a", "libuam2rt.a")

# What a Switch 2 link must not contain: devkitPro's original Switch platform
# (libnx), its Maxwell Deko3D, and the Switch 1 GPU portlibs that only make
# sense beside it.
FORBIDDEN_LIBRARIES = ("libdeko3d", "libnvtegra", "libnvidia", "libnvdrv",
                       "libEGL.a", "libGLESv2.a", "libglapi.a", "libdrm_nouveau.a")

# The one devkitPro path no Switch 2 link may use. /opt/devkitpro/portlibs/switch
# is deliberately not forbidden: libounce's switch2_rules shares the C-only
# portlibs there (libSDL2.a, libz.a, libcurl.a), and a Switch 1 GPU library
# coming from it is caught by name in FORBIDDEN_LIBRARIES above.
FORBIDDEN_PATHS = ("/opt/devkitpro/libnx/",)


def problems_for_missing(directory: Path) -> List[str]:
    return [f"{directory.name}: no {name}; run `ninja switch2`"
            for name in ("warthog.nro", "warthog.elf", "warthog.nacp", "warthog.elf.map")
            if not (directory / name).is_file()]


def nacp_problems(nacp: bytes) -> List[str]:
    """the title, author and version hbmenu shows"""
    problems = []
    if len(nacp) != NACP_SIZE:
        return [f"warthog.nacp: {len(nacp)} bytes, not the {NACP_SIZE} an NACP is"]
    title = nacp[:0x200].split(b"\x00")[0].decode("utf-8", "replace")
    author = nacp[0x200:0x300].split(b"\x00")[0].decode("utf-8", "replace")
    version = nacp[NACP_VERSION_OFFSET:NACP_VERSION_OFFSET + NACP_VERSION_SIZE]
    version = version.split(b"\x00")[0].decode("utf-8", "replace")
    if title != NACP_TITLE:
        problems.append(f"warthog.nacp: title {title!r}, not {NACP_TITLE!r}")
    if author != NACP_AUTHOR:
        problems.append(f"warthog.nacp: author {author!r}, not {NACP_AUTHOR!r}")
    if version != nacp_version():
        problems.append(f"warthog.nacp: version {version!r}, not the pinned {nacp_version()!r}")
    return problems


def nro_problems(nro: bytes) -> List[str]:
    problems = []
    if len(nro) < NRO_SIZE_OFFSET + 4:
        return [f"warthog.nro: {len(nro)} bytes, too short for an NRO header"]
    magic = nro[NRO_MAGIC_OFFSET:NRO_MAGIC_OFFSET + len(NRO_MAGIC)]
    if magic != NRO_MAGIC:
        problems.append(f"warthog.nro: {magic!r} at offset {NRO_MAGIC_OFFSET}, not {NRO_MAGIC!r} "
                        f"(an original Switch NRO, or not an NRO)")
    mod0_offset = struct.unpack_from("<I", nro, NRO_MOD0_OFFSET_FIELD)[0]
    if mod0_offset + 4 > len(nro) or nro[mod0_offset:mod0_offset + 4] != b"MOD0":
        problems.append(f"warthog.nro: no MOD0 header at {mod0_offset:#x}")
    if b"OUN0" not in nro:
        problems.append("warthog.nro: no OUN0 header (libounce's Switch 2 module header)")

    nro_size = struct.unpack_from("<I", nro, NRO_SIZE_OFFSET)[0]
    if nro_size + 8 > len(nro) or nro[nro_size:nro_size + 4] != b"ASET":
        problems.append(f"warthog.nro: no ASET asset section at the NRO's size ({nro_size:#x}): "
                        f"no icon and no NACP")
        return problems
    if nro_size + ASET_HEADER_SIZE > len(nro):
        problems.append(f"warthog.nro: the ASET header runs past the end of the file")
        return problems
    icon_offset, icon_size, nacp_offset, nacp_size = struct.unpack_from("<QQQQ", nro, nro_size + 8)
    icon = nro[nro_size + icon_offset:nro_size + icon_offset + icon_size]
    nacp = nro[nro_size + nacp_offset:nro_size + nacp_offset + nacp_size]
    if not icon.startswith(b"\xff\xd8"):
        problems.append(f"warthog.nro: the icon is not a JPEG (starts {icon[:4].hex()})")
    if len(nacp) != NACP_SIZE:
        problems.append(f"warthog.nro: the embedded NACP is {len(nacp)} bytes, not {NACP_SIZE}")
    else:
        problems.extend(nacp_problems(nacp))
    return problems


def elf_problems(elf: bytes) -> List[str]:
    """the OUN0 header, and the sections a crash report is symbolized with"""
    if len(elf) < 64 or elf[:4] != b"\x7fELF":
        return ["warthog.elf: not an ELF file"]
    if elf[4] != 2:
        return ["warthog.elf: not an ELF64 file"]
    shoff, = struct.unpack_from("<Q", elf, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", elf, 0x3A)
    if shoff == 0 or shnum == 0 or shstrndx >= shnum or shoff + shnum * shentsize > len(elf):
        return ["warthog.elf: no section headers"]
    sections = []
    for index in range(shnum):
        name, _, _, _, offset, size, _, _, _, _ = struct.unpack_from("<IIQQQQIIQQ", elf, shoff + index * shentsize)
        sections.append((name, offset, size))
    _, string_offset, string_size = sections[shstrndx]
    strings = elf[string_offset:string_offset + string_size]
    names = []
    for name, _, _ in sections:
        end = strings.find(b"\x00", name)
        names.append(strings[name:end].decode("ascii", "replace"))
    problems = []
    for section in (".debug_info", ".symtab"):
        if section not in names:
            problems.append(f"warthog.elf: no {section} section (the release's symbols cannot be matched to it)")
    if b"OUN0" not in elf:
        problems.append("warthog.elf: no OUN0 header (libounce's Switch 2 module header)")
    return problems


def map_problems(text: str, flavor: str = None) -> List[str]:
    """what the link pulled in: Switch 2's libraries, and nothing of Switch 1's"""
    problems = []
    for library in ("libounce.a", "libuam2rt.a"):
        if library not in text:
            problems.append(f"warthog.elf.map: {library} is not linked")
    renderer = "libdrako3dd.a" if flavor == "debug" else "libdrako3d.a"
    if flavor is None:
        if not any(name in text for name in ("libdrako3d.a", "libdrako3dd.a")):
            problems.append("warthog.elf.map: Drako3D (libdrako3d.a / libdrako3dd.a) is not linked")
    else:
        if renderer not in text:
            problems.append(f"warthog.elf.map: {renderer} is not linked")
        other = "libdrako3d.a" if flavor == "debug" else "libdrako3dd.a"
        if other in text:
            problems.append(f"warthog.elf.map: {other} is linked for {flavor}")
    for path in FORBIDDEN_PATHS:
        if path in text:
            problems.append(f"warthog.elf.map: {path} is linked: this is the original Switch's platform")
    for library in FORBIDDEN_LIBRARIES:
        if library in text:
            problems.append(f"warthog.elf.map: {library} is linked: an original Switch library")
    if "/Users/" in text or "/home/" in text:
        problems.append("warthog.elf.map: a home directory is in the map; the build ran outside the container")
    return problems


def audit(directory: Path, flavor: str = None) -> List[str]:
    """every problem with the artifacts in `directory`; empty when it is sound"""
    directory = Path(directory)
    problems = problems_for_missing(directory)
    if problems:
        return problems
    problems.extend(nro_problems((directory / "warthog.nro").read_bytes()))
    problems.extend(nacp_problems((directory / "warthog.nacp").read_bytes()))
    problems.extend(elf_problems((directory / "warthog.elf").read_bytes()))
    problems.extend(map_problems((directory / "warthog.elf.map").read_text(encoding="utf-8", errors="replace"), flavor))
    return problems


def audit_package(path: Path, flavor: str = None, symbols: Path = None) -> List[str]:
    path = Path(path)
    problems = []
    if path.is_dir():
        files = {p.relative_to(path).as_posix(): p.read_bytes()
                 for p in path.rglob("*") if p.is_file()}
    elif path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            problems.extend(f"{entry.filename}: compressed ZIP entry" for entry in archive.infolist()
                            if entry.compress_type != zipfile.ZIP_STORED)
            files = {entry.filename: archive.read(entry) for entry in archive.infolist() if not entry.is_dir()}
    else:
        return [f"{path}: not a package directory or zip"]
    for name in files:
        lower = name.lower()
        if lower.endswith((".map", ".iso", ".xiso", ".7z", ".bik", ".sav", ".dksh")) or lower.rsplit("/", 1)[-1] == "loading.tga":
            problems.append(f"{name}: forbidden package file")
    root = "switch/warthog/"
    for name in ("warthog.nro", "LICENSE", "THIRD-PARTY-NOTICES.txt"):
        if root + name not in files:
            problems.append(f"{root + name}: missing")
    if root + "warthog.nro" in files:
        problems.extend(nro_problems(files[root + "warthog.nro"]))
    if root + "THIRD-PARTY-NOTICES.txt" in files:
        notice = files[root + "THIRD-PARTY-NOTICES.txt"].decode("utf-8", "replace").lower()
        for required in ("gpl-3.0-or-later", "zlib", "drako3d", "uam2", "isc", "libounce",
                         "libkaihen", "mit", "nagaa95/dolphin-nx",
                         "7fb685b353e19a9a5848e9bd658945d1f9cd382a", "not affiliated"):
            if required not in notice:
                problems.append(f"THIRD-PARTY-NOTICES.txt: missing {required}")
    if flavor and not symbols:
        problems.append("symbols archive required to verify flavor")
    if symbols:
        if not zipfile.is_zipfile(symbols):
            problems.append(f"{symbols}: not a symbols ZIP")
            return problems
        with zipfile.ZipFile(symbols) as archive:
            names = set(archive.namelist())
            for name in ("warthog.elf", "warthog.elf.map", "warthog.nacp"):
                if name not in names:
                    problems.append(f"symbols: missing {name}")
            if "warthog.elf" in names:
                problems.extend(elf_problems(archive.read("warthog.elf")))
            if "warthog.elf.map" in names:
                problems.extend(map_problems(archive.read("warthog.elf.map").decode("utf-8", "replace"), flavor))
            nro = files.get(root + "warthog.nro")
            if nro and not nro_problems(nro) and "warthog.nacp" in names:
                size, = struct.unpack_from("<I", nro, NRO_SIZE_OFFSET)
                offset, length = struct.unpack_from("<QQ", nro, size + 24)
                if archive.read("warthog.nacp") != nro[size + offset:size + offset + length]:
                    problems.append("symbols: NACP differs from NRO")
    return problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("build") / "switch2")
    parser.add_argument("--flavor", choices=("debug", "release"))
    parser.add_argument("--package", type=Path)
    parser.add_argument("--symbols", type=Path)
    args = parser.parse_args(argv[1:])
    directory = args.package or args.directory
    problems = audit_package(args.package, args.flavor, args.symbols) if args.package else audit(directory, args.flavor)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s) in {directory}")
        return 1
    print(f"{directory}: audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
