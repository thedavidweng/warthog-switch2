# Troubleshooting

Launch Warthog from hbmenu in `Application` or `SystemApplication` title
takeover mode. Album applet mode does not provide enough memory and the
program refuses to continue. Returning to hbmenu joins worker threads and
releases the window, HID and audio resources before relaunch.

If the game reports a missing `ui.map`, copy the complete retail Xbox map set
to `sdmc:/switch/warthog/maps/`, including `ui.map`, `bitmaps.map` and
`sounds.map`. An XISO is unpacked on first launch only after a free-space
check; an interrupted extraction leaves no partial map. Halo Trial maps and
MCC version 13 maps are unsupported. Compatible
`sdmc:/switch/ChupaThingyCE/maps/` data is detected and reused.

The granted refresh interval is read with `nwindowGetPresentInterval`. If the
display handshake does not grant 120 Hz, the application falls back to 60 Hz.
Docked `3840x2160` output is capped at 60 Hz; 4K120 is not supported or
advertised. Smooth Motion is a setting for the pacing path and does not
change that cap.

Some host titles refuse `hidInitializeKeyboard` or `hidInitializeMouse`; the
application continues without the unavailable service. It intentionally does
not query `usb:hs` under kaiHEN's shared SM session. Joy-Con 2 `Nmouse`
requires the controller attachment and a suitable pointing surface. Rumble is
stopped when a controller disconnects.

The first shader run displays `Compiling shaders: N / M`. Interrupted or
corrupt `.dksh` entries are discarded and rebuilt. The cache is under
`sdmc:/switch/warthog/` in the Ampere cache directory reported by the runtime;
clear that directory while the game is stopped to force a clean compile.

For online play, put `cacert.pem` at
`sdmc:/switch/warthog/cacert.pem`. Four BSD sockets are reserved for the
network pool; exhaustion appears as failed server-list or map requests.
Interrupted downloads use `.part` files, which are removed before retry.

Logs are stored in `sdmc:/switch/warthog/logs/`. Fetch and symbolize them with
the matching unstripped ELF:

```sh
python3 tools/switch_logs.py --target switch2 --elf <matching-warthog.elf>
```

CPU exceptions and Drako3D GPU faults are reported separately. Keep the build
identifier, firmware, applet type, renderer and UAM2 revision with a report.
