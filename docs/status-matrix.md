# Status matrix

This is the authoritative release status for the Switch 2 port. `Compiled`
means the build links without console behaviour evidence. Status words
come from `GLOSSARY.md`. A host result does not count as console verification;
the rows that need interactive play remain below `Tested on hardware`.

| Area | Status | Evidence | Remaining limitation |
|---|---|---|---|
| Installation and archive extraction | Tested on host | `tests/test_switch2_release.py`, `tools/switch_package.py`, `tools/switch2_audit.py` | Clean installation from an XISO still needs a console run. |
| Self-Update | Tested on host | `tests/test_switch2_release.py` updater tests | Upgrade preservation on a real SD card remains to be checked. |
| Native LP64 engine | Tested on host | `docs/adr/0001-lp64-native-abi.md`, `tests/test_switch2_abi_probe.py` | The ABI probe and runtime memory behaviour need console evidence. |
| Drako3D renderer and parity | Tested on host | `docs/adr/0002-drako3d-uam2-renderer.md`, `docs/adr/0004-production-drako3d-parity.md`, `tests/test_switch2_drako3d_parity.py` | Interactive console rendering is pending. |
| Persistent Ampere shader cache | Tested on host | `tests/test_switch2_shader_cache.py`, `tools/dk_shader_check.py` | First boot, recovery and cache performance need console evidence. |
| Campaign and saves | Tested on host | `docs/campaign-status.md`, `tests/test_switch2_campaign.py`, `tests/test_switch2_gamedata.py` | Campaign play, checkpoints and save migration need console evidence. |
| Controllers and gyro | Tested on host | `tests/test_switch2_controllers.py` | Physical controller combinations and rumble need console evidence. |
| Text, `swkbd`, KBM keyboard and mouse | Tested on host | `tests/test_switch2_text_and_nmouse.py` | HID service availability varies by host title and needs console testing. |
| Joy-Con 2 `Nmouse` | Tested on host | `tests/test_switch2_text_and_nmouse.py` | Attachment and surface behaviour need console evidence. |
| Split-Screen 1–4P | Tested on host | `tests/test_switch2_splitscreen.py`, `tests/test_switch2_gameplay.py` | Interactive gameplay and four-player input need console evidence. |
| Display, 120 Hz, VRR and 4K60 | Tested on host | `tests/test_switch2_display_and_pacing.py` | Handheld, docked, VRR and undock transitions need console evidence. |
| Lifecycle and clocks | Tested on host | `docs/lifecycle.md`, `tests/test_switch2_lifecycle.py` | Suspend, exit and relaunch on hbmenu need console evidence. |
| Networking, HTTPS and map download | Tested on host | `docs/networking.md`, `tests/test_switch2_networking.py` | A real server list and interrupted download need console testing. |
| Custom Edition maps | Tested on host | `tests/test_switch2_custom_edition.py` | Hardware loading of `maps_ce/` remains to be checked. |
| MCC maps | Not yet supported | `docs/mcc-investigation.md` | Version 13 maps are not accepted. |
| GameShare | Tested on host | `docs/gameshare.md`, `tests/test_switch2_gameshare.py` | Two-console matchmaking and streaming need console evidence. |
| Performance telemetry | Implemented | `tests/test_switch2_perf.py`, `tools/switch_profile.py` | FPS and frame-time numbers are withheld until `perf_report.json` is captured on hardware. |
| Original Switch compatibility | Verified against upstream | `tests/test_repo_docs.py`, `tools/switch_overrides.py`, `ninja switch` configure | A full original Switch build remains a separate toolchain check. |
