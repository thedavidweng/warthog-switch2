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

**Pre-release. The Switch 2 build is under active development and is not yet
released.** Nothing here is a promise that the port runs a full campaign
today. This table is the current verification state, using the status words
defined in [GLOSSARY.md](GLOSSARY.md); each claim is only as strong as the
evidence behind it.

| Area | Status |
|---|---|
| Upstream Switch port (`ninja switch`) | Implemented — upstream's code, untouched by this repository |
| Switch 2 toolchain, `ninja switch2`, packaging | Compiled — the program builds, links and passes the artifact audit; not yet run on a console |
| Drako3D renderer and Ampere shader compilation | Not yet supported — in progress |
| Gameplay, campaign, multiplayer on Switch 2 | Not yet supported |
| Switch 2 display modes (1080p120 handheld, 4K60 / 1440p120 docked, VRR) | Not yet supported |
| Joy-Con 2 `Nmouse` aiming | Not yet supported |
| GameShare local multiplayer | Not yet supported |

Nothing here has been run on Switch 2 hardware yet. The upstream Switch port is
carried in this repository untouched, which is not the same as this fork having
rebuilt it. The Switch 2 build graph, renderer and platform work are being
added under the tickets of
[issue #1](https://github.com/thedavidweng/warthog-switch2/issues/1), and each
row above moves up a level only when the evidence behind it exists.

There is no download yet. When a build is published it will be a Switch 2
`OUN0` NRO with valid NACP metadata, no proprietary assets, and a
feature-status matrix carrying the same evidence standard as this table.

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
its own.** The port reads Xbox disc data; a PC or MCC installation is not a
substitute, and MCC map support is not implemented.

## Installation

Not available yet. The layout the port installs to, and the one a release
will use, is:

```
sdmc:/switch/warthog/
    warthog.nro
    warthog_guest.elf        # present when the ILP32 guest model is selected
    config.toml
    brokers.txt
    menus/
    maps/
    maps_ce/
    save/
    logs/
```

Everything stays inside that folder. Uninstalling means deleting it. Nothing
is written to NAND, no privileged background plugin is installed, and no
permanent system modification is required.

`maps/` holds the retail maps unpacked from your disc, `maps_ce/` holds Halo
PC Custom Edition maps, `save/` holds saves and profiles, and `logs/` holds
the logs to attach to a bug report. Existing extracted game data from
`sd:/switch/ChupaThingyCE/` is reused where it is compatible rather than
converted; the details land with the data-workflow work.

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
python3 tools/switch_deploy.py --host <switch2-ip> --port <port> \
    --destination /switch/warthog build/switch2/warthog.nro
python3 tools/switch_logs.py
```

The console runs an FTP server (kaiHEN's `ftpd`, or `sw2transfer`). Until the
Switch 2 development loop lands, the deploy tool still defaults to the
original Switch's paths, so the destination is passed explicitly. The address
is passed in, or set in `WARTHOG_SWITCH2_HOST` and `WARTHOG_SWITCH2_PORT`; it
is never committed.

## How it is built

The port keeps Warthog's existing renderer rather than forking it. Drako3D
preserves Deko3D's public `Dk*` / `dk::*` API, so the Switch 1 renderer
compiles against either library through a thin compatibility header, and only
the genuinely Ampere-specific parts — uncompressed VI2 swapchain images,
explicit descriptor cache invalidation, Ampere DKSH from UAM2 — sit behind a
platform adapter.

The game engine stays an explicitly pinned upstream submodule, the host and
guest boundary keeps Warthog's existing SDL2/SDL3 split, and fixes the console
needs live in `port/switch/overrides/` until upstream takes them. Both
candidate ABI models — Warthog's ILP32 guest inside an LP64 host, and building
the game natively as LP64 — are still under evaluation, and the measured
decision will be recorded in `docs/adr/`. [AGENTS.md](AGENTS.md) states the
boundaries and the constraints in full.

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

None of the following is vendored into this repository; the build consumes it
from its own source. Their licences are honoured and their notices kept beside
any code that is copied in.

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
- **dolphin-nx** — GPL-2.0-or-later as a whole; `NaGaa95/dolphin-nx`'s
  `nx2_platform` and `nx2_gameshare` modules are **MIT** and are adopted
  under MIT with their copyright, `SPDX-License-Identifier: MIT` header and an
  attribution comment naming the upstream and the reviewed revision. MIT code
  stays MIT and is not relicensed.
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
