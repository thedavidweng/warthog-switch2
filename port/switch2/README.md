# Switch 2

`ninja switch2` builds Warthog for the Nintendo Switch 2, as a homebrew
program (`warthog.nro`) that runs under kaiHEN. This folder is the port's
platform layer: the build graph (`build.py`), the startup program (`host/`)
and the patch UAM2 is built with (`uam2.patch`). The game engine is the
`chupathingyce/` submodule, and `port/switch/` stays what the original Switch
builds from; nothing here is read by `ninja switch`.

The build graph is loaded by the game's `configure.py`, the same way
`port/switch/build.py` is:

```sh
python3 chupathingyce/configure.py --console-port port/switch2
ninja switch2
```

That writes four files to `build/switch2`, and nothing anywhere else:

| File | What it is |
|---|---|
| `warthog.elf` | the program, unstripped, with its linker map beside it |
| `warthog.nacp` | the title, author and version hbmenu shows |
| `warthog.nro` | the homebrew the card takes, with the icon and the NACP |
| `warthog.elf.map` | what the link pulled in, which is what the audit reads |

Without a Switch 2 devkitPro (libounce, Drako3D, the UAM2 runtime) and the
`aarch64-none-elf` toolchain, `configure.py` writes a comment saying which one
is missing and `ninja switch` still configures. `--devkitpro DIR` selects an
install other than `DEVKITPRO`, `/opt/devkitpro` or `~/devkitpro`.

A `--release` build also disables development-only profiling and benchmark
hooks with `WARTHOG_DEV_PROFILING=0`; both flavors keep `.debug_info` and
`.symtab`, so a release's crash is symbolized against the symbols published
beside it.

## The toolchain

The toolchain is pinned, and the pins live in `UPSTREAM.json` and nowhere
else. `scripts/switch2/Dockerfile` builds an image from
`devkitpro/devkita64` at a fixed digest and adds the Switch 2 packages and the
three things devkitPro does not ship: Drako3D (`GPU_ARCH=ampere`), drakotools
and UAM2 with its on-console runtime `libuam2rt.a`. `tests/test_switch2_build.py`
fails when the Dockerfile's `ARG`s and `UPSTREAM.json` disagree.

`scripts/switch2/build.sh` runs the build inside that image:

```sh
scripts/switch2/build.sh image       # build the toolchain image (once)
scripts/switch2/build.sh configure   # configure.py --console-port port/switch2
scripts/switch2/build.sh build       # configure, then ninja switch2
scripts/switch2/build.sh audit       # tools/switch2_audit.py build/switch2
scripts/switch2/build.sh <command>   # anything else, inside the toolchain
```

The repository is mounted at `/src` and the commands run there, so the
linker map carries `/src/...` rather than the build machine's home directory.
`tools/switch2_audit.py` fails the artifacts when a home directory is in the
map, because a map that names one was not made in the pinned image.

`WARTHOG_SWITCH2_IMAGE` names the image (`warthog-switch2-toolchain:local` by
default). On a host with the same packages installed, `WARTHOG_SWITCH2_NATIVE=1`
runs the commands there instead; inside the image it is detected, so the
script does not try to nest Docker.

## What the program does

`host/main.c` is the startup program ticket #3 asks for: it launches, appears
in hbmenu with its name, icon, author and version, writes a log under
`sdmc:/switch/warthog/logs`, and returns to hbmenu cleanly. It draws nothing
and plays nothing. What it records is what the console granted the process:
the applet type and operation mode, the firmware, the core mask, the heap,
whether each syscall the original Switch port used is hinted, that UAM2's
runtime initialises, and that Drako3D is linked. That log is the evidence the
later tickets are decided on.

Every question it asks is read-only. The syscalls kaiHEN does not grant are
asked about with `envIsSyscallHinted` and never called, because an ungranted
one terminates the process instead of returning an error.

## Checking a build

`tools/switch2_audit.py` reads the four artifacts and answers the question the
release requirements ask: is this a Switch 2 program, or an original Switch
one wearing its name? It checks the `HOMEBREWNRO0` and `OUN0` headers, the
NACP's title, author and version, the symbol sections a crash is symbolized
against, and the map's libraries: libounce, Drako3D and the UAM2 runtime are
expected, and anything from devkitPro's original Switch libnx or its GPU
portlibs means the two consoles were mixed. `ninja switch2` builds and the
audit passes, or the artifacts say what is wrong.

`libounce`'s `switch2_rules` shares the C-only portlibs in
`portlibs/switch/` (`libSDL2.a`, `libz.a`), so a path under it is not by
itself a fault; the Switch 1 GPU libraries are caught by name.

## On the console

```sh
python3 tools/switch_deploy.py --host <switch2-ip> --port <port> \
  --destination /switch/warthog build/switch2/warthog.nro
```

`WARTHOG_SWITCH2_HOST` and `WARTHOG_SWITCH2_PORT` carry the console's address,
so no command line and no committed file has to. The log comes back with
`tools/switch_logs.py`, and a crash is symbolized against the matching
unstripped ELF.

Nothing here is `Tested on hardware` yet: the program is `Compiled`, and what
it reports on a console is ticket #3's remaining evidence.

## Third-party notices

Drako3D, UAM2 and drakotools are ouncebrew's, under Zlib (Drako3D, UAM2) and
GPL-3.0 (drakotools, which is not linked into the program). libounce, libnx
and libkaihen are ISC. devkitPro's devkitA64 is under its own terms. Nothing
from Nintendo's SDK is used, and no game data is part of a build.

SPDX-License-Identifier: GPL-3.0-or-later
