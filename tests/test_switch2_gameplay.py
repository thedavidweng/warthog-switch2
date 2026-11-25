import pathlib
import contextlib
import io
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import switch_logs


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DescriptorOrderingTest(unittest.TestCase):
    def test_uam2_ampere_macro_and_binary(self):
        if not shutil.which("docker"):
            self.skipTest("Docker unavailable")
        image = subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if image.returncode:
            self.skipTest("Switch 2 toolchain image unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = pathlib.Path(directory)
            relative = root.relative_to(ROOT)
            (root / "probe.vert").write_text(
                "#version 460\n"
                "#if !defined(DEKO3D) || DEKO3D != 200\n"
                "#error not Ampere\n#endif\n"
                "void main() { gl_Position = vec4(0.0); }\n")
            subprocess.run(
                [str(ROOT / "scripts/switch2/build.sh"), "uam2", "-s", "vert",
                 "-o", str(relative / "probe.dksh"),
                 "--asm=" + str(relative / "probe.asm"), str(relative / "probe.vert")],
                cwd=ROOT, check=True, capture_output=True, text=True)
            magic, header_size, control_size, code_size, _, count = struct.unpack_from(
                "<6I", (root / "probe.dksh").read_bytes())
            self.assertEqual(magic, 0x48534B44)
            self.assertGreater(header_size, 0)
            self.assertGreater(control_size, 0)
            self.assertGreater(code_size, 0)
            self.assertEqual(count, 1)
            self.assertTrue((root / "probe.asm").read_text().strip())

    def test_engine_asserts_actual_tick_rate(self):
        source = (ROOT / "port/switch2/host/headless_engine.c").read_text()
        self.assertIn('_Static_assert(TICKS_PER_SECOND == 30,', source)

    def test_tick_check_on_host(self):
        program = r"""
#include <stdint.h>
enum { TICKS_PER_SECOND = 30 };
typedef struct { float i, j, k; } real_vector3d;
typedef struct { float x, y, z; } real_point3d;
typedef struct { float unused; } real_matrix4x3;
unsigned int seed_random(uint32_t *);
void seed_random_direction3d(uint32_t *, real_vector3d *);
void matrix4x3_rotation_from_angles(real_matrix4x3 *, float, float, float);
void matrix4x3_transform_point(real_matrix4x3 *, real_point3d *, real_point3d *);
#include "port/switch2/host/headless_engine_checks.h"
int main(void) { return !warthog_verify_simulation_ticks(); }
"""
        with tempfile.TemporaryDirectory() as directory:
            binary = pathlib.Path(directory) / "check"
            subprocess.run(["clang", "-x", "c", "-std=c11", "-I", str(ROOT),
                            "-o", str(binary), "-"], input=program, text=True, check=True,
                           capture_output=True)
            subprocess.run([str(binary)], check=True)

    def test_descriptor_writes_precede_ampere_invalidation(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        for write in (
            "dkImageDescriptorInitialize(&descriptors[texture->slot], &view, false, false);",
            "dkSamplerDescriptorInitialize(&descriptors[index], &made);",
        ):
            following = source.split(write, 1)[1].lstrip()
            self.assertTrue(following.startswith("#ifdef __SWITCH2__"))
            self.assertIn("barrier(DkBarrier_None, DkInvalidateFlags_Descriptors);",
                          following.split("#endif", 1)[0])

    def test_gpu_fault_records_include_base_and_are_connected(self):
        log = (ROOT / "port/switch2/host/warthog_log.c").read_text()
        callback = log.split("void warthog_dk_debug_callback(", 1)[1]
        self.assertLess(callback.index('raw_field(fd, "MODULE_BASE: "'),
                        callback.index("raw_frames("))
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        for name, end in (("static void debug_callback(", "/* ----------"),
                          ("static int queue_faulted(", "/* (under dk_lock)")):
            self.assertIn("warthog_dk_debug_callback(", source.split(name, 1)[1].split(end, 1)[0])

    def test_switch2_does_not_initialize_legacy_nv_address_space(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        initialize = source.split("static int initialize(void)", 1)[1].split("dk.ready = 1;", 1)[0]
        self.assertIn("#ifndef __SWITCH2__", initialize)
        guarded = initialize.split("#ifndef __SWITCH2__", 1)[1].split("#endif", 1)[0]
        self.assertIn("nvMapInit();", guarded)
        self.assertIn("nvAddressSpaceCreate(", guarded)
        shutdown = source.split("if (dk.nv_ready) nvAddressSpaceClose", 1)[1]
        self.assertTrue(shutdown.split("nvMapExit()", 1)[0].endswith("#ifndef __SWITCH2__\n\tif (dk.ready) "))

    def test_gameplay_maps_are_loaded_twice(self):
        source = (ROOT / "port/switch2/host/headless_engine.c").read_text()
        self.assertIn('"bloodgulch.map", "levels\\\\test\\\\bloodgulch\\\\bloodgulch"', source)
        self.assertIn('"a10.map", "levels\\\\a10\\\\a10"', source)
        self.assertIn("loaded twice", source)

    def test_gpu_fault_is_symbolized_from_elf_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            elf = root / "test.elf"
            data = bytearray(64 + 3 * 64 + 16 + 48)
            data[:6] = b"\x7fELF\x02\x01"
            struct.pack_into("<Q", data, 40, 64)
            struct.pack_into("<HH", data, 58, 64, 3)
            struct.pack_into("<IIQQQQIIQQ", data, 128, 0, 3, 0, 0, 256, 16, 0, 0, 1, 0)
            struct.pack_into("<IIQQQQIIQQ", data, 192, 0, 2, 0, 0, 272, 48, 1, 1, 8, 24)
            data[256:262] = b"\0test\0"
            struct.pack_into("<IBBHQQ", data, 296, 1, 0x12, 0, 1, 0x100, 0x20)
            elf.write_bytes(data)
            (root / "warthog.log").write_text(
                "FAULT_KIND: GPU_FAULT\nMODULE_BASE: 0x10000\n"
                "FRAME #00: 0x10104 (warthog.elf+0x104)\n")
            output = io.StringIO()
            with mock.patch.object(switch_logs, "SWITCH2_LOCAL", root), \
                 mock.patch.object(switch_logs.shutil, "which", return_value=None), \
                 contextlib.redirect_stdout(output):
                switch_logs.switch2_main(["--no-fetch", "--elf", str(elf)])
            self.assertIn("outcome: GPU_FAULT", output.getvalue())
            self.assertIn("warthog.elf+0x104: test+0x4", output.getvalue())

    def test_retired_slots_and_command_list_invalidation(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        collect = source.split("static void releases_collect(void)", 1)[1].split(
            "static int slot_take", 1)[0]
        self.assertLess(collect.index("release->serial > retired"),
                        collect.index("tex.slots_free[tex.slots_free_count++]"))
        begin = source.split("static void command_memory_begin(void)", 1)[1].split(
            "static uint32_t command_memory_used", 1)[0]
        self.assertIn("DkInvalidateFlags_Descriptors", begin)


if __name__ == "__main__":
    unittest.main()
