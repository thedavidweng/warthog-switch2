"""Host checks for Switch 2 lifecycle decisions."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LifecycleTest(unittest.TestCase):
    def test_restricted_applet_memory_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "check"
            source = """
#include <assert.h>
#include "switch2_lifecycle.h"
int main(void) {
    assert(switch2_lifecycle_refuse_launch(1, 512ULL * 1024 * 1024 - 1));
    assert(switch2_lifecycle_refuse_launch(1, 512ULL * 1024 * 1024));
    assert(switch2_lifecycle_refuse_launch(0, 0));
    assert(!switch2_lifecycle_refuse_launch(0, 512ULL * 1024 * 1024));
    assert(switch2_lifecycle_size_changed(1920, 1080, 3840, 1080));
    assert(switch2_lifecycle_size_changed(1920, 1080, 1920, 2160));
    assert(!switch2_lifecycle_size_changed(1920, 1080, 1920, 1080));
    return 0;
}
"""
            subprocess.run(
                ["cc", "-x", "c", "-I", str(ROOT / "port/switch2/host"),
                 "-", "-o", str(exe)],
                input=source, text=True, check=True, capture_output=True,
            )
            subprocess.run([str(exe)], check=True)

    def test_exit_and_teardown_are_connected(self):
        bridge = (ROOT / "port/switch2/host/switch2_sdl3_bridge.c").read_text()
        self.assertIn("AppletHookType_OnExitRequest", bridge)
        self.assertIn("SDL_EVENT_QUIT", bridge)
        self.assertIn("appletHook(&lifecycle_cookie", bridge)
        self.assertIn("appletUnhook(&lifecycle_cookie", bridge)
        host = (ROOT / "port/switch2/host/switch2_host_bridge.c").read_text()
        actions = ("switch2_lifecycle_stop();", "host_dk_shutdown();", "host_sdl_quit();",
                   "switch2PlatformReleaseWindow();", "nx2ExitCleanupNow();",
                   "switch2PlatformRestoreClock();")
        positions = [host.index(action, host.index("void switch2_lifecycle_cleanup(")) for action in actions]
        self.assertEqual(positions, sorted(positions))
        main = (ROOT / "port/switch2/host/main.c").read_text()
        self.assertIn("atexit(switch2_lifecycle_cleanup)", main)
        platform = (ROOT / "port/switch2/host/nx2_platform.c").read_text()
        self.assertIn("ApmCpuBoostMode_Normal", platform)
        self.assertNotIn("appletCancelCpuBoostMode", platform)

    def test_documentation_marks_hardware_pending(self):
        doc = (ROOT / "docs/lifecycle.md").read_text()
        self.assertIn("No capability above has reached Tested on hardware", doc)
        self.assertIn("HOME suspend/resume under kaiHEN | Not yet supported", doc)
