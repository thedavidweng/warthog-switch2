# Networking

The Switch 2 build uses ChupathingyCE's networking code and the existing Switch
Delta platform identifier. The interoperability targets are ChupathingyCE
v0.9.1a at `2e5eac00e3d6` and Warthog for Switch build-7. Compatibility has
not been established on hardware.

| Mode | Status | Evidence and remaining work |
| --- | --- | --- |
| Server Browser and Direct Connect | Implemented | The browser, socket implementations and certificate bundle are in the build graph; live connections have not been tested. |
| System Link LAN | Implemented | The upstream discovery code is included; multi-device discovery and joining have not been tested on Switch 2. |
| Dedicated server join | Implemented | The upstream client code is included; joining a server has not been tested on Switch 2. |
| Co-op campaign | Implemented | The upstream game code is included; a multi-device campaign has not been tested on Switch 2. |
| Atomic custom map installation | Not yet supported | Upstream stages and validates downloads, but its final file move does not guarantee no replacement under a concurrent writer or persistence after power loss. |

Upstream stages custom map downloads in a quarantine folder and validates the
cache header and other map data before installation. Until the installation
boundary is hardened, do not rely on it to protect existing maps from
concurrent writes or a power failure. Keep independent backups of maps.

The browser requires a trusted certificate bundle and refuses HTTPS when it
cannot load one. At startup, the application installs its HTTPS roots as
`cacert.pem` if the file is absent and leaves an existing bundle in place.

Upstream restricts game-changing console commands in public games by default.
A host can explicitly enable `network.host_cheats`; that setting is advertised
in Online Games.

Homebrew use on online services or local networks carries platform and network
risks, including possible account or device enforcement and exposure to other
participants. Follow the rules of the networks and servers you use. Do not
perform destructive testing against public servers; use systems you control
and have permission to test.
