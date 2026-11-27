"""Host checks for Switch 2 local split-screen geometry and routing."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "port/switch2/host"
ENGINE_CONNECTION = ROOT / "chupathingyce/source/networking/network_connection.h"


class SplitScreenTest(unittest.TestCase):
    def test_engine_keeps_four_local_players(self):
        text = ENGINE_CONNECTION.read_text()
        self.assertIn("MAXIMUM_NUMBER_OF_LOCAL_PLAYERS = 4", text)
        self.assertNotIn("HALO_CONSOLE_PLAYERS < 4", (ROOT / "port/switch2/engine_build.py").read_text())

    def compile_and_run(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "check.c"
            executable = Path(tmp) / "check"
            source.write_text(body)
            subprocess.run(
                ["clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(HOST), str(source),
                 str(HOST / "switch2_splitscreen.c"),
                 str(HOST / "switch2_input.c"), "-lm", "-o", str(executable)],
                check=True,
            )
            subprocess.run([str(executable)], check=True)

    def test_layouts_are_disjoint_and_confined(self):
        self.compile_and_run(r"""
#include <assert.h>
#include "switch2_splitscreen.h"
static int overlap(struct switch2_split_rect a, struct switch2_split_rect b) {
    return a.x < b.x + b.width && b.x < a.x + a.width &&
           a.y < b.y + b.height && b.y < a.y + a.height;
}
int main(void) {
    struct switch2_split_rect v[4], c;
    unsigned count, i, j;
    count = switch2_splitscreen_layout(2, 1920, 1080, SWITCH2_SPLIT_HORIZONTAL, v);
    assert(count == 2 && v[0].height == 540 && v[1].y == 540);
    for (i = 0; i < count; ++i) for (j = i + 1; j < count; ++j) assert(!overlap(v[i], v[j]));
    count = switch2_splitscreen_layout(2, 1920, 1080, SWITCH2_SPLIT_VERTICAL, v);
    assert(v[0].width == 960 && v[1].x == 960);
    count = switch2_splitscreen_layout(3, 1920, 1080, SWITCH2_SPLIT_HORIZONTAL, v);
    assert(count == 3 && v[2].y == 540);
    count = switch2_splitscreen_layout(4, 1920, 1080, SWITCH2_SPLIT_HORIZONTAL, v);
    assert(count == 4);
    for (i = 0; i < count; ++i) {
        assert(v[i].x + v[i].width <= 1920 && v[i].y + v[i].height <= 1080);
        for (j = i + 1; j < count; ++j) assert(!overlap(v[i], v[j]));
        c = switch2_splitscreen_clamp(v[i], 1920, 1080);
        assert(c.x == v[i].x && c.y == v[i].y && c.width == v[i].width && c.height == v[i].height);
    }
    c = switch2_splitscreen_confine((struct switch2_split_rect){0, 0, 2000, 2000}, v[3]);
    assert(c.x == v[3].x && c.y == v[3].y &&
           c.width == v[3].width && c.height == v[3].height);
    return 0;
}
""")

    def test_four_controllers_bind_without_collision_or_cross_talk(self):
        self.compile_and_run(r"""
#include <assert.h>
#include "switch2_input.h"
int main(void) {
    struct switch2_controller_slots slots;
    int wireless[SWITCH2_NPAD_COUNT] = {1, 1, 1, 1};
    switch2_slots_init(&slots);
    switch2_slots_update(&slots, 0, wireless);
    assert(switch2_slot_npad(&slots, 0) == 0);
    assert(switch2_slot_npad(&slots, 1) == 1);
    assert(switch2_slot_npad(&slots, 2) == 2);
    assert(switch2_slot_npad(&slots, 3) == 3);
    wireless[1] = 0;
    switch2_slots_update(&slots, 0, wireless);
    assert(switch2_slot_npad(&slots, 0) == 0);
    assert(!switch2_slot_connected(&slots, 1));
    assert(switch2_slot_npad(&slots, 2) == 2);
    assert(switch2_slot_npad(&slots, 3) == 3);
    return 0;
}
""")

    def test_secondary_route_and_frame_stats(self):
        self.compile_and_run(r"""
#include <assert.h>
#include "switch2_splitscreen.h"
int main(void) {
    struct switch2_present_route route, secondary = {
        SWITCH2_OUTPUT_SECONDARY, {10, 20, 300, 400}
    };
    struct switch2_splitscreen_stats stats;
    switch2_splitscreen_get_present_route(&route, 1920, 1080);
    assert(route.surface == SWITCH2_OUTPUT_PRIMARY &&
           route.destination.width == 1920 && route.destination.height == 1080);
    switch2_splitscreen_set_present_route(&secondary);
    switch2_splitscreen_get_present_route(&route, 1920, 1080);
    assert(route.surface == SWITCH2_OUTPUT_SECONDARY && route.destination.x == 10);
    switch2_splitscreen_record_frame(4, 100);
    switch2_splitscreen_record_frame(4, 250);
    switch2_splitscreen_get_stats(&stats);
    assert(stats.active_viewports == 4 && stats.frames == 2 &&
           stats.total_ns == 350 && stats.maximum_ns == 250);
    assert(switch2_splitscreen_pause_leave_match(4));
    return 0;
}
""")
