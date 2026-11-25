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
    def test_nv2a_generators_compile_to_ampere_dksh(self):
        xdk = (ROOT / "chupathingyce/port/include/xdk/xdk_pdb.h").read_text()
        # Each enum has its own namespace; their values come from the engine.
        enums = "\n".join(
            "enum " + name + " {" + xdk.split("enum " + name + " {", 1)[1].split("};", 1)[0] + "};"
            for name in ("_D3DRENDERSTATETYPE", "_D3DCMPFUNC", "_D3DFOGMODE")
        )
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = pathlib.Path(directory)
            rel = root.relative_to(ROOT)
            shim = r"""
#include <stdint.h>
#define __HALO_LINUX_XGPU_H
typedef uint32_t DWORD;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
""" + enums + r"""
#define XGPU_VERTEX_ATTRIBUTE_COUNT 16
#define XGPU_VERTEX_CONSTANT_COUNT 192
#define XGPU_VERTEX_CONSTANT_BIAS 96
enum { _xgpu_sampler_none, _xgpu_sampler_2d, _xgpu_sampler_3d, _xgpu_sampler_cube };
struct xgpu_text { char *buffer; unsigned long length, capacity; };
void xgpu_text_append(struct xgpu_text *, const char *, ...);
#include "nv2a_pixel_key.h"
"""
            (root / "shim.h").write_text(shim)
            (root / "driver.c").write_text(r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dk_shaders.h"
int config_boolean(const char *key) { (void)key; return 0; }
const char *config_string(const char *key) { (void)key; return ""; }
int main(int argc, char **argv) {
    if (argc != 3) return 1;
    char path[512], *glsl;
    int which = atoi(argv[1]);
    if (which < 2) {
        uint32_t instructions[] = { 0, (1u << 21) | 0x1b, 2u << 26,
                                    (15u << 12) | (1u << 11) | 1u };
        if (which) instructions[1] |= 1u << 9;
        glsl = nv2a_dk_vertex_shader_to_glsl(instructions, 1, which ? 2 : 0);
    } else {
        struct nv2a_pixel_shader_key key = {0};
        key.sampler_type[0] = _xgpu_sampler_2d;
        key.sampler_type[1] = _xgpu_sampler_2d;
        key.texture_modes = 1 | (1 << 5);
        key.combiner_state[D3DRS_PSCOMBINERCOUNT] = 2;
        key.combiner_state[D3DRS_PSRGBINPUTS0] = (8u << 24) | (9u << 16);
        key.combiner_state[D3DRS_PSRGBOUTPUTS0] = 12u << 4;
        key.combiner_state[D3DRS_PSRGBINPUTS0 + 1] = (12u << 24) | (4u << 16);
        key.combiner_state[D3DRS_PSRGBOUTPUTS0 + 1] = 12u << 4;
        key.fog_enable = 1; key.fog_table_mode = D3DFOG_LINEAR;
        if (which == 3) key.texture_modes |= NV2A_PIXEL_KEY_CLIP;
        if (which == 4) key.texture_modes |= NV2A_PIXEL_KEY_WARP_BLEND;
        glsl = nv2a_dk_pixel_shader_to_glsl(&key);
    }
    if (!glsl) return 2;
    snprintf(path, sizeof(path), "%s/%d.glsl", argv[2], which);
    FILE *file = fopen(path, "w");
    if (!file) return 3;
    fputs(glsl, file); fclose(file); free(glsl);
    return 0;
}
""")
            guest = ROOT / "port/switch/guest"
            linux = ROOT / "chupathingyce/port/linux/src"
            subprocess.run(
                ["clang", "-std=c11", "-include", str(root / "shim.h"),
                 "-I", str(guest), "-I", str(linux),
                 str(root / "driver.c"), str(guest / "nv2a_vsh_dk.c"),
                 str(guest / "nv2a_psh_dk.c"), str(linux / "xgpu_text.c"),
                 "-o", str(root / "driver")], cwd=ROOT, check=True)
            for number in range(5):
                subprocess.run([str(root / "driver"), str(number), str(root)], check=True)
                glsl = (root / f"{number}.glsl").read_text()
                self.assertTrue(glsl.startswith("#version 460\n"))
                if number == 1:
                    self.assertIn("unpack_normpacked3(v1_packed)", glsl)
                    self.assertNotEqual(glsl, (root / "0.glsl").read_text())
                if number == 2:
                    self.assertIn("combiner stage 1", glsl)
                    self.assertIn("fog_parameters.y - xFog", glsl)
                if number == 3:
                    self.assertIn("clip_uv", glsl)
                if number == 4:
                    self.assertIn("warp_spread", glsl)
                stage = "vert" if number < 2 else "frag"
                subprocess.run(
                    [str(ROOT / "scripts/switch2/build.sh"), "uam2", "-s", stage,
                     "-o", str(rel / f"{number}.dksh"), "--asm=" + str(rel / f"{number}.asm"),
                     str(rel / f"{number}.glsl")], cwd=ROOT, check=True)
                magic, _, control, code, _, count = struct.unpack_from(
                    "<6I", (root / f"{number}.dksh").read_bytes())
                self.assertEqual(magic, 0x48534B44)
                self.assertGreater(control, 0)
                self.assertGreater(code, 0)
                self.assertEqual(count, 1)
                self.assertTrue((root / f"{number}.asm").read_text().strip())

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
