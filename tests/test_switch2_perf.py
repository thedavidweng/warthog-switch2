"""Host checks for Switch 2 performance tooling."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_switch2_devloop import MockFtp, run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import switch_profile


class ProfileTests(unittest.TestCase):
    def test_release_build_flags_disable_development_profiling(self):
        build = (ROOT / "port/switch2/build.py").read_text()
        self.assertIn("profiling = 0 if release else 1", build)
        self.assertIn("-DWARTHOG_DEV_PROFILING={profiling}", build)

    def test_clock_comparison_restores_normal_after_error(self):
        program = """
#include "switch2_perf.h"
#include <stdio.h>
static int modes[4], count;
static void clock(enum switch2_perf_clock_mode mode, void *unused) { (void)unused; modes[count++] = mode; }
static int run(enum switch2_perf_clock_mode mode, void *unused) { (void)mode; (void)unused; return 1; }
int main(void) { int result = switch2_perf_compare_clocks(run, clock, 0);
  printf("%d %d %d\\n", result, count, modes[count - 1]); }
"""
        with tempfile.TemporaryDirectory() as temp:
            source, binary = Path(temp) / "clock.c", Path(temp) / "clock"
            source.write_text(program)
            subprocess.run(["cc", "-std=c11", "-I", str(ROOT / "port/switch2/host"),
                            str(source), str(ROOT / "port/switch2/host/switch2_perf.c"),
                            "-o", str(binary)], check=True, capture_output=True, text=True)
            output = subprocess.run([str(binary)], check=True, capture_output=True, text=True).stdout
        self.assertEqual(output.strip(), "-1 2 0")

    def test_real_elf_native_address_symbolization(self):
        elf = ROOT / "build/switch2/warthog.elf"
        if not elf.exists() or not all(shutil.which(switch_profile.tool(tool))
                                       for tool in ("nm", "readelf", "addr2line")):
            self.skipTest("requires a Switch 2 ELF and its symbol tools")
        anchor = switch_profile.symbol_address(elf, "host_logf")
        target = switch_profile.symbol_address(elf, "host_dk_shutdown")
        self.assertIsNotNone(anchor)
        self.assertIsNotNone(target)
        shift = 0x7100000000
        profile = {"image": "warthog.elf", "anchor": ("host_logf", anchor + shift),
                   "threads": {0: {"kind": "game", "samples": 1, "failed": 0}},
                   "stacks": [(1, 0, [target + shift])], "seconds": 1, "hz": 500, "dropped": 0}
        args = SimpleNamespace(images=elf.parent, target="switch2", thread="game", top=30, folded=None)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(switch_profile.report(args, [profile]), 0)
        self.assertIn("host_dk_shutdown", output.getvalue())

    def test_fetch_prints_report_even_without_profiles(self):
        directory = "/switch/warthog/logs/profile"
        report = {"runs": [{"scene": "a10", "mode": "Normal", "refresh_hz": 60,
                            "cpu_ms": {"p95": 20}, "gpu_ms": {"mean": 8},
                            "submit_wait_us": 5, "acquire_max_us": 6, "fence_max_us": 7,
                            "shader": {"count": 2, "total_ms": 12, "mean_ms": 6, "max_ms": 8},
                            "map_load_ms": 100, "memory_peak_bytes": 4096}]}
        with MockFtp(files={"/switch/warthog/logs/perf_report.json": json.dumps(report).encode()},
                     directories=("/", "/switch", "/switch/warthog",
                                  "/switch/warthog/logs", directory)) as ftp:
            result = run(ROOT / "tools/switch_profile.py", "--target", "switch2", "--fetch",
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": str(ftp.port)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a10", result.stdout)

    def test_performance_report_summary(self):
        data = {"runs": [{"scene": "a10", "mode": "Normal", "refresh_hz": 60,
                          "cpu_ms": {"mean": 12, "p50": 10, "p95": 20, "p99": 30, "max": 40},
                          "gpu_ms": {"mean": 8}, "submit_wait_us": 5,
                          "acquire_max_us": 6, "fence_max_us": 7,
                          "shader": {"count": 2, "total_ms": 12, "mean_ms": 6, "max_ms": 8},
                          "map_load_ms": 100, "memory_peak_bytes": 4096}]}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            switch_profile.summarize_perf(data)
        for text in ("a10", "Normal", "60", "p95", "20", "4096", "UAM2"):
            self.assertIn(text, output.getvalue())

    def test_performance_report_compares_clock_modes(self):
        common = {"scene": "a10", "refresh_hz": 60,
                  "gpu_ms": {"mean": 8}, "submit_wait_us": 5, "acquire_max_us": 6,
                  "fence_max_us": 7, "shader": {"count": 0, "total_ms": 0,
                                                "mean_ms": 0, "max_ms": 0},
                  "map_load_ms": 100, "memory_peak_bytes": 4096}
        data = {"runs": [{**common, "mode": "Normal", "cpu_ms": {"mean": 10}},
                         {**common, "mode": "FastLoad", "cpu_ms": {"mean": 8}}]}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            switch_profile.summarize_perf(data)
        self.assertIn("-20.0%", output.getvalue())

    def test_percentiles_and_shader_memory_aggregation(self):
        program = """
#include "switch2_perf.h"
#include <stdio.h>
int main(void) {
    struct switch2_perf_stats stats = {0};
    struct switch2_perf_summary result;
    for (int i = 100; i > 0; --i) switch2_perf_add_frame(&stats, i);
    switch2_perf_add_shader(&stats, 4);
    switch2_perf_add_shader(&stats, 8);
    switch2_perf_add_memory(&stats, 10);
    switch2_perf_add_memory(&stats, 5);
    result = switch2_perf_summary(&stats);
    printf("%.1f %.1f %.1f %.1f %.1f %llu %.1f %.1f %llu\\n",
           result.mean, result.p50, result.p95, result.p99, result.max,
           (unsigned long long)stats.shader_count, stats.shader_total_ms,
           stats.shader_max_ms, (unsigned long long)stats.memory_peak);
    switch2_perf_clear(&stats);
}
"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "perf_test.c"
            binary = Path(temp) / "perf_test"
            source.write_text(program)
            host = ROOT / "port/switch2/host"
            subprocess.run(["cc", "-std=c11", "-I", str(host), str(source),
                            str(host / "switch2_perf.c"), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "50.5 50.0 95.0 99.0 100.0 2 12.0 8.0 10")

    def test_switch2_fetch_uses_environment_and_profile_directory(self):
        directory = "/switch/warthog/logs/profile"
        with MockFtp(directories=("/", "/switch", "/switch/warthog",
                                  "/switch/warthog/logs", directory)) as ftp:
            result = run(ROOT / "tools/switch_profile.py", "--target", "switch2", "--fetch",
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": str(ftp.port)})
        self.assertIn("NLST " + directory, ftp.commands)
        self.assertIn("fetched 0 profile(s)", result.stderr)

    def test_switch2_fetch_requires_host_environment(self):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("WARTHOG_SWITCH2_")}
        result = subprocess.run([sys.executable, str(ROOT / "tools/switch_profile.py"),
                                 "--target", "switch2", "--fetch"],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WARTHOG_SWITCH2_HOST", result.stderr)

    def test_native_lp64_addresses_are_relocated_to_the_single_elf(self):
        profile = {
            "image": "warthog.elf", "anchor": ("host_logf", 0x7100001000),
            "threads": {0: {"kind": "game", "samples": 1, "failed": 0}},
            "stacks": [(1, 0, [0x7100001100, 0x7100001204])],
            "seconds": 1, "hz": 500, "dropped": 0,
        }
        args = SimpleNamespace(images=Path("/build"), target="switch2", thread="game",
                               top=30, folded=None)
        with mock.patch.object(switch_profile, "symbol_address", return_value=0x1000), \
             mock.patch.object(switch_profile, "load_ranges", return_value=[(0x1000, 0x3000)]), \
             mock.patch.object(switch_profile, "symbolize",
                               return_value={0x1100: "game_tick", 0x1200: "game_loop"}) as symbols, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(switch_profile.report(args, [profile]), 0)
        symbols.assert_called_once_with(Path("/build/warthog.elf"), {0x1100, 0x1200})
        self.assertIn("game_tick", output.getvalue())
        self.assertIn("game_loop", output.getvalue())


if __name__ == "__main__":
    unittest.main()
