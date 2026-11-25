# Architecture decision records

One file per decision that would be expensive to reverse, numbered
`NNNN-short-title.md`: the context, the options considered, the decision, and
its consequences. Evidence that decided it — measurements, hardware probes,
upstream issues — belongs in the record, not in a commit message.

`GLOSSARY.md` at the repository root fixes the vocabulary these records use.
Superseding a record means writing a new one that names the old, never editing
history. `AGENTS.md` describes the process.

## Open decisions

None of the decisions named by the spec remain open.

## Records

- [0001. Use native LP64 for the game](0001-lp64-native-abi.md).
- [0002. Use Drako3D and UAM2 for the renderer](0002-drako3d-uam2-renderer.md).
- [0003. SDL2 host and SDL3 seam](0003-sdl2-host-sdl3-seam.md).
