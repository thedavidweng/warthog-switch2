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


class BasePathTest(unittest.TestCase):
    def test_switch2_base_path_uses_data_root(self):
        if not (SDL / "SDL3/SDL.h").is_file():
            self.skipTest("configure the Switch 2 build to obtain pinned SDL headers")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
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
                 "-I", str(directory), "-I", str(SDL),
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