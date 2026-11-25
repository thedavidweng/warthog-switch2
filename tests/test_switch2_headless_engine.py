"""Checks shared infrastructure for Switch 2 engine overrides."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import switch_overrides


ROOT = Path(__file__).resolve().parents[1]
SDL = ROOT / "build/switch2/third_party/SDL3/include"


class OverrideChecks(unittest.TestCase):
    def test_both_ports_are_checked_against_their_own_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "chupathingyce"
            directories = [root / "port" / port / "overrides" for port in ("switch", "switch2")]
            for directory in [game, *directories]:
                directory.mkdir(parents=True)
            (game / "example.c").write_text("upstream\n")
            for directory in directories:
                (directory / "example.c").write_text("fixed\n")
                (directory / "README.md").write_text("## example.c\n")

            with patch.object(switch_overrides, "ROOT", root), \
                 patch.object(switch_overrides, "GAME", game), \
                 patch.object(switch_overrides, "OVERRIDE_DIRS", directories), \
                 patch("sys.argv", ["switch_overrides.py"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(switch_overrides.main(), 0)
                (directories[1] / "README.md").write_text("")
                self.assertEqual(switch_overrides.main(), 1)
                (directories[1] / "README.md").write_text("## example.c\n")
                (directories[1] / "example.c").write_text("upstream\n")
                self.assertEqual(switch_overrides.main(), 1)


class LP64BuildChecks(unittest.TestCase):
    def test_headless_runner_is_connected(self):
        host = ROOT / "port/switch2/host"
        runner = (host / "headless_engine.c").read_text()
        self.assertTrue((host / "headless_engine_checks.h").is_file())
        for symbol in ("warthog_headless_engine_run", "scenario_tags_load",
                       "physical_memory_allocate", "real_math_initialize",
                       "switch2_mman_shutdown"):
            self.assertIn(symbol, runner)
        self.assertIn("headless_engine.c", (ROOT / "port/switch2/engine_build.py").read_text())
        self.assertIn("warthog_headless_engine_run()", (host / "main.c").read_text())

    def test_rewrite_preserves_xptr_and_converts_long(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.c"
            output = Path(directory) / "output.c"
            source.write_text("long value;\nunsigned long seed;\nXPTR(void) pointer;\n")
            subprocess.run(
                [sys.executable, str(ROOT / "tools/switch2_lp64_rewrite.py"),
                 "--output", str(output), str(source)],
                check=True, capture_output=True,
            )
            text = output.read_text()
            self.assertIn("int value;", text)
            self.assertIn("unsigned int seed;", text)
            self.assertIn("XPTR(void) pointer;", text)
            subprocess.run(
                ["clang", "-x", "c", "-fsyntax-only", "-"],
                input=("#include <stdint.h>\n#define XPTR(type) uint32_t\n"
                       + text + "\n_Static_assert(sizeof(value) == 4, \"value\");\n"
                       "_Static_assert(sizeof(seed) == 4, \"seed\");\n"
                       "_Static_assert(sizeof(pointer) == 4, \"pointer\");\n"),
                check=True, capture_output=True, text=True,
            )

    def test_pointer_conversion_warnings_are_errors(self):
        source = (ROOT / "port/switch2/engine_build.py").read_text()
        self.assertIn('f"-Werror={warning}"', source)
        self.assertIn('f"-Werror={w}"', source)
        for warning in ("int-to-pointer-cast", "pointer-to-int-cast",
                        "int-conversion", "implicit-function-declaration"):
            self.assertIn(f'"{warning}"', source)
            self.assertNotIn(f"-Wno-{warning}", source)
        self.assertNotIn('"-w"', source)


class MemoryMappingTest(unittest.TestCase):
    def test_switch2_reservation_commit_and_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "switch.h").write_text(
                "#include <stddef.h>\n"
                "typedef struct { int unused; } VirtmemReservation;\n"
                "#define R_SUCCEEDED(x) ((x) == 0)\n"
                "void virtmemLock(void); void virtmemUnlock(void);\n"
                "void *virtmemFindStack(size_t, size_t);\n"
                "VirtmemReservation *virtmemAddReservation(void *, size_t);\n"
                "void virtmemRemoveReservation(VirtmemReservation *);\n"
                "int svcMapMemory(void *, void *, size_t);\n"
                "int svcUnmapMemory(void *, void *, size_t);\n"
            )
            (directory / "malloc.h").write_text(
                "#include <stdlib.h>\n"
                "static inline void *memalign(size_t a, size_t n) "
                "{ void *p = 0; return posix_memalign(&p, a, n) ? 0 : p; }\n"
            )
            (directory / "main.c").write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "switch.h"
#include "switch2_mman.h"
static void *region;
static int reservations, mappings;
static VirtmemReservation reservation;
void virtmemLock(void) {}
void virtmemUnlock(void) {}
void *virtmemFindStack(size_t n, size_t alignment) {
    return posix_memalign(&region, alignment, n) ? NULL : region;
}
VirtmemReservation *virtmemAddReservation(void *p, size_t n) {
    assert(p == region && n == SWITCH2_XBOX_WINDOW_SIZE);
    reservations++; return &reservation;
}
void virtmemRemoveReservation(VirtmemReservation *p) {
    assert(p == &reservation); reservations--; free(region);
}
int svcMapMemory(void *dst, void *src, size_t n) {
    (void)dst; (void)src; (void)n; mappings++; return 0;
}
int svcUnmapMemory(void *dst, void *src, size_t n) {
    (void)dst; (void)src; (void)n; mappings--; return 0;
}
int main(void) {
    assert(switch2_mman_init() && reservations == 1);
    char *p = (char *)(uintptr_t)(xbox_address_space_base + SWITCH2_XBOX_WINDOW_LOW);
    assert(mmap(p, 4096, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p);
    assert(switch2_mman_committed_bytes() == 4096 && mappings == 1);
    p[0] = 42;
    assert(mmap(p, 8192, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p);
    assert(p[0] == 0 && switch2_mman_committed_bytes() == 8192 && mappings == 2);
    switch2_mman_shutdown();
    assert(!reservations && !mappings && !switch2_mman_run_count());
    assert(!switch2_mman_committed_bytes() && !xbox_address_space_base);
    return 0;
}
''')
            host = ROOT / "port/switch2/host"
            executable = directory / "mman-test"
            subprocess.run(
                ["clang", "-D__SWITCH2__", "-I", str(directory), "-I", str(host),
                 str(host / "switch2_mman.c"), str(directory / "main.c"),
                 "-pthread", "-o", str(executable)], check=True, capture_output=True,
            )
            subprocess.run([str(executable)], check=True, capture_output=True)


class BasePathTest(unittest.TestCase):
    def test_switch2_base_path_uses_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            sdl = SDL
            if not (sdl / "SDL3/SDL.h").is_file():
                sdl = directory
                (sdl / "SDL3").mkdir()
                (sdl / "SDL3/SDL.h").write_text(
                    "#include <stdbool.h>\n#include <stddef.h>\n#include <stdint.h>\n"
                    "typedef uint64_t Uint64;\ntypedef int64_t SDL_Time;\n"
                    "typedef struct SDL_IOStream SDL_IOStream;\n"
                    "typedef struct SDL_AudioStream SDL_AudioStream;\n"
                    "typedef struct SDL_AudioSpec SDL_AudioSpec;\n"
                    "typedef uint32_t SDL_AudioDeviceID;\ntypedef unsigned SDL_GlobFlags;\n"
                    "typedef void (*SDL_FunctionPointer)(void);\n"
                    "typedef void (*SDL_AudioStreamCallback)(void *, SDL_AudioStream *, int, int);\n"
                    "enum { SDL_PATHTYPE_FILE, SDL_PATHTYPE_DIRECTORY, SDL_PATHTYPE_OTHER };\n"
                    "typedef struct { int type; Uint64 size; SDL_Time create_time, modify_time, access_time; } SDL_PathInfo;\n"
                    "const char *SDL_GetBasePath(void);\n"
                )
                (sdl / "SDL3/SDL_opengl.h").write_text("")
            (directory / "switch.h").write_text(
                "#include <stdint.h>\n"
                "typedef uint32_t Result;\n"
                "#define R_FAILED(result) ((result) != 0)\n"
                "Result fsdevCommitDevice(const char *name);\n"
                "uint64_t armGetSystemTick(void);\n"
                "uint64_t armGetSystemTickFreq(void);\n"
            )
            (directory / "main.c").write_text(
                '#include <stdio.h>\n#include <SDL3/SDL.h>\n'
                'int main(void) { const char *p = SDL_GetBasePath(); '
                'if (!p) return 1; puts(p); return 0; }\n'
            )
            executable = directory / "base-path"
            subprocess.run(
                ["clang", "-D__SWITCH2__", "-ffunction-sections", "-fdata-sections",
                 "-I", str(directory), "-I", str(sdl),
                 str(ROOT / "port/switch2/host/switch2_sdl_headless.c"),
                 str(directory / "main.c"),
                 "-Wl,-dead_strip" if sys.platform == "darwin" else "-Wl,--gc-sections",
                 "-o", str(executable)],
                check=True, capture_output=True,
            )
            for root, expected in (
                (None, "sdmc:/switch/warthog/"),
                ("sdmc:/custom", "sdmc:/custom/"),
                ("sdmc:/custom/", "sdmc:/custom/"),
            ):
                env = os.environ.copy()
                env.pop("HALO_DATA_ROOT", None)
                if root is not None:
                    env["HALO_DATA_ROOT"] = root
                result = subprocess.run([str(executable)], env=env, check=True,
                                        capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()