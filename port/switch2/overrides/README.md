# Switch 2 overrides

Whole-file fixes to the engine belong here until upstream takes them. Each
override must be listed below with its purpose and upstream destination.
`python3 tools/switch_overrides.py` checks both console override directories.

## port/linux/src/xbox_heap.c

Commits the LP64 Xbox heap in 1 MiB increments on Switch 2. This
platform-specific change can be proposed upstream with the Switch 2 memory
adapter.

## port/linux/src/xbox_memory.c

Reserves the Switch 2 address window and commits contiguous and Custom Edition
tag-cache pages on demand. This platform-specific change can be proposed
upstream with the Switch 2 memory adapter.
