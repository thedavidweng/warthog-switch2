# Architecture

The repository has three boundaries. The `chupathingyce/` submodule is the
unchanged engine. `port/switch/` contains shared console code and the
Deko3D renderer. `port/switch2/` contains the Switch 2 build graph and
platform adapters. The Switch 2 layer does not leak into gameplay code.

ADR-0001 selects native LP64. The source rewrite preserves the Xbox data
layouts, reserves `[0x40000000, 0xa0000000)` for the `StackRegion`, and
relocates checkpoint pointers. ADR-0002 and ADR-0004 keep one shared renderer:
Drako3D preserves the Deko3D API, UAM2 emits SM 8.6 `DEKO3D=200` `.dksh`,
and explicit barriers protect descriptor and render-target caches.

ADR-0003 keeps the SDL seam. Namespaced `sdl2_host_SDL_*` functions answer the
SDL3 guest calls through `switch2_sdl3_bridge.c`. The MIT `nx2_platform` and
`nx2_gameshare` helpers supply platform and GameShare pieces with their
provenance intact.

`switch2_perf` records timing and counters. Developers can fetch profiles with
`python3 tools/switch_profile.py --target switch2`. The stock
`ApmCpuBoostMode_Normal` is the baseline and is restored on every exit path.
Console FPS and frame-time numbers are published only after a real Switch 2
run produces `perf_report.json`.

Host tests cover the build graph, probes, lifecycle, input, display, renderer,
gameplay, networking, packaging and release audit. The release runbook adds
debug and release builds, package audits, and interactive console gates.
