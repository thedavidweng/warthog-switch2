# Warthog for Switch 2

The Nintendo Switch 2 port of Warthog, the console line of the ChupathingyCE
Halo: Combat Evolved decompilation. This glossary fixes the vocabulary the
spec, the tickets, the documentation and the code share, so the port does not
invent a second name for something the upstream already has.

Terms are the ones this repository uses in issue titles, ADRs, commit
messages and code. `_Avoid_:` lists the words that mean something else here,
or nothing.

## The project

**Warthog for Switch 2**:
This repository's application: ChupathingyCE's engine running natively on a
Nintendo Switch 2 under kaiHEN, with no emulator, Linux, Android or streaming
in between.
_Avoid_: Warthog NS2, Halo Switch 2, the Switch 2 port (unqualified)

**Warthog for Switch**:
The upstream original-Switch port by `ChupathingyCE/warthog-switch` that this
repository forks and keeps building with `ninja switch`.
_Avoid_: Switch 1 port, old port, upstream port

**ChupathingyCE**:
The game engine and its decompilation, consumed as the pinned `chupathingyce`
submodule and never forked here. The `CE` in the name is the engine's, not a
reference to Halo: Custom Edition.
_Avoid_: the game code, the engine fork, OpenCE

**switch2**:
The platform identifier this repository uses in paths, targets, options and
configuration (`port/switch2/`, `ninja switch2`, `--switch2`).
_Avoid_: nx2, NS2, ns2

**Ounce**:
The Switch 2 homebrew development codename, used where the hardware or the
ecosystem is meant: ounce-devkit, `[ounce]` packages, OunceVK.
_Avoid_: ounce (lower case, as a platform name), Switch 2 SDK

**NX2**:
Not a name this project uses. `NX` is the original Switch's development
codename, so `NX2` branding would be wrong in every user-facing place.
_Avoid_: using it in a menu, a filename, an option or a release

## Graphics and shaders

**Deko3D**:
The original Switch's low-level GPU API (`libdeko3d`, devkitPro). Warthog's
existing renderer is written against it, and that renderer stays the source
of truth for both consoles.
_Avoid_: Switch 1 renderer (as a separate thing), the old backend

**Drako3D**:
ouncebrew's native Ampere (GA10F) low-level GPU API, which preserves Deko3D's
public `Dk*` / `dk::*` interface. The port's production renderer on Switch 2.
_Avoid_: Vulkan, the new renderer, NS2 deko3d

**Ampere**:
The Switch 2's GPU architecture (GA10F, SM 8.6), as opposed to the original
Switch's Maxwell.
_Avoid_: NS2 GPU, next-gen GPU

**DKSH**:
Deko3D's compiled shader binary format. Maxwell and Ampere binaries are not
interchangeable, so a DKSH is only ever valid for the architecture, compiler
revision, shader ABI and generator revision that produced it.
_Avoid_: shader blob, shader file

**UAM2**:
ouncebrew's Ampere shader compiler, defining `DEKO3D=200` and emitting SM 8.6
DKSH, where the original Switch's UAM defines `DEKO3D=100`.
_Avoid_: UAM (unqualified, when the Switch 2 compiler is meant), NAK

**Shader cache key**:
The identity a compiled shader is stored under: GPU architecture, compiler
revision, shader ABI, generator revision and compile configuration. A key
that omits any of them is a bug, not an optimisation.
_Avoid_: cache name, shader hash

**OunceVK**:
ouncebrew's NVK Vulkan 1.4 and Zink GLES 3.2 runtime. A documented
contingency only, if Drako3D hits demonstrated hardware blockers; the port
ships one production renderer.
_Avoid_: the graphics backend, the Vulkan port, Vulkan-first

## Platform and runtime

**kaiHEN**:
The pre-existing Switch 2 homebrew environment the port runs under, assumed
and never modified, together with `libkaihen`, the client library it exposes.
_Avoid_: CFW, jailbreak, exploit

**libounce**:
The Switch 2 platform API layer, libnx-compatible, that provides the window,
HID, filesystem and memory services this port calls.
_Avoid_: the SDK, libnx (when the Switch 2 layer is meant)

**ILP32 guest**:
Warthog's existing model: the game compiled as 32-bit-pointer AArch64 code
(`arm64_32`, built with the Android NDK's clang) and run inside an LP64
homebrew host that answers its calls. It keeps the Xbox's 32-bit data layouts
but needs executable guest memory mapped below 4 GB.
_Avoid_: 32-bit build, the guest (unqualified, when the ABI is the point)

**LP64**:
The 64-bit-pointer AArch64 model devkitA64 and every Switch 2 NRO use. Native
LP64 means building the game itself that way, which needs no runtime
executable-memory publication but has to keep the Xbox's data layouts intact
another way. Both models are candidates until ADR-0001 records the measured
decision.
_Avoid_: 64-bit build, native (unqualified)

**Guest**:
The game image (`warthog_guest.elf`) under the ILP32 model. Under native LP64
there is no separate image, so the word does not apply.
_Avoid_: the game binary, the payload

**Host**:
The homebrew program (`warthog.nro`) that owns the process: window, GPU,
filesystem, input and the shims the guest calls.
_Avoid_: launcher, wrapper, loader

**Nmouse**:
libounce's Joy-Con 2 mouse interface (`hidInitializeNmouse` and friends),
fed into Halo's relative mouse path as deltas.
_Avoid_: pointer mode, Joy-Con mouse, touch input

**GameShare**:
Horizon's native local-session sharing (`gameshare` / `stpl`), letting a
Switch 2 host give a second console an independent view of a local match.
_Avoid_: remote play, streaming, netplay

## Status and verification

Every capability is reported as exactly one of these. A claim without the
evidence behind it is a bug in the documentation.

**Implemented**:
The code exists and is reachable in a build.
_Avoid_: done, finished

**Compiled**:
The code builds and links for Switch 2, and nothing more has been shown.
_Avoid_: works, builds fine

**Tested on host**:
The behaviour was observed on a development machine, not on a console.
_Avoid_: tested, passing

**Tested on hardware**:
The behaviour was observed on a real Switch 2, with the build identifier and
the evidence recorded.
_Avoid_: verified, confirmed working

**Verified against upstream**:
The behaviour was compared with the upstream Warthog or ChupathingyCE result
and matches.
_Avoid_: parity (unqualified), same as Switch 1

**Not yet supported**:
The feature is planned or accepted in the spec and is absent today. Say so
plainly rather than describing the intent as if it were the state.
_Avoid_: TODO, coming soon, WIP
