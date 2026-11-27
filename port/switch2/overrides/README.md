# Switch 2 overrides

Whole-file fixes to the engine belong here until upstream takes them. Each
override must be listed below with its purpose and upstream destination.
`python3 tools/switch_overrides.py` checks both console override directories.

## port/linux/src/port_config.c

Uses Switch 2 defaults: 1080p handheld rendering, Switch 2 display mode
help, and stock `Normal` clock policy. The original Switch configuration keeps
its 720p and legacy clock choices. This can be proposed upstream with a
platform-specific configuration target.

## port/linux/src/msvc_crt.c

Uses GCC AArch64 register instructions for the Switch 2 floating-point control
word. This can be proposed upstream for GCC AArch64 builds.

## port/linux/src/sdl_platform.c

Omits the POSIX signal watchdog on Switch 2, whose Newlib signal API lacks
the required sigaction fields, and skips OpenGL function loading for the
Drako3D renderer. This can be proposed upstream for the port.

## port/linux/src/d3d8_resources.c

Uses a 32-bit format argument after the LP64 source rewrite and tracks LP64
`D3DDevice_CreateIndexBuffer` allocations so the Drako3D guest treats dynamic
index buffers as inline rather than fixed contiguous geometry. This can be
proposed upstream for the LP64 build.

## port/linux/src/xbox_heap.c

Commits the LP64 Xbox heap in 1 MiB increments on Switch 2. This
platform-specific change can be proposed upstream with the Switch 2 memory
adapter.

## port/linux/src/xbox_memory.c

Reserves the Switch 2 address window and commits contiguous and Custom Edition
tag-cache pages on demand. This platform-specific change can be proposed
upstream with the Switch 2 memory adapter.

## port/linux/include/halo_linux_prefix.h

Adapts the LP64 prefix to Newlib and the Switch 2 address window. This
platform-specific change can be proposed upstream with the Switch 2 port.

## source/interface/terminal.c

Uses the native variadic argument type for Switch 2 status lines. This ABI
fix can be proposed upstream with the Switch 2 port.

## port/linux/game/network_distributed.c

Avoids calling the chat notice when chat is disabled. This can be proposed
upstream for console builds.

## port/linux/game/msvc_comdat.c

Emits weak definitions of header inline functions for Switch 2's GCC build.
This can be proposed upstream with the Switch 2 port.

## source/saved games/game_state_xbox.c

Writes persistent checkpoints atomically through a synced `.part` file and removes interrupted writes before loading.

## source/saved games/game_state.c

Relocates LP64 native pointers in saved memory pools and LRUV caches before validating a checkpoint image.

## port/linux/src/xinput_sdl.c

Defaults the Switch 2 controller prompt scheme to `PROMPT_SCHEME_NINTENDO`
before the first input event so menu and overlay prompts match physical Switch
buttons immediately on boot. This can be proposed upstream under
`HALO_SWITCH_CONSOLE`.

## port/linux/game/menu_tags.c

Draws Nintendo Switch overlay button glyphs (`B` select, `A` back) in classic
Xbox and Gearbox menu footers as well as modern Chupathingy menus when
`platform_prompt_scheme()` is `PROMPT_SCHEME_NINTENDO`. This can be proposed
upstream for console prompt parity.

## source/interface/hud_messaging.c

Draws Nintendo Switch overlay button glyphs (`B`, `A`, `Y`, `X`, `L`, `R`, `ZL`,
`ZR`, `+`, `−`) instead of raw Xbox sprites in campaign/gameplay HUD prompts
when `platform_prompt_scheme()` is `PROMPT_SCHEME_NINTENDO`. This can be
proposed upstream for console prompt parity.

## source/interface/ui_widget.c

Draws Nintendo Switch overlay button glyphs instead of raw Xbox `iface_map2`
sprites inside inline menu and pause dialog text when `platform_prompt_scheme()`
is `PROMPT_SCHEME_NINTENDO`. This can be proposed upstream for console prompt
parity.

## server/src/server_commands.c

Uses a 32-bit unsigned literal (`0U`) in `command_banlist` after the LP64
source rewrite converts `%lu` to `%u`. This can be proposed upstream for the
LP64 build.

## source/game/player_control.c

Applies configured Switch 2 zoom sensitivity multipliers to optical mouse and
gyroscope aiming when zoomed in. This can be proposed upstream under
`HALO_SWITCH_CONSOLE`.

## port/linux/game/menu_functions.c

Exposes the fourth Switch 2 controller settings page (`JOY-CON MOUSE`) and its
help string in Controls Setup. This can be proposed upstream under
`HALO_SWITCH_CONSOLE`.
