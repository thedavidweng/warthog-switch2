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
    const float upright[] = { 0, -1, 0 };
    const float flat[] = { 0, 0, -1 };
    const float tilted[] = { 0, -0.70710678f, -0.70710678f };
    float yaw = 0, pitch = 0;
    /* A right turn and upward tilt, measured in turns per second. */
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ 0.5f, -1.0f, 0 }, upright, 20000000, &yaw, &pitch);
    assert(fabsf(yaw + 0.12566371f) < 0.00001f);
    assert(fabsf(pitch - 0.06283185f) < 0.00001f);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ 0.001f, 0.001f, 0 }, upright, 20000000, &yaw, &pitch);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 0, (float[]){ 5, 5, 0 }, upright, 20000000, &yaw, &pitch);
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ 5, 5, 0 }, upright, 100000001, &yaw, &pitch);
    assert(fabsf(yaw + 0.12566371f) < 0.00001f);
    assert(fabsf(pitch - 0.06283185f) < 0.00001f);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ 0, 0, -1 }, flat, 20000000, &yaw, &pitch);
    assert(fabsf(yaw + 0.12566371f) < 0.00001f && pitch == 0);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, tilted, tilted, 20000000, &yaw, &pitch);
    assert(fabsf(yaw + 0.12566371f) < 0.00001f && pitch == 0);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ 0, 1, 0 }, flat, 20000000, &yaw, &pitch);
    assert(yaw == 0 && pitch == 0);
    /* A fine correction at 1.8 degrees per second. */
    switch2_gyro_add(SWITCH2_GYRO_NORMAL, 1, (float[]){ -0.005f, 0.005f, 0 }, upright, 20000000, &yaw, &pitch);
    assert(fabsf(yaw - 0.00062832f) < 0.00001f);
    assert(fabsf(pitch + 0.00062832f) < 0.00001f);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_RIGHT, 1, (float[]){ 1, 2, 0 }, (float[]){ -1, 0, 0 }, 20000000, &yaw, &pitch);
    assert(fabsf(yaw - 0.12566371f) < 0.00001f);
    assert(fabsf(pitch + 0.25132741f) < 0.00001f);
    yaw = pitch = 0;
    switch2_gyro_add(SWITCH2_GYRO_LEFT, 1, (float[]){ 1, 2, 0 }, (float[]){ 1, 0, 0 }, 20000000, &yaw, &pitch);
    assert(fabsf(yaw + 0.12566371f) < 0.00001f);
    assert(fabsf(pitch - 0.25132741f) < 0.00001f);

    struct switch2_gyro_recenter button = { 0 };
    switch2_gyro_recenter_poll(&button, 1, 1, 100);
    assert(button.down && button.discard_motion && !button.level_view);
    button.discard_motion = 0;
    switch2_gyro_recenter_poll(&button, 1, 0, 200);
    assert(!button.down && button.discard_motion && button.level_view);
    button.level_view = button.discard_motion = 0;
    switch2_gyro_recenter_poll(&button, 1, 0, 210);
    assert(!button.discard_motion && !button.level_view);

    switch2_gyro_recenter_poll(&button, 1, 1, 300);
    switch2_gyro_recenter_poll(&button, 1, 1, 740);
    assert(button.down && button.discard_motion && !button.level_view);
    button.discard_motion = 0;
    switch2_gyro_recenter_poll(&button, 1, 0, 750);
    assert(!button.down && button.discard_motion && !button.level_view);

    switch2_gyro_recenter_poll(&button, 0, 1, 900);
    switch2_gyro_recenter_poll(&button, 1, 1, 910);
    switch2_gyro_recenter_poll(&button, 1, 0, 920);
    assert(!button.down && button.discard_motion && !button.level_view);
    return 0;
}
""")
            subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(HOST), str(source),
                            str(HOST / "switch2_input.c"), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
