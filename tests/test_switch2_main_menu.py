"""Checks for the shared renderer's Switch 2 memory boundary."""

import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RendererAddressTest(unittest.TestCase):
    def test_command_addresses_follow_platform_abi(self):
        guest = ROOT / "port/switch/guest"
        for flags, expected in (([], "4"), (["-D__SWITCH2__"], "sizeof(uintptr_t)")):
            subprocess.run(
                ["clang", "-x", "c", "-fsyntax-only", "-I", str(guest), *flags, "-"],
                input=('#include "dk_commands.h"\n'
                       f'_Static_assert(sizeof(dk_addr_t) == {expected}, "address width");\n'
                       '_Static_assert(sizeof(((struct dk_command_texture *)0)->source) == sizeof(dk_addr_t), "texture");\n'
                       '_Static_assert(sizeof(((struct dk_command_draw *)0)->index_address) == sizeof(dk_addr_t), "index");\n'
                       '_Static_assert(sizeof(((struct dk_hud_sheet *)0)->png) == sizeof(dk_addr_t), "png");\n'
                       '_Static_assert(sizeof(((struct dk_surface *)0)->data) == 4, "Xbox offset");\n'),
                text=True, check=True, capture_output=True,
            )


class SharedRendererTest(unittest.TestCase):
    def test_switch2_presentation_and_descriptor_invalidation(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        self.assertFalse((ROOT / "port/switch2/host/host_dk.c").exists())
        self.assertIn("output_height = SCREEN_FULL_HEIGHT;", source)
        self.assertIn("DkInvalidateFlags_Descriptors", source)
        self.assertIn("VI2 swapchain images cannot use hardware compression", source)

    def test_uam2_compiles_probe_shaders(self):
        probe = ROOT / "port/switch2/probe"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            directory = Path(tmp)
            for stage in ("vert", "frag"):
                shutil.copyfile(probe / f"warthog.{stage}", directory / f"shader.{stage}")
                subprocess.run(
                    ["docker", "run", "--rm", "-v", f"{directory}:/work",
                     "warthog-switch2-toolchain:local", "uam2", "-s", stage,
                     "-o", f"/work/shader.{stage}.dksh", f"/work/shader.{stage}"],
                    check=True,
                )
                self.assertEqual((directory / f"shader.{stage}.dksh").read_bytes()[:4], b"DKSH")


class RendererBackingTest(unittest.TestCase):
    def test_backing_lookup_requires_one_committed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "check.c"
            source.write_text(r"""
#include <assert.h>
#include <stdint.h>
#include <sys/mman.h>
#include "switch2_mman.h"
int main(void) {
    assert(switch2_mman_init());
    char *p = (char *)(uintptr_t)(xbox_address_space_base + SWITCH2_XBOX_WINDOW_LOW);
    assert(mmap(p, 4096, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p);
    char *backing = switch2_mman_heap_backing((uintptr_t)p, 4096);
    assert(backing && !((uintptr_t)backing % 4096));
    assert(switch2_mman_heap_backing((uintptr_t)p + 10, 100) == backing + 10);
    assert(!switch2_mman_heap_backing((uintptr_t)p, 8192));
    assert(mmap(p + 4096, 4096, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p + 4096);
    assert(!switch2_mman_heap_backing((uintptr_t)p, 8192));
    assert(!switch2_mman_heap_backing(0, 4096));
    switch2_mman_shutdown();
    assert(!switch2_mman_heap_backing((uintptr_t)p, 1));
    return 0;
}
""")
            host = ROOT / "port/switch2/host"
            executable = directory / "check"
            subprocess.run(["clang", "-I", str(host), str(host / "switch2_mman.c"),
                            str(source), "-pthread", "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
