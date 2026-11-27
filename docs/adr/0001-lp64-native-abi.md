# 0001. Use native LP64 for the game

## Context

The ILP32 guest preserves Xbox layouts but needs executable code, stacks and
data below 4 GiB. `port/switch/host/host_mman.c` describes Horizon 22.5's
high StackRegion and the use of process-code mappings for low addresses. It
also records that IPC rejected a code-memory stack with `0xd401`. Those
observations are from Warthog for Switch, not Switch 2 measurements.
The process-memory calls `0x73`–`0x75`, `0x77` and `0x78` are unavailable
under kaiHEN; calling an unhinted call can terminate the process.

libounce's JIT can select code memory or libkaihen's RO JIT according to
available capabilities. Neither establishes that an ILP32 guest's complete
low-address executable and IPC-compatible writable memory can be placed.
The isolated probe records the actual hints, regions and JIT addresses.

## Decision

Use native LP64, `HALO_64BIT`, and the upstream `lp64_rewrite.py` source
conversion. Link the shared Deko3D renderer in process against Drako3D;
do not use cross-ABI guest trampolines. This selects one production ABI,
without deciding the separate SDL split.

`lp64_build.py` rewrites Xbox ABI `long` to 32 bits. `xbox_address.h`
stores Xbox-layout pointers as 32-bit `XPTR` addresses and translates them
relative to a host base. The Linux `xbox_memory.c` and `xbox_heap.c` show
the upstream reservation and heap strategy. A Switch 2 adapter must supply
the memory backing and preserve those layouts; the desktop implementation
is not evidence that the Switch 2 game already runs.

The proposed StackRegion slice covers Xbox addresses `[0x40000000,
0x90000000)` by subtracting `0x40000000` from its host address. The probe
tests finding and reserving a 1.25 GiB slice and mapping one page, not the
full game's memory requirements.

## Consequences and evidence

The game needs its LP64 source conversion, address-space adapter and direct
renderer integration. The main program currently does not contain them.
Runtime executable guest loading and privileged process-memory mappings are
not needed by the selected model.

**Verified against upstream**: the source-level Xbox address translation,
LP64 rewrite and original Switch mapping constraints above were inspected.
**Compiled**: applies only to artifacts actually built with the pinned
toolchain, not to the future LP64 game. **Tested on host**: applies only to
host tests that were run. **Tested on hardware**: not claimed; an
`abi_probe.log` from a real Switch 2, with its build identifier and launch
context, is needed to establish its actual region, mapping, JIT, TLS and
thread results. A successful page probe alone does not establish gameplay.
