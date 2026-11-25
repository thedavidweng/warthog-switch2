# Release checklist

Before a public release, run the complete host test suite, the override check,
and Python compilation. Build Debug and `--release` in the pinned
`ounce-devkit` image. Package each with
`python3 tools/switch_package.py --target switch2`, then run
`python3 tools/switch2_audit.py --package` with the matching symbols archive.
Generate `SHA256SUMS.txt`. Check stored ZIP entries, zero Maxwell `.dksh`
files, zero SDK or game assets, zero personal data, and notices for
GPL-3.0-or-later, Zlib, ISC and MIT, including `nx2_platform` and
`nx2_gameshare`.

The release archive must install cleanly from an XISO and from pre-extracted
`maps/`. On hardware, verify upgrade over existing `save/` and `config.toml`,
the main menu, campaign checkpoints, multiplayer, 4P split-screen, handheld
1080p120, docked 4K60, VRR, dock and undock, hbmenu exit and relaunch, and a
`perf_report.json` capture. Record the build identifier, firmware, applet type,
renderer, UAM2 revision and actual refresh rate. Only then remove the
Pre-release status and cut `v<version>` on `main`.

`.github/workflows/release.yml` builds both flavors. The tag procedure is:

```sh
git tag -a v<version>
git push origin v<version>
```

The workflow publishes the `build-<run_number>` release with
`warthog-switch2-release.zip`, `warthog-switch2-debug.zip`, matching
`*-symbols.zip`, and `SHA256SUMS.txt`.
