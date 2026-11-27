# 0003: SDL2 host and SDL3 seam

## Context

Warthog already translates between its SDL2 host and the SDL3 interface used
by the engine. The existing event bridge uses SDL3 headers without linking
the SDL3 library. Switch 2 needs controller and audio services as well as
platform-specific display and input handling.

## Options

- Keep the SDL2 host and the existing SDL3 engine seam.
- Replace the host and bridge with native SDL3.

## Decision

Keep SDL2 for the host, including audio and game controller initialization,
and retain the SDL3 engine seam. SDL video stays disabled so Drako3D owns
`nwindowGetDefault()`. libounce supplies platform services, including window,
display, operation mode and Nmouse; the attributed MIT `nx2_platform`
helpers provide platform adaptations and lifecycle handling.

Native SDL3 would require replacing a working boundary without demonstrated
benefit. This is the single production architecture.

## Consequences and evidence

The existing `port/switch/host/host_sdl2.c` and `host_sdl3_events.c` establish
the bridge. The SDL2 archive references video initialization even when
video is not requested. Wrapping initialization and shutdown lets section
garbage collection discard the EGL implementation; debug information for
discarded archive members can still appear in the link map. The probe is
compiled and its map can be inspected for graphics libraries. Input, audio
and shutdown have not been tested on hardware.
