# Campaign status

The campaign validation and checkpoint paths are **Tested on host** by the
Ticket 13 host test suite. The console result remains **Tested on hardware**
pending human verification with the matching build identifier.

| Mission | Scenario | Status |
|---|---|---|
| a10 | Pillar of Autumn | Implemented; Tested on host |
| a30 | Halo | Implemented; Tested on host |
| a50 | Truth and Reconciliation | Implemented; Tested on host |
| b30 | The Silent Cartographer | Implemented; Tested on host |
| b40 | Assault on the Control Room | Implemented; Tested on host |
| c10 | 343 Guilty Spark | Implemented; Tested on host |
| c20 | The Library | Implemented; Tested on host |
| c40 | Two Betrayals | Implemented; Tested on host |
| d20 | Keyes | Implemented; Tested on host |
| d40 | The Maw | Implemented; Tested on host |

Cinematics and campaign audio remain part of the engine's scenario and cache
loading path. The headless runner loads and unloads each present scenario twice
and reports corrupt or truncated map headers with the affected path. The
checkpoint and profile save paths use a flushed, synchronised temporary file
and rename; an interrupted temporary file is removed before reading. These
behaviours are **Tested on host**. Hardware verification is **Not yet
supported** until a human runs the real-hardware workflow.
