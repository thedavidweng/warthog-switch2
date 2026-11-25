# 0002: Drako3D and UAM2 for the renderer

## Context

Warthog for Switch has a Deko3D renderer and generates GLSL from NV2A
shaders. Switch 2 needs Ampere DKSH; Maxwell DKSH cannot be reused. The
dependency revisions and licences are recorded in `UPSTREAM.json`.

## Decision

Use Drako3D 0.5.0 with the shared Deko3D renderer and compile generated GLSL
with UAM2's `libuam2rt` and `uam2rt_compile_glsl`. The compatibility headers
forward the existing API to Drako3D. UAM2's standalone Mesa GLSL to NIR to
NAK path builds without GPU drivers; its runtime exports four entry points.
UAM2 is Zlib licensed and its Mesa components are MIT licensed.
The patched GLSL entry point serializes compilation with a mutex; this does
not establish throughput or safety for other compiler entry points, or for
calling `uam2rt_exit` while workers are active.

VI2 swapchain images use `DkImageFlags_UsageRender`,
`DkImageFlags_UsagePresent` and `DkImageFlags_Usage2DEngine`, without
hardware compression. Invalidate descriptor caches with
`dkCmdBufBarrier(cmdbuf, DkBarrier_None, DkInvalidateFlags_Descriptors)` at
command-list start and when descriptor ring entries are reused. Prefix the
shader cache namespace with `ampere-<uam2-12hex>` and include the shader
ABI, generator revision and compile configuration in the cache key.

The host UAM2 CLI compiled the representative vertex and fragment shaders
in `port/switch2/probe/` to files with DKSH magic. This checks neither the
entire game shader corpus nor rendering on hardware. Runtime compilation,
cache coherency, presentation and teardown still require Switch 2 hardware
evidence. Measure compiler thread safety, allocation, timing and binary size
on Switch 2 before choosing a worker count or allocator; measurements from
the original Switch compiler do not establish these properties for UAM2.

## Alternatives

* glslang to SPIR-V followed by UAM2 adds another compiler and its binary
  size, BSD-3-Clause licence and other dependency notices, version pin and
  maintenance surface. It also introduces another translation path to
  compare with the host CLI. Its actual size
  and concurrency characteristics have not been measured here.
* The binary-only `mesa-26.3.1-switch2-horizon-sdk.zip` used by dolphin-nx
  has no identified public source repository. It cannot be reproduced or
  audited against a source revision, so it is rejected; the licence and
  provenance of all its included components cannot be verified from that
  archive alone. Its size and thread safety have not been established for
  this application.
* OunceVK is a contingency, not a second production renderer. Evaluate it
  only after a reproducible Switch 2 hardware test demonstrates either a
  required rendering operation cannot be implemented correctly with Drako3D
  or a GPU fault persists after a minimal reproducer and an upstream fix
  attempt. Record the test, hardware and firmware, shader, failure and
  attempted fix before reopening this decision. A missing optimization or
  an unmeasured performance concern is not a blocker.

## Consequences

The shared renderer remains the source of truth. UAM2 is needed at runtime
for generated shaders and contributes to the application size. No hardware
rendering or lifecycle claim follows from successful host compilation.
