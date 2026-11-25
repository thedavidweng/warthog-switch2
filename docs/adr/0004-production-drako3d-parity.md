# 0004: Production Drako3D renderer parity

## Context

Warthog for Switch 2 uses the existing Deko3D renderer in
`port/switch/host/host_dk*.c` and `port/switch/guest/*_dk.c`. Drako3D 0.5.0
preserves the Dk API for Ampere, while UAM2 0.1.0 compiles the generated GLSL
to Ampere SM 8.6 DKSH (`DEKO3D=200`). Maintaining a second renderer would
split fixes and make Switch 1 and Switch 2 behaviour diverge.

## Decision

Drako3D is the single production renderer on Switch 2. The shared renderer is
compiled against Deko3D on Warthog for Switch and against Drako3D through the
existing compatibility include directory on Switch 2. UAM2 is the only
production shader compiler. OunceVK remains in `UPSTREAM.json` as a documented
contingency only: it may be evaluated after a reproducible hardware rendering
blocker survives a minimal reproducer and an upstream fix attempt. It is never
compiled, probed, shipped, or used as a second backend for this port.

The verified Ampere rules are:

* Invalidate descriptor caches at command-list start and after every
  `dkImageDescriptorInitialize` or `dkSamplerDescriptorInitialize`.
* After a 2D-engine mip composite or render-to-texture transition, use an
  image and L2 cache invalidation before fragment sampling.
* Clean CPU-cached ranges before the GPU reads them. HUD decode buffers are
  cleaned immediately before `dkCmdBufCopyBufferToImage`; window ranges use
  `armDCacheClean`, while uncached upload rings are retired by the frame
  fence.
* A command, upload, descriptor or image ring slot is reusable only after its
  fence serial retires. Resize and teardown wait for the queue before
  destroying swapchain images or backing memory.
* Switch 2 performance reports include `upload_bytes`, `upload_rollovers`,
  `fence_waits` and `fence_wait_us`, alongside the existing frame and shader
  metrics.

## Consequences

Renderer fixes remain in one shared implementation and retain
`ninja switch` compatibility. Switch 2 adds only narrow Ampere cache and
memory ordering rules under `__SWITCH2__`. The host parity checks can validate
the fence policy and cache-invalidation decisions without linking the console
GPU libraries. A real console is still required to establish
**Tested on hardware** status for rendering and lifecycle behaviour.
