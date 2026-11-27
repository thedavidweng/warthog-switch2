# MCC investigation

Ticket #23 reviewed the MCC path in the pinned `chupathingyce` submodule. The
result is a documented boundary: Switch 2 builds define `HALO_MCC=0`, so MCC
maps are **Not yet supported** on Switch 2. The presence of an MCC `.map` file
must produce a diagnostic rather than accidentally entering the Custom Edition
loader.

## What upstream implements

The MCC implementation is in `chupathingyce/port/linux/game/mcc_cache.c` and
the format reader is in `chupathingyce/port/linux/game/mcc_cache_format.c`.
The reader identifies a Halo 1 MCC version-13 header, validates the file
length and tag-data range, checks tag tables and BSP ranges, and converts the
runtime tags, geometry, audio and bitmaps. `mcc_cache.c` then selects package
resources, validates their checksums, prepares scripts, and exposes the
converted cache to the game.

`chupathingyce/port/linux/src/mcc_memory.c` reserves one 64 MiB tag window at
the map's linked address. In the 64-bit path the address is translated through
`xbox_pointer`, and `xbox_heap_reserve_window` makes the heap step around the
window. The current MCC Tool base is `0x50000000`. The original Switch host
counterpart, `port/switch/host/host_mcc_memory.c`, accepts a 64 MiB aligned
window between `0x42000000` and `0x70000000`, using a fixed non-replacing map.

MCC loading is more than reading a cache header. `mcc_cache.c` reads package
metadata and external bitmap/sound resources, applies `mcc_resources.c`
selection and checksums, and runs tag, geometry, audio, bitmap, script and
campaign conversion. `mcc_checkpoint.c` supplies MCC campaign checkpoint
lifetime and validation. The package path and Workshop identity are handled by
the MCC package and identity modules; this is separate from the Custom Edition
`maps_ce/` search path.

The upstream cache reader also has format-specific compressed data handling.
The MCC resource and package modules account for MCC's zstd/LZ4-compressed
payloads and external resources. This is not the same as Chimpira/Chimera
compressed Custom Edition maps, which are expanded by
`chupathingyce/port/linux/src/map_compressed_files.c`.

## Switch 2 conclusion

Switch 2 deliberately compiles platform objects with `-DHALO_MCC=0` in
`port/switch2/engine_build.py`. `port/switch2/host/switch2_headless_platform.c`
also documents the MCC hooks as excluded. The Switch 2 address-space design
does reserve the LP64 Xbox window and supports the CE cache at
`0x40440000`, but that does not provide the independent 64 MiB MCC tag window,
package resource resolver, conversion passes, Workshop bridge, or MCC network
layout.

Therefore MCC cache version 13, MCC-only resource sets, and compressed MCC
packages are **Not yet supported** on Switch 2. They are rejected by the
Switch 2 Custom Edition preflight with a message naming version 13 and the
missing MCC loader. No end-to-end tested data acquisition, package extraction,
resource verification and console load path exists for this port, so claiming
MCC compatibility would be unverified.

Owning Halo PC or Halo: The Master Chief Collection alone is not sufficient.
The game still needs the retail Xbox Halo: Combat Evolved maps and `ui.map`
from the user's own Xbox disc data in `maps/`; PC Custom Edition maps are
optional additions in `maps_ce/`, and MCC is not a substitute for the retail
Xbox base data. The repository contains no game data.
