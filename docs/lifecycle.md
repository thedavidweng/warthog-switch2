# Switch 2 lifecycle

| Capability | Status | Evidence and remaining work |
| --- | --- | --- |
| Title-takeover launch | Implemented | The startup guard accepts an unrestricted application with sufficient heap. A launch under kaiHEN still needs console verification. |
| Low-memory / applet guard | Tested on host | The launch decision is exercised with restricted and unrestricted modes and values around the heap threshold. Console output and the actual heap budget still need console verification. |
| Runtime dock/undock & TV mode transitions | Implemented | Display dimensions are polled, resize events are queued and the swapchain is recreated when either dimension changes. Docking and TV changes still need console verification. |
| Exit to hbmenu & Normal clock restore | Implemented | Exit requests enter the SDL event queue; cleanup stops the renderer and SDL, releases the window and restores the Normal clock. This still needs console verification. |
| HOME suspend/resume under kaiHEN | Not yet supported | Suspend and resume behavior has not been established on hardware. |

No capability above has reached Tested on hardware. A console run must record
the build identifier, firmware, launch context, renderer, shader compiler
revision and granted refresh rate.
