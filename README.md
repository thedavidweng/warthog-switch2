<p align="center"><img src="port/switch/art/icon.jpg" width="120" alt=""></p>

<h1 align="center">Warthog for Switch 2</h1>

<p align="center"><b>Chupathingy on the Nintendo Switch 2, under kaiHEN, playing online with the PCs and the Xbox.</b></p>

<p align="center">
<a href="https://github.com/ChupathingyCE/chupathingyce">The game (Chupathingy)</a> ·
<a href="https://github.com/ChupathingyCE/warthog-switch">Upstream: Warthog for Switch</a> ·
<a href="https://stats.chupathingy.org">Games online now</a> ·
<a href="https://chupathingy.org">chupathingy.org</a> ·
<a href="https://discord.gg/chupathingy">Discord</a>
</p>

<p align="center">
<a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="License: GPL-3.0-or-later"></a>
<a href="https://github.com/thedavidweng/warthog-switch2/actions/workflows/build.yml?query=branch%3Amain+event%3Apush"><img src="https://img.shields.io/github/actions/workflow/status/thedavidweng/warthog-switch2/build.yml?branch=main&event=push&label=build" alt="Build status on main"></a>
<a href="https://discord.gg/chupathingy"><img src="https://img.shields.io/discord/1555995995555365045?label=discord&color=5865F2" alt="Discord"></a>
</p>

Warthog for Switch 2 is the Halo: Combat Evolved decompilation built for the
Nintendo Switch 2, on the same game code as
[Chupathingy](https://github.com/ChupathingyCE/chupathingyce) (the Windows,
Mac, Linux and Android builds) and
[Warthog](https://github.com/ChupathingyCE/warthog-xbox) (the original Xbox).
It runs natively as homebrew on a Switch 2 under
[kaiHEN](https://github.com/ouncebrew/kaihen) — no Xbox emulator, no Android,
no Linux, no remote streaming — and carries the same networking code to join
PC and Xbox games from the **Online Games** list or System Link.

This repository is a fork of
[ChupathingyCE/warthog-switch](https://github.com/ChupathingyCE/warthog-switch)
(Warthog for Switch), keeping its history, authorship and licence. The game is
the `chupathingyce` submodule (`v0.9.1a`), `port/switch/` keeps the original
Switch build intact, and `port/switch2/` holds the Switch 2 platform layer.

You need your own copy of Halo. No game files are included, and nothing from
Nintendo's SDK is used: the port is built with devkitPro's free tools and the
[ouncebrew](https://github.com/ouncebrew) Switch 2 ecosystem (`Ounce`).

## Status

**Pre-release.** The Switch 2 build, packaging, artifact audit and host test
suites pass, and FTP deployment is verified, but interactive campaign,
rendering, input, networking and lifecycle verification on real Switch 2
hardware is still required before cutting the first public `v<version>` tag on
`main`. See [docs/status-matrix.md](docs/status-matrix.md) for the exact
verification state of every subsystem.

- **Engine and ABI:** Native LP64 AArch64 build (`warthog.nro` alone, no
  separate guest ELF), preserving Xbox data layouts with a
  `[0x40000000, 0xa0000000)` `StackRegion`, atomic `.part` checkpoint saves
  and pointer relocation (ADR-0001; `Tested on host`, hardware verification
  pending).
- **Graphics and shaders:** Shares `port/switch/`'s Deko3D renderer through
  Drako3D (`GPU_ARCH=ampere`), with uncompressed VI2 swapchains, explicit
  descriptor and render-target barriers, UAM2 (`DEKO3D=200`, SM 8.6), and an
  isolated Ampere shader cache with CRC recovery and `Compiling shaders: N / M`
  progress UI (ADRs 0002, 0004; `Tested on host`, hardware rendering
  verification pending).
- **Network:** The game's wire, `chupa-44a` (`0.9.1a`), with TLS support via
  `cacert.pem`. Code for **Multiplayer > ONLINE GAMES**, dedicated servers,
  **Link Profile**, System Link LAN and lobby map downloads is in the build
  (`Implemented` / `Tested on host`; live hardware verification pending; see
  [docs/networking.md](docs/networking.md)).
- **Display:** 1080p default in handheld (up to 120 Hz when granted) and up to
  4K60 or 1080p/1440p120 docked with VRR and Smooth Motion
  (`display.interpolation`). Docked 2160p is strictly clamped to 60 Hz, and
  `nwindowGetPresentInterval` reads back the rate VI2 actually grants
  (`Tested on host`, display verification on hardware pending).
- **Controls and input:** Controllers, per-player gyro aiming (`GYRO` page in
  Controls Setup), rumble, native `swkbd` text input, USB/Bluetooth keyboard
  and mouse (degrading gracefully if a kaiHEN host title refuses HID services,
  and refusing blocking `usb:hs` lookups), and Joy-Con 2 `Nmouse` aiming
  (`Tested on host`, console input verification pending).
- **Local multiplayer and GameShare:** 1–4 player split-screen and Switch 2
  GameShare (`Mirror` and dual-swapchain `SeparateViews` on `player1`;
  `Tested on host`, two-console hardware verification pending; see
  [docs/gameshare.md](docs/gameshare.md)).
- **Maps and campaign:** All 10 retail Xbox campaign missions and multiplayer
  maps, unpacked from your `.iso` or `.xiso` disc image at first launch (with
  automatic reuse of compatible `sdmc:/switch/ChupaThingyCE/` data), plus Halo
  PC (version 7) and Custom Edition (version 609) maps in `maps_ce/`
  (`Tested on host`, console playtesting pending).
- **Menus:** Chupathingy's menus, with Switch 2 rows in Video Setup
  (`INTERNAL RESOLUTION`, `OUTPUT REFRESH`, `SMOOTH MOTION`) and the `GYRO`
  page in Controls Setup. There is no `QUIT`: the HOME button is the way out.
- **Updates itself:** Release builds (built with a build number) check
  `thedavidweng/warthog-switch2` `build-<N>` releases at start and stage
  updates (`update.auto` turns that off; `Tested on host`).
- **Not yet supported:** Halo: The Master Chief Collection (version 13) maps
  (see [docs/mcc-investigation.md](docs/mcc-investigation.md)), HOME
  suspend/resume under kaiHEN, atomic custom map installation, and shared
  pre-compiled Ampere shader keys.

## What you need

- A Switch 2 that runs homebrew under [kaiHEN](https://github.com/ouncebrew/kaihen)
  (launched via hbmenu in full-memory title takeover mode).
- About 2 GB free on the SD card, for the extracted maps and the Ampere shader
  cache (or an FTP server such as kaiHEN's `ftpd` for the development loop).
- Your own retail Halo: Combat Evolved Xbox disc. Use the North American (NTSC)
  release, `01.10.12.2276`, as every Chupathingy build and server does; the PAL
  disc's maps work too. Warthog never provides maps, disc images or other game
  data, and never links to them. Don't share yours.
- For online play, a certificate bundle called `cacert.pem`. Startup seeds its
  HTTPS root bundle if `cacert.pem` is absent, or you can provide Mozilla's
  from [curl.se/docs/caextract.html](https://curl.se/docs/caextract.html) or
  your computer's `ca-certificates.crt`.

**Owning Halo on PC or through the Master Chief Collection is not enough on
its own.** The port requires retail Xbox Halo: Combat Evolved disc data; a PC
or MCC installation is not a substitute, and MCC map support is not
implemented.

## Getting started

### Install

Download the Switch 2 preview from [Releases](https://github.com/thedavidweng/warthog-switch2/releases).
Preview builds are installed manually. See the [changelog](CHANGELOG.md) for
changes and known issues.

1. Unpack `warthog-switch2-release.zip` (or `warthog-switch2-debug.zip`) at the
   root of your Switch 2 microSD card. Everything lands under
   `sdmc:/switch/warthog/` with `warthog.nro`, `brokers.txt`, `menus/`,
   `LICENSE` and `THIRD-PARTY-NOTICES.txt`. Native LP64 uses one `warthog.nro`;
   no guest ELF is needed.
2. Add your maps: copy `ui.map`, `bitmaps.map`, `sounds.map`, campaign and
   multiplayer maps into `sdmc:/switch/warthog/maps/`. Or put your retail Xbox
   `.iso` or `.xiso` disc image in `sdmc:/switch/warthog/` and the first launch
   checks free space, unpacks `maps/` (and `bink/`) and cleans up partial
   `.part` files if interrupted. Compatible data under
   `sdmc:/switch/ChupaThingyCE/` is detected and reused automatically.
3. Optional Custom Edition or Halo PC maps go in `sdmc:/switch/warthog/maps_ce/`.
   Put `cacert.pem` at `sdmc:/switch/warthog/cacert.pem` for HTTPS server
   lists and map downloads (startup also seeds it when missing).
4. Start `warthog.nro` from hbmenu in full-memory title takeover mode
   (`Application` or `SystemApplication`), rather than album applet mode.

The first start writes `config.toml` and compiles the Ampere shaders the menus
need with UAM2 (`Compiling shaders: N / M`). The shader cache under
`sdmc:/switch/warthog/shader_cache/` keeps them for next time.

### Updating

Release builds (`HALO_BUILD_NUMBER > 0`) check `thedavidweng/warthog-switch2`
for a newer `build-<N>` release when they start, verify the `OUN0` NRO and
stored ZIP entries, and stage the update (`warthog.nro`, `menus/`,
`brokers.txt`, `LICENSE`, `THIRD-PARTY-NOTICES.txt`) to apply on the next
start. Set `update.auto = false` in `config.toml` to turn the check off.

To update by hand, unzip a newer `warthog-switch2-release.zip` at the root of
the SD card. Your `maps/`, `maps_ce/`, `save/`, `config.toml` and `logs/`
stay untouched.

Builds you compile yourself without `HALO_BUILD_NUMBER` never check for updates.

### Where things go

Everything is in `sdmc:/switch/warthog/`. Nothing is written to NAND, no
privileged background plugin is installed, and no permanent system modification
is required.

| What | Where |
| --- | --- |
| The program | `warthog.nro` |
| Settings | `config.toml` |
| Online brokers | `brokers.txt` |
| Menus | `menus/` |
| Retail maps | `maps/` |
| Custom Edition maps | `maps_ce/` |
| Saves | `save/` |
| Ampere shader cache | `shader_cache/` |
| The Switch 2 host & crash log | `logs/warthog.log` |
| The game's log | `logs/debug.txt` |
| Certificates for online play | `cacert.pem` |
| Licence and notices | `LICENSE`, `THIRD-PARTY-NOTICES.txt` |

### Custom Edition maps

Halo PC (version 7) and Custom Edition (version 609) maps go in
`sdmc:/switch/warthog/maps_ce/`. Put Custom Edition's `bitmaps.map`,
`sounds.map` and `loc.map` in the same folder. Maps in a subfolder are listed
under the folder's name (campaign maps under CUSTOM SINGLEPLAYER, multiplayer
maps under CUSTOM MULTIPLAYER; one level of folders is read), and compatible
`sdmc:/switch/ChupaThingyCE/maps_ce/` maps are reused automatically.

When you join a game with a map you don't have, it is downloaded from the host
while you wait in the lobby (staged with `.part` files).

### The Ultrahand overlay

The engine still builds `overlay_commands.c` (`game.overlay_commands = true` by
default), reading commands from `sdmc:/switch/.packages/halo/overlay` when
present. Whether [OpenCE-Ultrahand](https://github.com/hardran3/OpenCE-Ultrahand)
and Ultrahand Overlay run in a given Switch 2 environment depends on kaiHEN and
the overlay's own Switch 2 support. Set `game.overlay_commands = false` in
`config.toml` to disable it.

## Settings

The settings are in `sdmc:/switch/warthog/config.toml`. The first start writes
it with every setting, commented out at its default. Remove the `# ` in front of
one, change its value and save. Most change at once; the rest take effect at
the next start.

Most settings are the same as on Chupathingy's PC and Android builds. These
are the ones most relevant on Switch 2:

| Setting | Default | What it does |
| --- | --- | --- |
| `display.resolution_limit` | `"1080"` | Internal resolution height: `"480"`, `"720"`, `"900"`, `"1080"`, `"1440"` or `"2160"`, scaled to the output. Handheld draws up to 1080p; docked supports up to 2160p (capped at 60 Hz). |
| `display.refresh_rate` | `0.0` (menu: `60` / `120`) | Requested refresh rate in Hz. 120 Hz is available up to 1440p when granted by VI2; 2160p is clamped to 60 Hz. |
| `display.interpolation` | `true` | Smooth Motion: blend frames between the authoritative 30 Hz simulation ticks. |
| `display.dynamic_resolution` | `false` | Draw one step lower while the frame rate falls under 55, and step back up when there is room. |
| `display.big_sprite_limit` | `8` | The most big sprites drawn in a frame. A big sprite covers more than half the view. The Xbox drew 11. |
| `performance.cpu_clock` | `"stock"` | Switch 2 uses stock `ApmCpuBoostMode_Normal` by default (`"fast_load"` / boost modes may lower GPU clock and `Normal` is always restored on exit). |
| `input.gyro_aim` | `"false"` | Aim with the gyroscope: `"true"` always, `"zoom"` only while zoomed in, `"false"` never. |
| `input.gyro_sensitivity_horizontal` | `1.0` | How far the view turns left and right with the gyroscope, from 0.25 to 10. |
| `input.gyro_sensitivity_vertical` | `1.0` | How far the view turns up and down with the gyroscope, from 0.25 to 10. |
| `input.gyro_invert_horizontal` | `false` | Turn the gyroscope's left and right around. |
| `input.gyro_invert_vertical` | `false` | Turn the gyroscope's up and down around. |
| `game.overlay_commands` | `true` | Take commands from an overlay folder if installed. |
| `game.terminal_output` | `"menus"` | Where the game's messages show at the bottom left: `"menus"`, `"console"`, `"always"` or `"none"`. |
| `debug.log_files` | `true` | Write `logs/debug.txt` and `logs/warthog.log`. With `false`, nothing is kept to say what went wrong. |
| `update.auto` | `true` | Check for a newer `build-<N>` release at start. |

Video Setup has rows for `INTERNAL RESOLUTION`, `OUTPUT REFRESH` and
`SMOOTH MOTION`. The gyro settings are on the `GYRO` page of Controls Setup.
With gyro on, tap D-pad Down to level the view without changing its heading.
Hold it to pause gyro aiming while you reposition the controller, then release
it to resume. The `RECENTER BUTTON` setting can turn off this binding.
There is no `QUIT` on the main menu: press HOME to leave.

The other `debug.*` settings in the file are for finding renderer and
performance problems; leave them at their defaults unless debugging a report.

## Reporting problems

1. Right after the problem, copy `logs/warthog.log` and `logs/debug.txt` from
   `sdmc:/switch/warthog/` to your computer (or pull and symbolize
   `warthog.log` over FTP with `python3 tools/switch_logs.py --target switch2 --elf <matching-warthog.elf>`).
2. Open an issue on
   [thedavidweng/warthog-switch2](https://github.com/thedavidweng/warthog-switch2/issues)
   (never commit or post personal LAN IP addresses or local paths). Include
   the build identifier, Switch 2 firmware, launch context (`AppletType`),
   graphics backend (`Drako3D`), UAM2 revision and granted refresh rate, and
   distinguish CPU exceptions from Drako3D GPU faults.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for the full list. The
common cases:

- **It refuses to launch (restricted applet mode).** Launch `warthog.nro` from
  hbmenu in full-memory `Application` or `SystemApplication` title takeover
  mode under kaiHEN, not album applet mode.
- **It says the maps are missing.** Check `sdmc:/switch/warthog/maps/ui.map`,
  or put your retail Xbox `.iso`/`.xiso` image in `sdmc:/switch/warthog/`.
  Compatible `sdmc:/switch/ChupaThingyCE/maps/` data is reused automatically.
  Halo Trial and MCC version 13 maps are unsupported.
- **Online Games shows no games.** Put `cacert.pem` in
  `sdmc:/switch/warthog/` (startup also seeds it when absent).
- **120 Hz or 4K output.** Docked `3840x2160` is capped at 60 Hz; 120 Hz is
  requested up to 1440p and falls back to 60 Hz if VI2 does not grant it.
- **First launch or level stutters.** Ampere shaders are compiled by UAM2 on
  first use (`Compiling shaders: N / M`) and cached under
  `sdmc:/switch/warthog/shader_cache/`. Corrupt `.dksh` entries are discarded
  and rebuilt automatically.
- **Keyboard, mouse or `Nmouse` not responding.** Some kaiHEN host titles
  refuse `hidInitializeKeyboard` or `hidInitializeMouse`; Warthog degrades
  gracefully without aborting and skips `usb:hs` under kaiHEN's shared SM
  session. Joy-Con 2 `Nmouse` requires controller attachment and a pointing
  surface.

## Building it yourself

Clone with the game submodule:

```sh
git clone --recursive https://github.com/thedavidweng/warthog-switch2.git
cd warthog-switch2
```

(In a clone you already have: `git submodule update --init`. After a `git pull`,
`git submodule update` moves `chupathingyce` to the pinned revision.)

You need Python 3, [ninja](https://ninja-build.org/), `clang`, and the Switch 2
toolchain from [ouncebrew](https://github.com/ouncebrew): `ounce-devkit` with
`libounce`, `libkaihen`, `drako3d`, `uam2` (and `drakotools` for inspection).
`scripts/switch2/Dockerfile` and `scripts/switch2/build.sh` build and run
inside the pinned toolchain container; on a host with the same packages
installed, `WARTHOG_SWITCH2_NATIVE=1` runs natively. The original Switch build
(`ninja switch`) still needs devkitPro and the Android NDK, unchanged from
upstream.

```sh
# The Switch 2 build, in its pinned toolchain (scripts/switch2/build.sh)
scripts/switch2/build.sh image        # build the toolchain image (once)
scripts/switch2/build.sh configure    # configure.py --console-port port/switch2
scripts/switch2/build.sh build        # configure, then ninja switch2
scripts/switch2/build.sh audit        # tools/switch2_audit.py build/switch2

# Or directly on a host with the Switch 2 packages installed:
python3 chupathingyce/configure.py --console-port port/switch2 [--release]
ninja switch2                         # build/switch2/warthog.nro and warthog.elf

# The original Switch build, unchanged from upstream
python3 chupathingyce/configure.py --console-port port/switch
ninja switch

# Documentation, pin, override and host unit tests (no toolchain, no console)
python3 -m unittest discover -s tests
python3 tools/switch_overrides.py
```

Package, audit and deploy over FTP to a console running kaiHEN and `ftpd` (set
`WARTHOG_SWITCH2_HOST` and optionally `WARTHOG_SWITCH2_PORT`; never commit a
console address):

```sh
python3 tools/switch_package.py --target switch2 --out dist/stage --release-dir dist/release --flavor release
python3 tools/switch2_audit.py --package dist/release/warthog-switch2-release.zip --flavor release --symbols dist/release/warthog-switch2-release-symbols.zip
python3 tools/switch_deploy.py --target switch2 --build
python3 tools/switch_logs.py --target switch2 --elf build/switch2/warthog.elf
python3 tools/switch_profile.py --target switch2
```

### How it is built

The port keeps Warthog's existing Deko3D renderer (`port/switch/host/host_dk.c`,
`host_dk_shaders.c`) rather than forking it. Drako3D preserves Deko3D's public
`Dk*` / `dk::*` API, so the same renderer compiles against either library
through a thin compatibility header (`port/switch2/include/deko3d.h`), with
only Ampere-specific parts — uncompressed VI2 swapchain images, explicit
descriptor cache invalidation and Ampere DKSH from UAM2 — behind platform
adapters or `__SWITCH2__` guards. OunceVK is a documented contingency only.

Dependency pins live exclusively in [UPSTREAM.json](UPSTREAM.json). Engine
fixes live in `port/switch/overrides/` and `port/switch2/overrides/` until
upstream takes them. [AGENTS.md](AGENTS.md) and [GLOSSARY.md](GLOSSARY.md)
define the boundaries and vocabulary; `docs/adr/` records architectural
decisions (ADR-0001 on native LP64 and `StackRegion`, ADRs 0002–0004 on
Drako3D/UAM2, the SDL2 host / SDL3 guest seam and renderer parity); and
[docs/architecture.md](docs/architecture.md),
[docs/lifecycle.md](docs/lifecycle.md),
[docs/upstream-sync.md](docs/upstream-sync.md),
[docs/release-checklist.md](docs/release-checklist.md),
[docs/campaign-status.md](docs/campaign-status.md) and
[`port/switch2/README.md`](port/switch2/README.md) cover the build,
verification and release rules in full (alongside upstream's
[port/switch/README.md](port/switch/README.md) and
[port/switch/DEKO3D.md](port/switch/DEKO3D.md)).

## Generative AI

Both the upstream Switch port and the Switch 2 port were built with heavy use
of generative AI tools, following the game's
[policy](https://github.com/ChupathingyCE/chupathingyce/blob/main/CONTRIBUTING.md#using-ai-tools):
a person decides what to build, reviews every change, verifies it and is
responsible for it.

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
  source attribution are preserved. The upstream `nx2_gameshare` helper is
  also MIT, from the same revision.
- **nanosvg** — Zlib, in `port/switch/third_party`, drawn from upstream's port.

### No console SDK, no game assets

The port is built only with free, legally available tools and libraries.
Nothing from Nintendo's SDK is in this repository and none of it may be
committed. Halo itself is not covered by this licence: it gives no rights in
Halo, its maps or anything else Microsoft owns.

## Support

Chupathingy is free and always will be. Support through
[Ko-fi](https://ko-fi.com/milenko) or [Patreon](https://www.patreon.com/c/chupathingy)
goes to running the site and the servers. If there's a specific developer or
port you'd like to support, ask them: they may not be part of our community.

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
  integration and its MIT-licensed `nx2_platform` and `nx2_gameshare` helpers.
- Additional architectural reference:
  [HDErick/BO2-Requiem-NX](https://github.com/HDErick/BO2-Requiem-NX).
- The Ultrahand package: [hardran3](https://github.com/hardran3)
  ([OpenCE-Ultrahand](https://github.com/hardran3/OpenCE-Ultrahand)).

## Links

- This repository: [thedavidweng/warthog-switch2](https://github.com/thedavidweng/warthog-switch2)
- The upstream Switch port: [ChupathingyCE/warthog-switch](https://github.com/ChupathingyCE/warthog-switch)
- The game: [ChupathingyCE/chupathingyce](https://github.com/ChupathingyCE/chupathingyce)
- The Xbox: [ChupathingyCE/warthog-xbox](https://github.com/ChupathingyCE/warthog-xbox)
- Games online now: [stats.chupathingy.org](https://stats.chupathingy.org)
- Discord: [discord.gg/chupathingy](https://discord.gg/chupathingy)
  (#warthog-support for help, #warthog-dev for development)

## Disclaimer

Halo is a trademark of Microsoft. Nintendo Switch and Nintendo Switch 2 are
trademarks of Nintendo. Warthog for Switch 2 is a fan project. It is not affiliated
with Nintendo, Microsoft, Bungie, 343 Industries, ChupathingyCE or ouncebrew, and no affiliation, authorisation, sponsorship or endorsement is
claimed from any of them. It includes none of the game's content. The code is
released under the GNU GPL, version 3 or later (see [License](#license)).
