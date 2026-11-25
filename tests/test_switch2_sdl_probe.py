"""Checks for the Switch 2 SDL platform decision."""

import unittest
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SDLDecisionTest(unittest.TestCase):
    def test_imported_helpers_preserve_upstream_header_and_provenance(self):
        for extension in ("c", "h"):
            text = (ROOT / f"port/switch2/host/nx2_platform.{extension}").read_text()
            lines = text.splitlines()
            self.assertTrue(lines[0].startswith("// nx2_platform:"))
            self.assertIn("Copyright", text)
            self.assertEqual(lines[1], "// SPDX-License-Identifier: MIT")
            self.assertIn("NaGaa95/dolphin-nx", lines[2])
            self.assertIn(f"Source/Core/Common/nx2_platform.{extension}", lines[2])
            self.assertIn("7fb685b353e19a9a5848e9bd658945d1f9cd382a", lines[3])

    def test_decision_records_the_platform_boundary(self):
        text = (ROOT / "docs/adr/0003-sdl2-host-sdl3-seam.md").read_text()
        for term in ("SDL2", "SDL3", "Drako3D", "nwindowGetDefault()",
                     "libounce", "Nmouse", "hardware"):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_probe_wraps_video_and_refused_services(self):
        build = (ROOT / "port/switch2/build.py").read_text()
        for name in ("SDL_VideoInit", "SDL_VideoQuit", "hidInitializeKeyboard",
                     "hidInitializeMouse", "smGetServiceWrapper", "__syscall_thread_create"):
            self.assertIn("--wrap=" + name, build)

    def test_toolchain_link_map_and_live_symbols(self):
        if not shutil.which("docker") or subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode:
            self.skipTest("pinned local toolchain image is not available")
        script = ROOT / "scripts/switch2/build.sh"
        subprocess.run([str(script), "configure"], cwd=ROOT, check=True)
        subprocess.run([str(script), "ninja", "switch2-probe-sdl"], cwd=ROOT, check=True)
        map_text = (ROOT / "build/switch2/sdl_probe.elf.map").read_text()
        self.assertIn("libSDL2.a", map_text)
        self.assertIn("libounce.a", map_text)
        for library in ("libnx.a", "libEGL.a", "libGLESv2.a", "libdrm_nouveau.a",
                        "libdrm.a", "libglapi.a", "libmesa"):
            self.assertNotIn(library, map_text)
        symbols = subprocess.check_output(
            [str(script), "/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm",
             "build/switch2/sdl_probe.elf"], cwd=ROOT, text=True)
        self.assertNotIn(" SDL_EGL_", symbols)
        self.assertNotIn(" SDL_VideoInit\n", symbols)
        for name in ("sdl_probe.elf", "sdl_probe.nro"):
            self.assertTrue((ROOT / "build/switch2" / name).is_file())


if __name__ == "__main__":
    unittest.main()
