# Architecture decision records

One file per decision that would be expensive to reverse, numbered
`NNNN-short-title.md`: the context, the options considered, the decision, and
its consequences. Evidence that decided it — measurements, hardware probes,
upstream issues — belongs in the record, not in a commit message.

`GLOSSARY.md` at the repository root fixes the vocabulary these records use.
Superseding a record means writing a new one that names the old, never editing
history. `AGENTS.md` describes the process.

## Open decisions

These decisions are named by the spec and must be recorded before the code
commits to an answer:

- **SDL split** — the existing SDL2 host with an SDL3 guest, or migration to
  native SDL3.

## Records

- [0001. Use native LP64 for the game](0001-lp64-native-abi.md).
- [0002. Use Drako3D and UAM2 for the renderer](0002-drako3d-uam2-renderer.md).
