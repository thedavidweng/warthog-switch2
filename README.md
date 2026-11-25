<p align="center"><img src="port/switch/art/icon.jpg" width="120" alt=""></p>

<h1 align="center">Warthog for Switch 2</h1>

<p align="center"><b>Chupathingy on the Nintendo Switch 2, under kaiHEN, with no emulator in between.</b></p>

<p align="center">
<a href="https://github.com/ChupathingyCE/chupathingyce">The game (Chupathingy)</a> ·
<a href="https://github.com/ChupathingyCE/warthog-switch">Upstream: Warthog for Switch</a> ·
<a href="https://chupathingy.org">chupathingy.org</a> ·
<a href="https://discord.gg/chupathingy">Discord</a>
</p>

<p align="center">
<a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="License: GPL-3.0-or-later"></a>
</p>

Warthog for Switch 2 is the Nintendo Switch 2 port of **Warthog**, the console
line of the [ChupathingyCE](https://github.com/ChupathingyCE/chupathingyce)
Halo: Combat Evolved decompilation. It runs the same game code as the Windows,
Mac, Linux and Android builds of Chupathingy and as
[Warthog](https://github.com/ChupathingyCE/warthog-xbox) on the original Xbox,
as a native homebrew application on a Switch 2 running
[kaiHEN](https://github.com/ouncebrew/kaihen) — no Xbox emulator, no Android,
no Linux, no remote streaming.

This repository is a fork of
[ChupathingyCE/warthog-switch](https://github.com/ChupathingyCE/warthog-switch)
(the original Switch port), keeping its history, authorship and licence. The
game engine is the `chupathingyce` submodule; the console code is here.

You need your own copy of Halo. No game files are included, and nothing from
Nintendo's SDK is used.

## Status

**Pre-release.** The build and package have been verified on the host, but
interactive campaign, rendering, input and lifecycle verification on a Switch
2 is still required before cutting the first public `v<version>` tag on
`main`. The detailed evidence and remaining gaps are in
[docs/status-matrix.md](docs/status-matrix.md).

| Area | Status |
|---|---|
| Upstream Switch port (`ninja switch`) | Implemented — upstream code carried forward intact; host configuration verified |
| Switch 2 toolchain, `ninja switch2`, Debug/Release packaging and `OUN0` audit | Tested on host — pinned `ounce-devkit` build, package and audit pass; FTP deployment verified, interactive launch pending Tested on hardware |
| Native LP64 engine and memory model (ADR-0001) | Tested on host — source rewrite, `[0x40000000, 0xa0000000)` `StackRegion`, atomic `.part` saves and checkpoint relocation; console probe pending Tested on hardware |
| Drako3D, Ampere `DEKO3D=200`, UAM2 and persistent shader cache (ADRs 0002, 0004) | Tested on host — VI2, cache barriers, five-part cache key, CRC recovery and compile progress; console rendering pending Tested on hardware |
| Campaign, multiplayer, 4-player split-screen, Custom Edition and extraction | Tested on host — XISO extraction, map reuse, 10 campaign missions, TLS networking and 1–4P viewports; console playtesting pending Tested on hardware |
| Display modes, 120 Hz, VRR, Smooth Motion and 4K60 | Tested on host — present-interval readback and strict 4K60 clamp; display verification pending Tested on hardware |
| Controllers, gyro, `swkbd`, USB/BT KBM and Joy-Con 2 `Nmouse` | Tested on host — input deduplication and graceful HID refusal; console input verification pending Tested on hardware |
| GameShare local multiplayer | Tested on host — `Mirror` and dual-swapchain `SeparateViews` on `player1`; two-console testing pending Tested on hardware |
| Halo: The Master Chief Collection maps | Not yet supported — see [docs/mcc-investigation.md](docs/mcc-investigation.md) |


## What you need

- A Switch 2 running homebrew through kaiHEN.
- A way to put files on the SD card, or an FTP server on the console for the
  development loop.
- Your own Halo: Combat Evolved Xbox disc. Use the North American (NTSC)
  release, `01.10.12.2276`, as every Chupathingy build and server does; the
  PAL disc's maps work too. The application unpacks `maps/` from your own
  disc image. Warthog never provides maps, disc images or other game data,
  and never links to them. Don't share yours.
- For online play, a certificate bundle called `cacert.pem`. Mozilla's is at
  [curl.se/docs/caextract.html](https://curl.se/docs/caextract.html); your
  computer's `ca-certificates.crt` works too.

**Owning Halo on PC or through the Master Chief Collection is not enough on
its own.** The port requires retail Xbox Halo: Combat Evolved disc data;
a PC or MCC installation is not a substitute, and MCC map support is not
implemented.

## Installation

1. Unpack `warthog-switch2-release.zip` at the root of the Switch 2 microSD
   card. `warthog.nro`, `brokers.txt`, `menus/`, `LICENSE` and
   `THIRD-PARTY-NOTICES.txt` must be under `sdmc:/switch/warthog/`. Native
   LP64 uses one `warthog.nro`; no guest ELF is needed.
2. Put your own retail Xbox Halo: Combat Evolved `.iso` or `.xiso.iso` under
   `sdmc:/switch/warthog/`. The first launch extracts it into `maps/` after a
   free-space check and removes partial files after interruption. Alternatively
   copy `ui.map`, `bitmaps.map`, `sounds.map`, campaign and multiplayer maps
   into `sdmc:/switch/warthog/maps/`. Compatible
   `sdmc:/switch/ChupaThingyCE/maps/` data is detected and reused. Optional
   Custom Edition maps go in `maps_ce/`; put `cacert.pem` at the application
   root for HTTPS server lists and map downloads.
3. Launch **Warthog for Switch 2** from hbmenu in full-memory title takeover
   mode (`Application` or `SystemApplication`), rather than album applet mode.
4. Upgrade by unpacking a newer archive, or use the in-app updater confined to
   `thedavidweng/warthog-switch2` Switch 2 `build-<N>` releases. It updates
   `warthog.nro`, `menus/`, `brokers.txt` and notices while preserving `maps/`,
   `maps_ce/`, `save/`, `config.toml` and `logs/`.

Everything stays inside `sdmc:/switch/warthog/`. Nothing is written to NAND,
no privileged background plugin is installed, and no permanent system
modification is required.


## Building it yourself

You need Python 3, `ninja`, `clang`, and the Switch 2 toolchain from
[ouncebrew](https://github.com/ouncebrew): `ounce-devkit` with `libounce`,
`libkaihen`, `drako3d` and `uam2`. The original Switch build still needs
devkitPro and the Android NDK, exactly as upstream documents.

```sh
git clone --recursive https://github.com/thedavidweng/warthog-switch2.git
cd warthog-switch2

# The original Switch build, unchanged from upstream
python3 chupathingyce/configure.py --console-port port/switch
ninja switch

# Documentation, pin and override checks; no toolchain, no console
python3 -m unittest discover -s tests
python3 tools/switch_overrides.py

# The Switch 2 build, in its pinned toolchain (scripts/switch2/build.sh)
python3 chupathingyce/configure.py --console-port port/switch2
ninja switch2
```

Dependency versions are pinned in [UPSTREAM.json](UPSTREAM.json) and nowhere
else. [AGENTS.md](AGENTS.md) has the full development guide:
[GLOSSARY.md](GLOSSARY.md) for the vocabulary, `docs/adr/` for the decision
records, and `port/switch/README.md` and `port/switch/DEKO3D.md` for the
existing renderer and the host/guest split, and
[`port/switch2/README.md`](port/switch2/README.md) for the Switch 2 build, its
pinned toolchain and the artifact audit.

### Deploying to a development console

```sh
python3 tools/switch_deploy.py --target switch2 --build
python3 tools/switch_logs.py --target switch2 --elf build/switch2/warthog.elf
```

The console runs an FTP server (kaiHEN's `ftpd`). Set
`WARTHOG_SWITCH2_HOST` and optionally `WARTHOG_SWITCH2_PORT` before deploying;
the address is never committed. Crash logs must be matched with the same
unstripped ELF.

## How it is built

The port keeps Warthog's existing renderer rather than forking it. Drako3D
preserves Deko3D's public `Dk*` / `dk::*` API, so the Switch 1 renderer
compiles against either library through a thin compatibility header, and only
the genuinely Ampere-specific parts — uncompressed VI2 swapchain images,
explicit descriptor cache invalidation, Ampere DKSH from UAM2 — sit behind a
platform adapter.

The game engine stays an explicitly pinned upstream submodule, the host and
guest boundary keeps Warthog's existing SDL2/SDL3 split, and fixes the console
needs live in `port/switch/overrides/` until upstream takes them. ADR-0001
selects native LP64 and records the `[0x40000000, 0xa0000000)` `StackRegion`
and checkpoint relocation constraints. ADRs 0002–0004 document Drako3D/UAM2,
renderer parity and the SDL seam. The full build, deployment and verification
workflow is in [docs/architecture.md](docs/architecture.md) and
[docs/release-checklist.md](docs/release-checklist.md). [AGENTS.md](AGENTS.md)
states the boundaries and the constraints in full.

## License

Warthog for Switch 2 is free software: you can redistribute it and modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License or (at your option) any
later version (**GPL-3.0-or-later**). It comes with no warranty. The full text
is in [LICENSE](LICENSE).

- **The original Switch port** is
  [thelinkin3000](https://github.com/thelinkin3000)'s work, contributed under
  GPL-3.0-or-later.
- **The game** (`chupathingyce/`) is under its own repository's licence, with
  its third-party code, fonts and art under theirs.
- **The Switch 2 platform work** in this repository is contributed under
  GPL-3.0-or-later.

### Third-party notices

Dependencies are consumed from their own sources except where noted. Their
licences are honoured and notices kept beside any code copied in.

- **Drako3D** — Zlib. `ouncebrew/drako3d`, the Switch 2 low-level GPU API.
- **UAM2** — Zlib, with Mesa's MIT-licensed shader compiler components.
  `ouncebrew/uam2`, the Ampere shader compiler.
- **libounce** — ISC. `ouncebrew/libounce`, the Switch 2 platform layer.
- **libnx** — ISC. devkitPro's library, reached through libounce on Switch 2.
- **ounce-devkit** — MIT. `ouncebrew/ounce-devkit`, the toolchain.
- **OunceVK** — MIT. `ouncebrew/ouncevk`, a documented contingency only.
- **kaiHEN** — GPL-2.0 for the environment itself; `libkaihen`, the client
  library this port links, is ISC. The environment is assumed, never
  modified.
- **dolphin-nx** — GPL-2.0-or-later as a whole; the imported `nx2_platform`
  subset is MIT, from `NaGaa95/dolphin-nx` at
  `7fb685b353e19a9a5848e9bd658945d1f9cd382a`. Its original SPDX headers and
  source attribution are preserved. The upstream `nx2_gameshare` helper
  is also MIT, from the same revision.
- **nanosvg** — Zlib, in `port/switch/third_party`, drawn from upstream's port.

### No console SDK, no game assets

The port is built only with free, legally available tools and libraries.
Nothing from Nintendo's SDK is in this repository and none of it may be
committed. Halo itself is not covered by this licence: it gives no rights in
Halo, its maps or anything else Microsoft owns.

## Credits

- The decompilation: [punpckhdq/halo](https://github.com/punpckhdq/halo) and
  [bnunu/halo-1](https://github.com/bnunu/halo-1), of the Xbox build 2342.
- The game: [ChupathingyCE/chupathingyce](https://github.com/ChupathingyCE/chupathingyce)
  and its contributors, and OpenCE and its contributors before it.
- Warthog, the consoles' line: [Milenko](https://github.com/MrMilenko) and
  contributors.
- The original Switch port and this fork's direct upstream:
  [ChupathingyCE/warthog-switch](https://github.com/ChupathingyCE/warthog-switch),
  maintained by [thelinkin3000](https://github.com/thelinkin3000), with
  **puginatux**.
- The Switch 2 homebrew ecosystem: [ouncebrew](https://github.com/ouncebrew) —
  ounce-devkit, libounce, libkaihen, Drako3D, UAM2, OunceVK and drakotools.
- The Switch 2 reference implementation:
  [NaGaa95/dolphin-nx](https://github.com/NaGaa95/dolphin-nx), for its Drako3D
  integration and its MIT-licensed `nx2_platform` and `nx2_gameshare`
  helpers.
- Additional architectural reference:
  [HDErick/BO2-Requiem-NX](https://github.com/HDErick/BO2-Requiem-NX).
- The Ultrahand package: [hardran3](https://github.com/hardran3)
  ([OpenCE-Ultrahand](https://github.com/hardran3/OpenCE-Ultrahand)).

## Links

- This repository: [thedavidweng/warthog-switch2](https://github.com/thedavidweng/warthog-switch2)
- The upstream Switch port: [ChupathingyCE/warthog-switch](https://github.com/ChupathingyCE/warthog-switch)
- The game: [ChupathingyCE/chupathingyce](https://github.com/ChupathingyCE/chupathingyce)
- The Xbox: [ChupathingyCE/warthog-xbox](https://github.com/ChupathingyCE/warthog-xbox)
- Discord: [discord.gg/chupathingy](https://discord.gg/chupathingy)

## Disclaimer

Halo is a trademark of Microsoft. Nintendo Switch and Nintendo Switch 2 are
trademarks of Nintendo. Warthog for Switch 2 is a fan project. It is not affiliated
with Nintendo, Microsoft, Bungie, 343 Industries, ChupathingyCE or ouncebrew,
and no affiliation, authorisation, sponsorship or endorsement is claimed from
any of them. It includes none of the game's content. The code is released
under the GNU GPL, version 3 or later (see [License](#license)).
