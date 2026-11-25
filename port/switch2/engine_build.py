"""LP64 engine source preparation for the Switch 2 build."""

import hashlib
import io
import shutil
import tarfile
import urllib.request
from pathlib import Path

from tools.embed_assets import hud_asset_inputs
from tools.linux_build import EXPAT_SOURCES, ZLIB_SOURCES, ZLIB_DEFINES, updater_defines
from tools.version import VERSION_SOURCES
from tools.server_build import SDL_TARBALL_SHA256, SDL_TARBALL_URL, SDL_VERSION


def fetch_sdl_headers(build):
    """Fetch the server's pinned SDL headers for the headless platform."""
    destination = build / "third_party/SDL3"
    if (destination / "include/SDL3/SDL.h").is_file() and (destination / "LICENSE.txt").is_file():
        return destination / "include"
    with urllib.request.urlopen(SDL_TARBALL_URL) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SDL_TARBALL_SHA256:
        raise ValueError(f"SDL archive SHA-256 {digest} does not match {SDL_TARBALL_SHA256}")
    prefix = f"SDL3-{SDL_VERSION}/"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            relative = Path(member.name[len(prefix):])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Invalid SDL archive path: {member.name}")
            if relative != Path("LICENSE.txt") and relative.parts[:1] != ("include",):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    if not (destination / "include/SDL3/SDL.h").is_file() or not (destination / "LICENSE.txt").is_file():
        raise ValueError("SDL archive is missing its headers or license")
    return destination / "include"


def engine_objects(n, port, build, code_flags, includes):
    game = port.game
    config = port.load_port_config()
    rewritten = build / "lp64"
    override = port.root / "overrides"
    roots = ("source", "port/linux/game", "port/linux/src", "port/linux/include",
             "port/include", "port/third_party/kcp", "port/third_party/tomlc17",
             "server/src")
    n.rule("switch2_lp64", command="$python tools/switch2_lp64_rewrite.py --output $out $in",
           description="SWITCH2 LP64 $in", restat=True)
    outputs = []
    for root in roots:
        for source in sorted((game / root).rglob("*")):
            if not source.is_file() or source.suffix.lower() not in (".c", ".h", ".inl", ".inc"):
                continue
            if source.name.startswith("posix_"):
                continue
            relative = source.relative_to(game)
            selected = override / relative
            if not selected.is_file():
                shared = port.root.parent / "switch/overrides" / relative
                selected = shared if shared.is_file() else source
            output = rewritten / relative
            n.build(output, "switch2_lp64", selected,
                    implicit=["tools/switch2_lp64_rewrite.py", game / "tools/lp64_rewrite.py"])
            outputs.append(output)
    stamp = build / "lp64.stamp"
    n.build(stamp, "phony", outputs)

    semantics = build / "halo_msvc_semantics.h"
    xdk = game / "port/include/xdk"
    n.rule("switch2_msvc_semantics",
           command="$python chupathingyce/tools/linux_msvc_semantics.py --output $out $scan",
           description="SWITCH2 MSVC SEMANTICS $out", restat=True)
    n.build(semantics, "switch2_msvc_semantics",
            implicit=[game / "tools/linux_msvc_semantics.py", *port.game_headers(), *sorted(xdk.glob("*.h"))],
            variables={"scan": f"--tags {game / 'source'}"})
    platform_semantics = build / "platform_msvc_semantics.h"
    n.build(platform_semantics, "switch2_msvc_semantics",
            implicit=[game / "tools/linux_msvc_semantics.py", *sorted(xdk.glob("*.h"))],
            variables={"scan": f"--tags {xdk}"})
    assets = build / "generated/hud_hires_assets.c"
    n.rule("switch2_embed_assets",
           command="$python chupathingyce/tools/embed_assets.py $out",
           description="SWITCH2 EMBED $out")
    n.build(assets, "switch2_embed_assets",
            implicit=[game / "tools/embed_assets.py", *(game / path for path in hud_asset_inputs())])
    n.build("switch2-platform-generated", "phony", [platform_semantics, assets])

    flags = [
        code_flags, includes, "-std=gnu89", "-D__STRICT_ANSI__", "-DHALO_64BIT",
        "-DHALO_CUSTOM_EDITION", "-DHALO_MAP_LIST", "-D_FORTIFY_SOURCE=0",
        "-DHALO_SWITCH_CONSOLE", "-DHALO_DELTA_PLATFORM=_delta_platform_switch",
        "-fsigned-char", "-fms-extensions", "-fshort-wchar", "-fcommon",
        "-fno-strict-aliasing", "-fwrapv", "-fno-delete-null-pointer-checks",
        "-fno-omit-frame-pointer", "-ffp-contract=off",
        *(f"-fno-builtin-{fn}" for fn in ("strnlen", "wcslen", "wcsnlen", "wcschr",
          "wcsrchr", "wcscmp", "wcsncmp", "wcscpy", "wcsncpy", "wcscat", "wcsncat",
          "wmemchr", "wmemcmp", "wmemcpy", "wmemmove", "wmemset")),
        "-Wno-incompatible-pointer-types", "-Wno-attributes", "-Wno-multichar",
        "-Wno-return-type", "-Wno-implicit-int",
        "-Wno-unused", "-Wno-parentheses", "-Wno-switch",
        "-Wno-char-subscripts", "-Wno-pointer-sign", "-Wno-missing-braces",
        "-Wno-unknown-pragmas", "-Wno-comment", "-Wno-address", "-Wno-sequence-point",
        "-Wno-maybe-uninitialized", "-Wno-format-truncation", "-Wno-stringop-overflow",
        "-Wno-array-bounds",
        *(f"-Werror={warning}" for warning in ("int-to-pointer-cast", "pointer-to-int-cast",
           "int-conversion", "implicit-function-declaration", "format")),
        f"-include {rewritten / 'port/linux/include/halo_linux_prefix.h'}",
        f"-include {semantics}",
        *(f"-D{define}" for define in config["game"]["defines"]),
        f"-I{rewritten / 'port/linux/include'}", f"-iquote {rewritten / 'port/linux/game'}",
        *(f'-I"{rewritten / directory}"' for directory in config["game"]["include_dirs"]),
        *(f'-idirafter "{game / directory}"' for directory in config["game"]["include_dirs"]),
        f"-idirafter {rewritten / 'port/include/xdk'}",
    ]
    excluded = set(config["lp64"]["exclude"])
    sources = [*port.game_sources(config), *sorted((game / "port/linux/game").glob("*.c"))]
    objects = []
    for source in sources:
        relative = source.relative_to(game)
        if relative.as_posix() in excluded:
            continue
        obj = build / "engine" / relative.with_suffix(".o")
        extra = " -Dmain=halo_main" if relative.as_posix() == "source/shell/shell_xbox.c" else ""
        n.build(obj, "switch2_cc", rewritten / relative, implicit=[semantics],
                order_only=[stamp], variables={"cflags": " ".join(flags) + extra})
        objects.append(obj)
    overlay = port.root.parent / "switch/overrides/port/linux/game/overlay_commands.c"
    overlay_rewritten = rewritten / "switch_overlay_commands.c"
    n.build(overlay_rewritten, "switch2_lp64", overlay,
            implicit=["tools/switch2_lp64_rewrite.py", game / "tools/lp64_rewrite.py"])
    overlay_obj = build / "engine/switch_overlay_commands.o"
    n.build(overlay_obj, "switch2_cc", overlay_rewritten, implicit=[semantics],
            order_only=[stamp], variables={"cflags": " ".join(flags)})
    objects.append(overlay_obj)
    return objects


def platform_objects(n, port, build, code_flags, includes, release):
    game = port.game
    rewritten = build / "lp64"
    third = game / "port/third_party"
    src = game / "port/linux/src"
    sdl = build / "third_party/SDL3/include"
    base = f"{code_flags} {includes} -std=gnu11 -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L -D_XOPEN_SOURCE=700"
    abi = (" -DHALO_LINUX_PLATFORM_LAYER -DHALO_64BIT -DHALO_SWITCH_CONSOLE"
           " -DHALO_CUSTOM_EDITION -DHALO_MAP_LIST -DHALO_MCC=0"
           " -DHALO_DELTA_PLATFORM=_delta_platform_switch -D_FORTIFY_SOURCE=0"
           " -fsigned-char -fms-extensions -fshort-wchar -fcommon -fno-strict-aliasing"
           " -fwrapv -fno-delete-null-pointer-checks -fno-omit-frame-pointer -ffp-contract=off")
    warnings = " ".join(f"-Werror={w}" for w in ("incompatible-pointer-types", "int-to-pointer-cast",
                        "pointer-to-int-cast", "int-conversion", "implicit-function-declaration", "format"))
    platform = " ".join([base, abi, warnings, "-Wno-error=format-truncation",
        f"-include {rewritten / 'port/linux/include/halo_linux_prefix.h'}",
        f"-include {build / 'platform_msvc_semantics.h'}",
        f"-I{rewritten / 'port/linux/src'}", f"-I{rewritten / 'port/linux/include'}",
        *(f"-I{rewritten / 'port/third_party' / name}" for name in ("tomlc17", "kcp")),
        *(f"-I{third / name}" for name in ("expat", "qrcodegen", "monocypher", "zlib")),
        f"-I{rewritten / 'source'}", f"-I{rewritten / 'source/cseries'}",
        f"-I{sdl}", f"-idirafter {rewritten / 'port/include/xdk'}"])
    native = f"{base} -I{src} -I{sdl}"
    tls = (f"-I{third / 'mbedtls/include'} -I{third / 'mbedtls/library'} -D__unix__=1"
           " -DMBEDTLS_NO_PLATFORM_ENTROPY -DMBEDTLS_ENTROPY_HARDWARE_ALT -DMBEDTLS_PLATFORM_MS_TIME_ALT")
    upnp = (f"-I{third / 'miniupnpc/include'} -I{third / 'miniupnpc/src'} -DMINIUPNP_STATICLIB"
            " -Dif_nametoindex=switch_upnp_if_nametoindex -Dif_indextoname=switch_upnp_if_indextoname"
            f" -include {port.root / 'host/switch2_upnp_names.h'}")
    objects = []

    def add(source, flags, name):
        obj = build / "platform" / name.with_suffix(".o")
        n.build(obj, "switch2_cc", source, implicit=[build / "platform_msvc_semantics.h"],
                order_only=[build / "lp64.stamp"], variables={"cflags": flags})
        objects.append(obj)

    excluded = {"updater.c", "launcher.c", "voice.c", "memory_watch.c", "sdl_platform.c", "xinput_sdl.c"}
    posix = {"posix_files.c", "posix_threads.c", "posix_time.c", "posix_browser.c", "posix_upnp.c", "posix_ui_font.c"}
    for source in sorted(src.glob("*.c")):
        name = source.name
        if name in excluded or (name.startswith("posix_") and name not in posix):
            continue
        if name in posix:
            extra = tls if name == "posix_browser.c" else upnp if name == "posix_upnp.c" else \
                    f"-I{third / 'stb'}" if name == "posix_ui_font.c" else ""
            add(source, f"{extra} {native}", source.relative_to(game))
        else:
            extra = updater_defines(release) if name in VERSION_SOURCES else \
                    f"-idirafter {src}" if name == "text_hires.c" else ""
            add(rewritten / source.relative_to(game), f"{platform} {extra}", source.relative_to(game))
    add(build / "generated/hud_hires_assets.c", platform, Path("generated/hud_hires_assets.c"))
    bridge = port.root / "host/switch2_headless_platform.c"
    bridge_rewritten = build / "lp64/switch2_headless_platform.c"
    n.build(bridge_rewritten, "switch2_lp64", bridge,
            implicit=["tools/switch2_lp64_rewrite.py", game / "tools/lp64_rewrite.py"])
    add(bridge_rewritten, platform, Path("bridge/switch2_headless_platform.c"))
    for name, extra in (("switch2_tls.c", tls), ("switch2_net.c", ""), ("switch2_sdl_headless.c", ""),
                        ("switch2_posix_compat.c", "")):
        add(port.root / "host" / name, f"{extra} {native}", Path("bridge") / name)
    for name in ("tomlc17/tomlc17.c", "kcp/ikcp.c"):
        add(rewritten / "port/third_party" / name, base + abi, Path("third_party") / name)
    for name in EXPAT_SOURCES:
        add(third / "expat" / name, f"{native} -I{third / 'expat'}", Path("third_party/expat") / name)
    for name in ("qrcodegen/qrcodegen.c", "monocypher/monocypher.c", "monocypher/monocypher-ed25519.c"):
        add(third / name, native, Path("third_party") / name)
    for name in ZLIB_SOURCES:
        add(third / "zlib" / name, f"{native} {' '.join(ZLIB_DEFINES)}", Path("third_party/zlib") / name)
    for source in sorted((third / "musl-math/src").glob("*.c")):
        add(source, f"{base} {abi} -DEPS=DBL_EPSILON -I{third / 'musl-math/include'} -include {third / 'musl-math/include/libm.h'}",
            Path("third_party/musl-math/src") / source.name)
    for source in sorted((third / "mbedtls/library").glob("*.c")):
        add(source, f"{tls} {native}", Path("third_party/mbedtls/library") / source.name)
    for source in sorted((third / "miniupnpc/src").glob("*.c")):
        add(source, f"{upnp} {native}", Path("third_party/miniupnpc/src") / source.name)
    return objects
