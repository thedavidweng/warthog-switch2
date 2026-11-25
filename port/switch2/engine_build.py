"""LP64 engine source preparation for the Switch 2 build."""

from pathlib import Path


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
    return objects
