# Switch 2 overrides

Whole-file fixes to the engine belong here until upstream takes them. Each
override must be listed below with its purpose and upstream destination.
`python3 tools/switch_overrides.py` checks both console override directories.

## port/linux/src/msvc_crt.c

Uses GCC AArch64 register instructions for the Switch 2 floating-point control
word. This can be proposed upstream for GCC AArch64 builds.

## port/linux/src/sdl_platform.c

Omits the POSIX signal watchdog on Switch 2, whose Newlib signal API lacks
the required sigaction fields, and skips OpenGL function loading for the
Drako3D renderer. This can be proposed upstream for the port.

## port/linux/src/d3d8_resources.c

Uses a 32-bit format argument after the LP64 source rewrite. This can be
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
