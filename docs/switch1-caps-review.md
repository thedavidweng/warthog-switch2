# Switch 1 caps review for Switch 2

This audit keeps the original Switch menu and configuration unchanged. The
Switch 2 target selects its own menu target and `port_config.c` override.

| Inherited item | Switch 1 behavior | Switch 2 decision |
| --- | --- | --- |
| Handheld output | 1280x720 | 1920x1080 output and 1080p internal default |
| Docked output | 1920x1080 | VI2 output may be 1920x1080, 2560x1440, or 3840x2160 |
| Refresh | Fixed console pacing | Granted refresh is read from VI2; 120 Hz is requested only through 1440p |
| Simulation | 30 Hz game tick | Kept authoritative at `TICKS_PER_SECOND == 30` |
| Interpolation | Native Smooth Motion option | `display.interpolation` remains native ChupathingyCE interpolation |
| CPU presets | Tegra X1 1020/1785 MHz choices | Stock `ApmCpuBoostMode_Normal` is default; optional `FastLoad` is a loading aid |
| `big_sprite_limit` | 8 | Keep 8 until a Switch 2 measurement justifies raising it; this avoids an unmeasured GPU cost |
| Hosted players | 48 in the current console port | Keep the existing host limit; network/session capacity is independent of output resolution |
| Maxwell compromises | Deko3D compression and Maxwell shader assumptions | Drako3D/Ampere path uses uncompressed VI2 swapchain images and Ampere shader cache keys |

The clock policy is explicit: normal play requires no overclock. `FastLoad`
can improve load-heavy work while lowering GPU frequency, so it is not the
default. Every exit path restores `ApmCpuBoostMode_Normal`.

The 4K mode is 60 Hz only. The display policy clamps any request whose output
is above 2560x1440 to 60 Hz, and the granted refresh is obtained from
`nwindowGetPresentInterval` after the VRR request. A rejected 120 Hz request
therefore falls back to 60 Hz.
