# Architecture decision records

One file per decision that would be expensive to reverse, numbered
`NNNN-short-title.md`: the context, the options considered, the decision, and
its consequences. Evidence that decided it — measurements, hardware probes,
upstream issues — belongs in the record, not in a commit message.

`GLOSSARY.md` at the repository root fixes the vocabulary these records use.
Superseding a record means writing a new one that names the old, never editing
history. `AGENTS.md` describes the process.

## Open decisions

No record has been written yet. These decisions are named by the spec and must
be recorded here before the code commits to an answer:

- **ABI model** — Warthog's existing ILP32 guest inside an LP64 host, or the
  game built natively as LP64. Decided by the capability probe work.
- **Renderer** — Drako3D with Ampere DKSH compiled by UAM2, keeping OunceVK as
  a documented contingency only.
- **SDL split** — the existing SDL2 host with an SDL3 guest, or migration to
  native SDL3.

## Records

None yet.
