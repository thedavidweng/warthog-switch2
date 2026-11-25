"""Host checks for Switch 2 controller input."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "port/switch2/host"


class ControllerInputTest(unittest.TestCase):
    def test_slots_preserve_player_zero_across_transitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "check"
            source = Path(tmp) / "check.c"
            source.write_text(r"""
#include <assert.h>
#include "switch2_input.h"
int main(void) {
    struct switch2_controller_slots slots;
    int wireless[SWITCH2_NPAD_COUNT] = { 0, 0, 0, 0 };
    switch2_slots_init(&slots);
    switch2_slots_update(&slots, 1, wireless);
    assert(switch2_slot_npad(&slots, 0) == SWITCH2_NPAD_HANDHELD);
    wireless[0] = 1;
    switch2_slots_update(&slots, 0, wireless);
    assert(switch2_slot_npad(&slots, 0) == SWITCH2_NPAD_NO1);
    switch2_slots_update(&slots, 1, wireless);
    assert(switch2_slot_npad(&slots, 0) == SWITCH2_NPAD_NO1);
    wireless[0] = 0;
    switch2_slots_update(&slots, 1, wireless);
    assert(switch2_slot_npad(&slots, 0) == SWITCH2_NPAD_HANDHELD);
    wireless[2] = 1;
    switch2_slots_update(&slots, 0, wireless);
    assert(switch2_slot_npad(&slots, 0) == SWITCH2_NPAD_NO1 + 2);
    wireless[2] = 0;
    switch2_slots_update(&slots, 0, wireless);
    assert(!switch2_slot_connected(&slots, 0));
    return 0;
}
""")
            subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(HOST), str(source),
                            str(HOST / "switch2_input.c"), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_gyro_settings_and_rumble_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "check"
            source = Path(tmp) / "check.c"
            source.write_text(r"""
#include <assert.h>
#include <math.h>
#include "switch2_input.h"
int main(void) {
    struct switch2_gyro_settings settings = {
        SWITCH2_GYRO_ZOOM_ONLY, 2.0f, 3.0f, 1, 1
    };
    float yaw, pitch;
    switch2_gyro_apply(&settings, 0, 1, 2, &yaw, &pitch);
    assert(yaw == 0 && pitch == 0);
    switch2_gyro_apply(&settings, 1, 1, 2, &yaw, &pitch);
    assert(fabsf(yaw + 2) < 0.00001f && fabsf(pitch + 6) < 0.00001f);
    assert(switch2_rumble_level(0) == 0);
    assert(switch2_rumble_level(65535) == 65535);
    assert(switch2_rumble_level(65536) == 65535);
    return 0;
}
""")
            subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(HOST), str(source),
                            str(HOST / "switch2_input.c"), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_gyro_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "check"
            source = Path(tmp) / "check.c"
            source.write_text(r"""
#include <assert.h>
#include <math.h>
#include "switch2_input.h"
int main(void) {
    float yaw = 0, pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, 0.5f, -1.0f, 20000000, &yaw, &pitch);
    assert(fabsf(yaw - 0.02f) < 0.00001f);
    assert(fabsf(pitch + 0.01f) < 0.00001f);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, 0.001f, 0.001f, 20000000, &yaw, &pitch);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 0, 5, 5, 20000000, &yaw, &pitch);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, 5, 5, 100000001, &yaw, &pitch);
    assert(fabsf(yaw - 0.02f) < 0.00001f);
    assert(fabsf(pitch + 0.01f) < 0.00001f);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_RIGHT, 1, 1, 2, 20000000, &yaw, &pitch);
    assert(fabsf(yaw + 0.02f) < 0.00001f);
    assert(fabsf(pitch - 0.04f) < 0.00001f);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_LEFT, 1, 1, 2, 20000000, &yaw, &pitch);
    assert(fabsf(yaw - 0.02f) < 0.00001f);
    assert(fabsf(pitch + 0.04f) < 0.00001f);
    return 0;
}
""")
            subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(HOST), str(source),
                            str(HOST / "switch2_input.c"), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
