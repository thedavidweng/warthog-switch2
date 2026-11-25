# GameShare local multiplayer

GameShare is the Switch 2 `gameshare`/`stpl` local session. Warthog hosts the
session and maps the connected console to Halo local player 1. The host keeps
player 0 and its local controllers independent.

The feature is available only when kaiHEN launches Warthog as an
`AppletType_Application` title takeover and the host title grants `stpl:u` and
GameShare. In a restricted library, system or overlay applet the feature
refuses to start with a diagnostic. A matchmaking HOME or B cancel rolls back
to the previous game state.

Mirror mode uses the host display for the guest. SeparateViews creates a
second uncompressed Drako3D swapchain on the `"player1"` window and presents
the guest view there. A disconnect waits for the queue to idle, destroys that
swapchain and window, and resumes the normal single-display path. Guest
controller, motion, rumble and audio are forwarded through the native
GameShare service.

Campaign co-op is limited to the upstream two-player local co-op path. More
than two campaign players are refused; ordinary one-to-four-player local
split-screen and network multiplayer keep their existing paths.

The adapter and renderer integration are **Implemented** and **Compiled**;
host state and routing checks are **Tested on host**. Console matchmaking,
guest input, audio and separate-display streaming remain pending **Tested on
hardware** because they require a Switch 2 title takeover, kaiHEN and a
second console.

`nx2_gameshare.{c,h}` retains its MIT licence and provenance from
Cemu-nx and `NaGaa95/dolphin-nx` revision
`7fb685b353e19a9a5848e9bd658945d1f9cd382a`.
