import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "port/switch2/host/switch2_display.c"
HEADER = ROOT / "port/switch2/host/switch2_display.h"


class Switch2DisplayTests(unittest.TestCase):
    def test_policy_is_pure_c_and_separates_dimensions(self):
        self.assertIn("internal_width", HEADER.read_text())
        self.assertIn("output_width", HEADER.read_text())
        self.assertIn("SWITCH2_SIMULATION_HZ 30", HEADER.read_text())
        self.assertIn("interpolation", HEADER.read_text())
        self.assertIn("granted_refresh", HEADER.read_text())

    def test_host_policy(self):
        source = r'''
        #include <stdio.h>
        #include "switch2_display.h"
        int main(void) {
          struct switch2_display_state s = {0};
          switch2_display_set_output(&s, 3840, 2160, true);
          if (switch2_display_clamp_refresh(3840, 2160, 120) != 60) return 1;
          if (switch2_display_clamp_refresh(2560, 1440, 120) != 120) return 2;
          if (switch2_display_interval_hz(1, 60) != 60) return 3;
          switch2_display_set_internal(&s, 1080);
          if (s.internal_height != 1080 || s.output_height != 2160) return 4;
          puts("ok");
        }
        '''
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp) / "test.c"
            exe = pathlib.Path(tmp) / "test"
            c.write_text(source)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-I", str(HEADER.parent),
                            str(c), str(DISPLAY), "-o", str(exe)], check=True)
            self.assertEqual(subprocess.check_output([str(exe)], text=True).strip(), "ok")

    def test_no_4k120_or_image_generation(self):
        texts = [
            (ROOT / "port/switch2/host/nx2_platform.c").read_text(),
            (ROOT / "tools/switch_menus.py").read_text(),
            (ROOT / "docs/switch1-caps-review.md").read_text(),
        ]
        self.assertNotRegex("\n".join(texts), r"4K\s*120|4K120|LSFG|image-based")
        self.assertIn("nwindowGetPresentInterval", texts[0])
        self.assertIn("nx2DisplayReapply", (ROOT / "port/switch/host/host_dk.c").read_text())

    def test_switch2_menu_target_and_switch1_defaults(self):
        menus = (ROOT / "tools/switch_menus.py").read_text()
        self.assertIn('--target", choices=("switch", "switch2")', menus)
        self.assertIn("--target switch2", (ROOT / "port/switch2/build.py").read_text())
        self.assertIn('("720P", "720")', menus)
        self.assertIn('("2160P", "2160")', menus)
        self.assertIn('target == "switch2" and setting == "performance.cpu_clock"', menus)

    def test_config_and_clock_policy(self):
        config = (ROOT / "port/switch2/overrides/port/linux/src/port_config.c").read_text()
        self.assertIn('#define DEFAULT_RESOLUTION_LIMIT "\\"1080\\""', config)
        self.assertIn('_config_string, "\\"stock\\""', config)
        platform = (ROOT / "port/switch2/host/nx2_platform.c").read_text()
        self.assertIn("ApmCpuBoostMode_Normal", platform)


if __name__ == "__main__":
    unittest.main()
