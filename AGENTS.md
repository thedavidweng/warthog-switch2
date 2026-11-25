# AGENTS.md — Warthog for Switch 2

A native Nintendo Switch 2 port of Warthog, the console line of the
ChupathingyCE Halo: Combat Evolved decompilation. This file is the working
guide for contributors and coding agents: what the project is, where the
boundaries are, what may be changed and how the work is verified. The
authoritative spec is issue #1; the tickets under it are the units of work.

Vocabulary is fixed by `GLOSSARY.md`. Decisions with lasting consequences are
ADRs in `docs/adr/`. Dependency versions live only in `UPSTREAM.json`.

## Scope

In scope:

- Warthog's own console code (`port/switch/`), carried forward for Switch 2,
  and a Switch 2 platform layer beside it.
- Drako3D rendering for Switch 2, sharing Warthog's Deko3D renderer rather
  than forking it, with Ampere shader compilation through UAM2.
- Switch 2 presentation (1080p/120 Hz handheld, up to 4K60 and
  1080p/1440p120 docked with VRR), Joy-Con 2 `Nmouse` aiming, lifecycle and
  clock handling, packaging, and the FTP development loop.
- The optional GameShare local-session feature, after gameplay and lifecycle
  work.

Out of scope, and not to be started without reopening the spec:

- Another Halo decompilation or an independent engine fork.
- An Xbox emulator, Android, Linux or remote streaming as the way Halo runs.
- Halo 2+, Halo: CEA remastered graphics, custom firmware, kaiHEN
  modifications, or persistent privileged background plugins.
- Distributing commercial game assets, Maxwell DKSH caches, or anything from
  Nintendo's SDK; promising ban-free online play; requiring overclocking.
- Importing Dolphin's LSFG or image-based frame generation, importing the full
  Mesa graphics stack only to obtain a shader compiler, or advertising 4K120.

## Engine and platform boundary

Three layers, and a change belongs to exactly one of them:

| Layer | Where | Rule |
|---|---|---|
| Shared engine | `chupathingyce/` submodule | Upstream's. Never edited in place; the pin moves instead. |
| Shared console code | `port/switch/` (guest + host) | Warthog's Deko3D renderer and console adaptations. Shared by both consoles; changes here must keep `ninja switch` working. |
| Switch 2 platform | `port/switch2/` | The Switch 2 build graph and platform adapters: window, display modes, clocks, `Nmouse`, GameShare, lifecycle. Created by ticket #3, and nothing outside `port/switch2/` may assume the rest of it exists. |

The engine stays the authoritative game. Platform-specific code does not leak
into shared gameplay code, and generally useful fixes are separable into
focused upstream pull requests against `ChupathingyCE/chupathingyce`.

Two seams carry most of the port:

- **Host/guest boundary.** Warthog's existing SDL2 host and SDL3 guest split
  is kept unless evidence justifies migrating. The host answers the guest's
  SDL3 calls; nothing above that seam needs to know which console it is on.
- **Renderer boundary.** `port/switch/host/host_dk.c` and `host_dk_shaders.c`
  speak Deko3D. On Switch 2 a thin include directory puts `deko3d.h` on
  `drako3d.h` and `deko3d.hpp` on `drako3d.hpp`, so the same renderer source
  compiles against either library.

## Shared Deko3D / Drako3D renderer

Warthog's Deko3D renderer is the source of truth for both consoles. Drako3D
preserves Deko3D's public `Dk*` / `dk::*` API, so the renderer is adapted, not
duplicated: do not create a second copy of it for Switch 2.

What genuinely differs on Ampere, and belongs behind a platform adapter or a
`__SWITCH2__` guard with a comment naming the reason:

- **Swapchain images are uncompressed on Switch 2 VI2.** Do not pass
  `DkImageFlags_HwCompression` under `__SWITCH2__`; use
  `DkImageFlags_UsageRender | DkImageFlags_UsagePresent |
  DkImageFlags_Usage2DEngine`.
- **Descriptor caches need explicit invalidation.** Rewriting descriptor rings
  in place does not invalidate Ampere's texture header and sampler caches;
  emit `dkCmdBufBarrier(cmdbuf, DkBarrier_None,
  DkInvalidateFlags_Descriptors)` at command-list start and on ring reuse.
- **Shaders are Ampere DKSH (`DEKO3D=200`).** Maxwell binaries are never
  loaded or distributed. The shader cache path carries the GPU architecture
  and the UAM2 revision (`HOST_DK_UAM_COMMIT` becomes `"ampere-<uam2-12hex>"`)
  so the two can never collide.
- **Shader compile concurrency is re-measured.** Do not carry Switch 1 UAM
  worker counts and allocators over without evidence.

OunceVK is a documented contingency only. It is not a second production
renderer, and the build does not probe Vulkan or GLES merely to satisfy a
checklist.

## Dependency pinning authority (`UPSTREAM.json`)

`UPSTREAM.json` is the only place a dependency version is written down. It
records, with full commit hashes:

- `upstream` — `ChupathingyCE/warthog-switch` at
  `366f43cbe060fcc554c00d834075d5d8f7f8e534` (`build-7`, `0.9.1a`,
  GPL-3.0-or-later).
- `submodules.chupathingyce` — the engine, pinned at
  `2e5eac00e3d6655e094fbbcd13253ac2b10ee773` (v0.9.1a), GPL-3.0-or-later.
- `dependencies` — the ouncebrew components the build consumes:
  `ounce-devkit`, `libounce`, `kaihen`, `drako3d` (the production renderer),
  `uam2`, `drakotools` and `ouncevk` (contingency).
- `references` — `NaGaa95/dolphin-nx` `1.2.3` and `HDErick/BO2-Requiem-NX`
  `0.4.2`, with what each is a reference for.

Rules:

- Change a pin in `UPSTREAM.json` in the same commit that changes the build.
- Never let a version float: no branches, no `latest`, no tags where a commit
  is available.
- A dependency bump that changes generated shader binaries or the ABI also
  bumps the shader cache key.
- `docs/adr/` records why a pin was chosen when the reason is not obvious.
  `UPSTREAM.json` records what the pin is.

## MIT helper provenance

`NaGaa95/dolphin-nx` (`7fb685b353e19a9a5848e9bd658945d1f9cd382a`, `1.2.3`,
GPL-2.0-or-later) ships two files that are MIT-licensed and are meant to be
reused: `Source/Core/Common/nx2_platform.{c,h}` and
`Source/Core/Common/nx2_gameshare.{c,h}`.

When adopting a subset of either:

- Keep the file's copyright line and its
  `SPDX-License-Identifier: MIT` header.
- Keep an attribution comment naming `NaGaa95/dolphin-nx` and the revision the
  code came from.
- Keep the imported filenames and symbols verbatim. Their prefix is the
  upstream helper's own naming, not this project's branding, and must not
  spread beyond those files.
- Prefer the current `libounce` API where a historical workaround in the
  helper has been superseded, and say so in a comment when it is.
- MIT code stays MIT. It is not relicensed under the project's GPL-3.0-or-later.

What the helpers are useful for: core-mask discovery (`InfoType_CoreMask`),
display and VRR pacing, GPU/VI2 handover, graceful refusal of unavailable
`hidInitializeKeyboard`/`hidInitializeMouse` services, refusal of blocking
`usb:hs` service lookups under kaiHEN's shared SM session, exit pthread
tracking and stack cleanup, `ApmCpuBoostMode_Normal` restoration, and the
GameShare host path.

## Upstream compatibility

The fork keeps working as an upstream consumer:

- **`ninja switch` keeps building.** `port/switch/` and its build graph stay
  unchanged in behaviour. A shared change that breaks the original Switch
  build is a regression, not a trade-off.
- **The engine pin is the only engine change.** The submodule stays at the
  revision in `UPSTREAM.json`.
- **Fixes the console needs live in `port/switch/overrides/`** (and
  `port/switch2/overrides/` for Switch 2-only fixes), each a whole copy of the
  fixed file, compiled in the game file's place. Every override is listed in
  that folder's `README.md` with what it fixes and where it is going.
  `python3 tools/switch_overrides.py` lists them and fails when one no longer
  differs from upstream's file (upstream has the fix: repin, delete the
  override), when its game file is gone, or when it is not listed.
- **New upstream releases are consumed, not reconstructed.** Repin the
  submodule, drop the overrides upstream has taken, and re-run the tests.
- **Generally useful fixes go upstream** as focused pull requests rather than
  living here forever.

## Decision records (`docs/adr/`)

Decisions that would be expensive to reverse live in `docs/adr/`, one file per
decision, numbered, in the format `NNNN-short-title.md`: the context, the
options considered, the decision, and the consequences.

The process:

1. Check `GLOSSARY.md` first. If the concept has a name, use that name; if the
   decision contradicts an existing ADR, say so explicitly rather than
   quietly overriding it.
2. Write the ADR before or with the change, not months after it. Evidence
   that decided it (measurements, hardware probes, upstream issues) goes in
   the ADR.
3. Superseding an ADR means a new ADR that names the old one, not an edit to
   history.
4. A new domain term goes into `GLOSSARY.md` in the same change that
   introduces it. `_Avoid_:` lines are what stop the codebase growing a second
   name for the same thing.

Open decisions the spec already names, which must land as ADRs before the
code commits to an answer: the ABI model (ILP32 guest in an LP64 host versus
native LP64), the renderer (Drako3D with Ampere DKSH through UAM2), and the
SDL split (SDL2 host with an SDL3 guest versus native SDL3).

## Build and test

The host toolchain is Linux or macOS with Python 3, `ninja`, `clang`, and a
Docker (or native) install of `ounce-devkit`. Nothing from Nintendo's SDK is
ever used.

```sh
# The original Switch build, unchanged (upstream's own requirements apply)
python3 chupathingyce/configure.py --console-port port/switch
ninja switch

# Repository documentation and pin checks; no toolchain, no console
python3 -m unittest discover -s tests

# The port's Python compiles
python3 -m py_compile port/switch/build.py port/switch2/build.py tools/*.py

# Overrides are still needed and still listed
python3 tools/switch_overrides.py

# The Switch 2 build, in its pinned toolchain (scripts/switch2/build.sh)
python3 chupathingyce/configure.py --console-port port/switch2
ninja switch2                       # build/switch2/warthog.nro and warthog.elf
```

`ninja switch2` is the target the Switch 2 build graph provides. Its output
lives under `build/switch2/` and never collides with `build/switch/`. A
`--release` build differs from the debug build only in optimisation and in the
assertion behaviour; both produce matching symbol files.

## Platform constraints

These are properties of the target, not bugs to work around:

- **No unpermitted syscalls.** kaiHEN does not grant the process-memory and
  fastmem syscalls (`0x73`–`0x75`, `0x77`, `0x78`) that the original Switch
  port relied on, and calling one terminates the process instead of returning
  an error. Check `envIsSyscallHinted` before invoking anything optional, and
  design around a capability being absent rather than assuming it.
- **Executable guest memory is the hard constraint.** Where RX memory can be
  placed decides whether the ILP32 guest model is viable; that is what the
  ABI ADR has to answer with measurements.
- **HID services may refuse.** `hidInitializeKeyboard` and
  `hidInitializeMouse` abort the process when the kaiHEN host title refuses
  them; wrap and degrade. A blocking `usb:hs` lookup under kaiHEN's shared SM
  session poisons every later homebrew program until reboot, so refuse it.
- **Clocks are explicit.** Stock `Normal` is the baseline. `CancelCpuBoostMode`
  leaves `FastLoad` active, which lowers the GPU clock, so restore
  `ApmCpuBoostMode_Normal` explicitly on every exit path.
- **The refresh rate is whatever was granted.** Read it back with
  `nwindowGetPresentInterval` and fall back to 60 Hz; never assume 120 Hz, and
  never advertise 4K120.
- **hbmenu runs the next NRO in the same process.** Returning from the
  application must join or pause threads, release Drako3D and VI2 window
  resources, and finalise HID and audio.
- **No NAND writes, no privileged plugins, no permanent system modification.**

## Licensing rules

- The project is **GPL-3.0-or-later** (see `LICENSE`). Contributions are
  accepted under it.
- Third-party code keeps its own licence, with its notice beside it and its
  terms honoured: Zlib (Drako3D, UAM2), ISC (libounce, libnx), MIT
  (ounce-devkit, OunceVK, the dolphin-nx helpers, Mesa), GPL-2.0 (kaiHEN
  itself, referenced but not distributed), GPL-2.0-or-later (dolphin-nx).
- **No console SDK, no proprietary assets.** Nothing from Nintendo's SDK is
  committed, and no Halo map, disc image or game data is ever distributed.
- A new dependency is added to `UPSTREAM.json` with its licence, and its
  notice is added to the README's third-party list, in the same change.

## Real-hardware workflow

Every graphical and lifecycle claim is eventually checked on a console. The
loop is:

1. `ninja switch2`.
2. Deploy over FTP to a console running kaiHEN with `ftpd` (and `sw2transfer`
   where the environment provides it). Until the Switch 2 dev loop lands,
   `tools/switch_deploy.py` still defaults to the original Switch's paths, so
   point it at the Switch 2 card explicitly:
   `python3 tools/switch_deploy.py --host <switch2-ip> --port <port>
   --destination /switch/warthog build/switch2/warthog.nro`.
3. Read the logs back with `tools/switch_logs.py`; symbolize a crash against
   the matching unstripped ELF.
4. Record what was observed: the build identifier, the firmware, the launch
   context (`AppletType`), the graphics backend, the shader compiler revision,
   and the actual refresh rate.

`WARTHOG_SWITCH2_HOST` and `WARTHOG_SWITCH2_PORT` are the environment
variables the Switch 2 tooling reads for the console's address, so no command
line and no committed file has to carry it.

Rules for hardware work:

- **Never commit a personal LAN address, hostname, path or screenshot
  containing one.** Use `<switch2-ip>` in documentation and an environment
  variable in scripts. `tests/test_repo_docs.py` fails when a committed
  document contains one.
- **Game data stays out of the repository.** Extract a disc image only to a
  temporary directory outside the repository, and delete it when the test is
  done.
- **A feature is not "hardware-tested" without hardware evidence.** Use the
  status words in `GLOSSARY.md` exactly; `Compiled` and `Tested on host` are
  not `Tested on hardware`.
- Distinguish CPU exceptions from GPU faults, and record which was seen.

## Release requirements

A release is not a build that happened to work. Before publishing:

- Reproducible debug and release builds from the pins in `UPSTREAM.json`, in
  the pinned `ounce-devkit` image.
- Artifact audit: Switch 2 linkage only (`libounce`, `libdrako3d`; no
  accidental original-Switch `libnx` linkage), valid Switch 2 (`OUN0`) NRO
  and NACP metadata with the application name, author, version and icon.
- No Maxwell DKSH binary anywhere in the package, and a shader cache that is
  keyed by architecture, compiler revision, shader ABI and generator revision.
- Licence and attribution notices present in the package: GPL-3.0-or-later,
  plus the Zlib, ISC and MIT notices of the dependencies and the MIT
  provenance of the dolphin-nx helpers.
- Matching debug symbols published beside the release, and checksums for
  every artifact.
- Self-update confined to this repository's verified Switch 2 release
  artifacts, preserving the user's maps, saves, profiles and settings.
- An honest feature-status matrix using the `GLOSSARY.md` status words, with
  the verification evidence behind each claim and the known gaps stated.
- Zero proprietary game or console assets in the package, and no
  affiliation claim with Nintendo, Microsoft, ChupathingyCE or ouncebrew.
- `ninja switch` still builds, so the original Switch port is not collateral
  damage.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for `thedavidweng/warthog-switch2`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) map to labels of the same name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
