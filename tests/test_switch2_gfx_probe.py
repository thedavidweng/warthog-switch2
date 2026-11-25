"""Public build interfaces for the Switch 2 graphics probe."""

import base64
import pathlib
import shutil
import struct
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GraphicsProbeTests(unittest.TestCase):
    def test_graphics_probe_build_is_registered(self):
        build = (ROOT / "port/switch2/build.py").read_text()
        self.assertIn('"switch2-probe-gfx"', build)
        self.assertTrue((ROOT / "port/switch2/probe/gfx_probe.c").is_file())

    def test_graphics_probe_builds_with_toolchain(self):
        if not shutil.which("docker"):
            self.skipTest("Docker unavailable")
        available = subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if available.returncode:
            self.skipTest("Switch 2 toolchain image unavailable")
        script = ROOT / "scripts/switch2/build.sh"
        subprocess.run([str(script), "configure"], cwd=ROOT, check=True)
        subprocess.run([str(script), "ninja", "switch2", "switch2-probe-gfx"], cwd=ROOT, check=True)
        subprocess.run([str(script), "audit"], cwd=ROOT, check=True)
        self.assertEqual((ROOT / "build/switch2/gfx_probe.elf").read_bytes()[:4], b"\x7fELF")
        self.assertEqual((ROOT / "build/switch2/gfx_probe.nro").read_bytes()[0x10:0x14], b"NRO0")

    def test_graphics_probe_has_uncompressed_swapchain_and_descriptor_barrier(self):
        source = (ROOT / "port/switch2/probe/gfx_probe.c").read_text()
        self.assertNotIn("DkImageFlags_HwCompression", source)
        for flag in ("DkImageFlags_UsageRender", "DkImageFlags_UsagePresent",
                     "DkImageFlags_Usage2DEngine", "DkInvalidateFlags_Descriptors"):
            self.assertIn(flag, source)

    def test_graphics_probe_artifacts(self):
        elf = ROOT / "build/switch2/gfx_probe.elf"
        nro = ROOT / "build/switch2/gfx_probe.nro"
        if not elf.exists() and not nro.exists():
            self.skipTest("graphics probe has not been built")
        self.assertEqual(elf.read_bytes()[:4], b"\x7fELF")
        self.assertEqual(nro.read_bytes()[0x10:0x14], b"NRO0")
        self.assertIn(b"OUN0", nro.read_bytes()[:4096])

    def test_renderer_decision_records_compiler_and_contingency(self):
        adr = (ROOT / "docs/adr/0002-drako3d-uam2-renderer.md").read_text()
        for item in ("uam2rt_compile_glsl", "DkInvalidateFlags_Descriptors",
                     "ampere-<uam2-12hex>", "glslang", "OunceVK", "hardware"):
            self.assertIn(item, adr)

    def test_compatibility_headers_forward_to_drako3d(self):
        include = ROOT / "port/switch2/include"
        for suffix in ("h", "hpp"):
            self.assertEqual(
                (include / f"deko3d.{suffix}").read_text().strip(),
                f"#include <drako3d.{suffix}>",
            )

    def test_uam2_compiles_warthog_style_shaders(self):
        if not shutil.which("docker"):
            self.skipTest("Docker unavailable")
        available = subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if available.returncode:
            self.skipTest("Switch 2 toolchain image unavailable")
        for stage in ("vert", "frag"):
            source = ROOT / "port/switch2/probe" / f"warthog.{stage}"
            result = subprocess.run(
                ["docker", "run", "--rm", "-i", "-v", f"{source}:/shader:ro",
                 "warthog-switch2-toolchain:local", "sh", "-c",
                 'uam2 -s "$1" -o /tmp/shader.dksh /shader && base64 /tmp/shader.dksh',
                 "sh", stage],
                check=True, capture_output=True, text=True,
            )
            binary = base64.b64decode(result.stdout)
            self.assertGreaterEqual(len(binary), 24)
            magic, header_size, control_size, code_size, programs_offset, count = struct.unpack_from("<6I", binary)
            self.assertEqual(magic, 0x48534B44)
            self.assertGreaterEqual(header_size, 24)
            self.assertGreater(code_size, 0)
            self.assertLessEqual(control_size + code_size, len(binary))
            self.assertLess(programs_offset, control_size)
            self.assertGreater(count, 0)

    def test_uam2_runtime_contains_glsl_compiler(self):
        if not shutil.which("docker"):
            self.skipTest("Docker unavailable")
        available = subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if available.returncode:
            self.skipTest("Switch 2 toolchain image unavailable")
        result = subprocess.run(
            ["docker", "run", "--rm", "warthog-switch2-toolchain:local",
             "aarch64-none-elf-nm", "-u", "/opt/devkitpro/portlibs/switch2/lib/libuam2rt.a"],
            check=True, capture_output=True, text=True,
        )
        self.assertNotIn(" U uam2_compile_glsl", result.stdout)
        for symbol in ("getuid", "geteuid", "getgid", "getegid"):
            self.assertNotIn(f" U {symbol}\n", result.stdout)
