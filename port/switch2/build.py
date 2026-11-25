"""Ninja rules for the Nintendo Switch 2 build (``ninja switch2``): the port's
build.py, which the game's configure.py loads (--console-port port/switch2;
the game's tools/console_build.py).

From this repository's root, with the game in chupathingyce/ (a submodule):

    python3 chupathingyce/configure.py --console-port port/switch2 [--devkitpro DIR]
    ninja switch2

What this graph builds, in build/switch2/ and nowhere else:

- warthog.elf, the program itself, unstripped (-g, .debug_info and .symtab
  kept, and a linker map beside it) so a console's crash can be symbolized;
- warthog.nacp, what hbmenu shows: the title, author and version;
- warthog.nro, the homebrew the card takes, with the icon and the NACP in the
  asset section elf2nro appends.

It is a Switch 2 program, not an original Switch one: libounce is the
platform (libnx.a is an alias of it), the linker script is libounce's
switch.specs and switch.ld, the CPU flags are libounce's switch2_cpu.mk, and
the libraries are Drako3D and the UAM2 runtime. Nothing here reads
/opt/devkitpro/libnx, which is where the original Switch's Deko3D and
portlibs live; tools/switch2_audit.py fails the build's artifacts when it
finds them.

The build is generated when devkitPro and libounce are found, and writes a
comment saying why when they are not, so `ninja switch` on a machine without
the Switch 2 toolchain still configures.

The toolchain itself is pinned: scripts/switch2/build.sh runs configure.py
and ninja inside the image scripts/switch2/Dockerfile builds, whose every pin
is UPSTREAM.json's. Built on a host with the same packages installed, the
same commands work outside it.
"""

import json
import os
from pathlib import Path
from typing import Any, List, Optional

from tools.console_build import ConsolePort
from tools.ninja_syntax import Writer

# What the console shows for this program in hbmenu. Fixed rather than taken
# from the environment: $USER on a build machine is whoever's account ran it,
# which would put a different publisher on every release.
NACP_TITLE = "Warthog"
NACP_AUTHOR = "thedavidweng, ChupathingyCE contributors"

# The libraries a Switch 2 program links. -lounce is libounce: the platform
# layer, the C runtime's console half, and the loader. -ldrako3d is the
# renderer (Drako3D keeps Deko3D's Dk*/dk::* API, so the Switch 1 renderer's
# source compiles against it). -luam2rt is UAM2's on-console half, the Ampere
# shader compiler the renderer calls at run time.
SWITCH2_LIBRARIES = ["drako3d", "uam2rt", "ounce", "m"]

# The CPU and ABI flags, from libounce's switch2_cpu.mk (Cortex-A78C; +crypto
# enables the AES and SHA extension the A78C has). -fPIE and the soft thread
# pointer are what the platform expects; __SWITCH2__ is what libounce's own
# headers check before they will compile.
CPU_FLAGS = "-mcpu=cortex-a78c+crypto -mtp=soft -fPIE"
PLATFORM_DEFINES = "-D__SWITCH__ -D__SWITCH2__"

# Where a program's files live on the card (the release requirements and the
# hardware workflow name it).
CARD_DIR = "sdmc:/switch/warthog"

# This repository's root, for UPSTREAM.json: the pins the build records in the
# program and the version hbmenu shows.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _quote(path: Any) -> str:
    text = str(path).replace(os.sep, "/")
    return f'"{text}"' if " " in text else text


def upstream_record() -> dict:
    """UPSTREAM.json: the one authority for what this build is made of"""
    with open(REPO_ROOT / "UPSTREAM.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def nacp_version(record: dict) -> str:
    """the version hbmenu shows: the pinned upstream release's

    Upstream names its release 0.9.1a, where the trailing letter is the
    build's and not the version's: the console shows 0.9.1. The field is 16
    bytes, and a version a player cannot read is worse than a shorter one.
    """
    version = record["upstream"]["version"].rstrip("abcdefghijklmnopqrstuvwxyz")
    if not version or len(version) >= 16:
        raise SystemExit(f"port/switch2: UPSTREAM.json's version {record['upstream']['version']!r} "
                         f"is not an NACP display version")
    return version


def add_arguments(parser: Any) -> None:
    """the port's own configure.py options"""
    parser.add_argument(
        "--devkitpro",
        metavar="DIR",
        type=Path,
        help="devkitPro's install for `ninja switch2`, with libounce, Drako3D and the UAM2 runtime "
        "(default: DEVKITPRO, or /opt/devkitpro)",
    )


def devkitpro_dir(sln: Any) -> Optional[Path]:
    """devkitPro's install: --devkitpro's alone when it is given, else
    DEVKITPRO's, /opt/devkitpro or ~/devkitpro, whichever is there"""
    explicit = getattr(sln.args, "devkitpro", None)
    candidates = [str(explicit)] if explicit else [os.environ.get("DEVKITPRO"), "/opt/devkitpro",
                                                    str(Path.home() / "devkitpro")]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().is_dir():
            return Path(candidate).expanduser().resolve()
    return None


def configure_inputs(port: ConsolePort) -> List[Path]:
    """Files whose change must re-run configure.py."""
    return [port.path("host"), port.path("README.md"), REPO_ROOT / "UPSTREAM.json"]


def build_header(sln: Any, record: dict) -> str:
    """warthog_build.h: what the log records about the build that wrote it"""
    flavor = "release" if getattr(sln, "port_release", False) else "debug"
    pins = {
        "WARTHOG_SWITCH2_VERSION": record["upstream"]["version"],
        "WARTHOG_SWITCH2_FLAVOR": flavor,
        "WARTHOG_SWITCH2_WARTHOG_SWITCH_COMMIT": record["upstream"]["commit"],
        "WARTHOG_SWITCH2_CHUPATHINGYCE_COMMIT": record["submodules"]["chupathingyce"]["commit"],
        "WARTHOG_SWITCH2_DRAKO3D_COMMIT": record["dependencies"]["drako3d"]["commit"],
        "WARTHOG_SWITCH2_DRAKO3D_VERSION": record["dependencies"]["drako3d"]["release"],
        "WARTHOG_SWITCH2_UAM2_COMMIT": record["dependencies"]["uam2"]["commit"],
        "WARTHOG_SWITCH2_UAM2_VERSION": record["dependencies"]["uam2"]["release"],
    }
    lines = ["/* generated by port/switch2/build.py from UPSTREAM.json: do not edit */",
             "#pragma once", ""]
    lines += [f'#define {name} "{value}"' for name, value in pins.items()]
    lines += ["", f'#define WARTHOG_SWITCH2_CARD_DIR "{CARD_DIR}"', ""]
    return "\n".join(lines)


def generate(n: Writer, sln: Any, port: ConsolePort) -> None:
    PORT_DIR = port.root
    BUILD: Path = sln.build_dir / "switch2"
    HOST_DIR = PORT_DIR / "host"
    ICON = Path.cwd() / "port" / "switch" / "art" / "icon.jpg"

    if not (HOST_DIR / "main.c").is_file():
        n.comment("Switch 2 build: no port/switch2/host/main.c")
        return

    devkitpro = devkitpro_dir(sln)
    if not devkitpro:
        n.comment("Switch 2 build: no devkitPro found (set DEVKITPRO or pass --devkitpro)")
        return
    libounce = devkitpro / "libounce"
    if not (libounce / "lib" / "libounce.a").is_file():
        n.comment(f"Switch 2 build: no libounce under {libounce} "
                  f"(the Switch 2 toolchain: scripts/switch2/build.sh image)")
        return
    compiler = devkitpro / "devkitA64" / "bin" / "aarch64-none-elf-gcc"
    linker = devkitpro / "devkitA64" / "bin" / "aarch64-none-elf-g++"
    if not compiler.is_file() or not linker.is_file():
        n.comment(f"Switch 2 build: no aarch64-none-elf toolchain under {devkitpro / 'devkitA64'}")
        return

    portlibs_switch2 = devkitpro / "portlibs" / "switch2"
    if not (portlibs_switch2 / "lib" / "libuam2rt.a").is_file():
        n.comment(f"Switch 2 build: no libuam2rt.a under {portlibs_switch2} "
                  f"(UAM2's runtime, which scripts/switch2/Dockerfile builds)")
        return
    if not (libounce / "lib" / "libdrako3d.a").is_file():
        n.comment(f"Switch 2 build: no libdrako3d.a under {libounce} "
                  f"(Drako3D, which scripts/switch2/Dockerfile builds)")
        return

    record = upstream_record()
    version = nacp_version(record)
    release = getattr(sln, "port_release", False)

    n.comment("Switch 2 build (ninja switch2); see port/switch2/README.md")
    n.variable("switch2_cc", str(compiler))
    n.variable("switch2_gxx", str(linker))
    n.variable("switch2_specs", str(libounce / "switch.specs"))

    # The include order is libounce's: the Switch 2 portlibs first (UAM2's
    # runtime and kaihen), then the original Switch's (a C-only library may
    # still come from there), then libounce's own headers. The Switch 2
    # headers must come first: switch2/ shadows switch/ where the two differ.
    includes = " ".join([
        f"-I{_quote(portlibs_switch2 / 'include')}",
        f"-I{_quote(devkitpro / 'portlibs' / 'switch' / 'include')}",
        f"-isystem {_quote(libounce / 'include')}",
        f"-I{_quote(HOST_DIR)}",
        f"-I{_quote(BUILD)}",
    ])
    library_paths = " ".join(f"-L{_quote(path)}" for path in
                             (portlibs_switch2 / "lib", devkitpro / "portlibs" / "switch" / "lib",
                              libounce / "lib"))

    # A release build differs from a debug build in optimisation and in the
    # asserts, and in nothing else: both keep .debug_info and .symtab, so a
    # release's crash is symbolized against the symbols published beside it.
    optimization = "-O2 -DNDEBUG" if release else "-O0"
    code_flags = f"{CPU_FLAGS} {PLATFORM_DEFINES} -g {optimization} -fno-omit-frame-pointer"

    # ---------- the build's own header, from UPSTREAM.json

    # Written here rather than by a rule: configure.py reruns when
    # UPSTREAM.json changes (configure_inputs), so the pins reach the program
    # through the same mechanism that reaches the build graph. Only when the
    # content differs, so a rerun that changes nothing does not touch the
    # header and force every object to be compiled again.
    header = BUILD / "warthog_build.h"
    header.parent.mkdir(parents=True, exist_ok=True)
    text = build_header(sln, record)
    if not header.is_file() or header.read_text(encoding="utf-8") != text:
        header.write_text(text, encoding="utf-8")

    # ---------- the program

    n.rule(
        name="switch2_cc",
        # -MMD and -MF are in the rule's command rather than the per-build
        # cflags: $out is only bound in a command, so -MF $out.d there names
        # build/switch2/host/main.c.o.d, where in a build statement's variable
        # it names .d in the repository root.
        command=f"$switch2_cc -c $cflags -o $out $in -MMD -MF $out.d",
        description="SWITCH2 CC $out",
        depfile="$out.d",
        deps="gcc",
    )
    objects = []
    for source in sorted((HOST_DIR).glob("*.c")):
        obj = BUILD / "host" / (source.name + ".o")
        n.build(outputs=obj, rule="switch2_cc", inputs=source,
                implicit=[header, libounce / "include" / "switch.h"],
                variables={"cflags": f"{code_flags} {includes}"})
        objects.append(obj)

    elf = BUILD / "warthog.elf"
    n.rule(
        name="switch2_link",
        # the C++ driver links even though the program is C: UAM2's runtime is
        # C++ (Mesa's NAK is), and its standard library comes with it
        command=(f"$switch2_gxx -specs=$switch2_specs -g {CPU_FLAGS} -o $out $in {library_paths} "
                 + " ".join(f"-l{library}" for library in SWITCH2_LIBRARIES)
                 + " -lstdc++ -Wl,-Map,$out.map"),
        description="SWITCH2 LINK $out",
    )
    n.build(outputs=elf, rule="switch2_link", inputs=objects)

    # ---------- the card's metadata: NACP and icon

    nacp = BUILD / "warthog.nacp"
    n.rule(
        name="switch2_nacp",
        command=f"{devkitpro / 'tools' / 'bin' / 'nacptool'} --create '{NACP_TITLE}' '{NACP_AUTHOR}' {version} $out",
        description="SWITCH2 NACP $out",
    )
    n.build(outputs=nacp, rule="switch2_nacp")

    # The icon does not go in the NACP: elf2nro embeds it as an asset. A
    # 256x256 JPEG, the port's own. Absolute paths throughout, as the Switch 1
    # build does: elf2nro reports success and writes nothing for a relative
    # one, which ninja cannot notice.
    nro = BUILD / "warthog.nro"
    n.rule(
        name="switch2_nro",
        command=(f"{devkitpro / 'tools' / 'bin' / 'elf2nro'} "
                 f"{(Path.cwd() / str(elf)).resolve()} {(Path.cwd() / str(nro)).resolve()}"
                 f" --icon={ICON.resolve()} --nacp={(Path.cwd() / str(nacp)).resolve()}"),
        description="SWITCH2 NRO $out",
    )
    n.build(outputs=nro, rule="switch2_nro", inputs=[elf, nacp, ICON])

    n.build(outputs="switch2", rule="phony", inputs=[nro, elf])
    n.newline()
