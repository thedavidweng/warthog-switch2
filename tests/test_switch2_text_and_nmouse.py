import ctypes
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class TextAndNmouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        so = pathlib.Path(cls.tmp.name) / "libtext.so"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-std=c11", "-Iport/switch2/host",
             "port/switch2/host/switch2_text_nmouse.c", "-o", str(so)],
            cwd=ROOT, check=True,
        )
        cls.lib = ctypes.CDLL(str(so))
        cls.lib.switch2_utf8_truncate.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_utf8_truncate.restype = ctypes.c_size_t

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_utf8_truncation_keeps_codepoints(self):
        value = ctypes.create_string_buffer("a中🙂z".encode())
        self.assertEqual(self.lib.switch2_utf8_truncate(value, 4), len("a中".encode()))
        self.assertEqual(value.value.decode(), "a中")

    def test_utf8_empty_and_exact_limit(self):
        value = ctypes.create_string_buffer("".encode())
        self.assertEqual(self.lib.switch2_utf8_truncate(value, 4), 0)
        value = ctypes.create_string_buffer("éx".encode())
        self.assertEqual(self.lib.switch2_utf8_truncate(value, 3), 3)
        self.assertEqual(value.value.decode(), "éx")

    def test_processor_deduplicates_and_uses_relative_delta(self):
        class Settings(ctypes.Structure):
            _fields_ = [("sensitivity_x", ctypes.c_float),
                        ("sensitivity_y", ctypes.c_float),
                        ("invert_x", ctypes.c_int), ("invert_y", ctypes.c_int)]
        class Processor(ctypes.Structure):
            _fields_ = [("last_sampling", ctypes.c_uint64),
                        ("have_sampling", ctypes.c_int), ("buttons", ctypes.c_uint32),
                        ("settings", Settings)]
        class Motion(ctypes.Structure):
            _fields_ = [("xrel", ctypes.c_int), ("yrel", ctypes.c_int),
                        ("buttons", ctypes.c_uint32),
                        ("button_pressed", ctypes.c_uint32),
                        ("button_released", ctypes.c_uint32)]
        self.lib.switch2_nmouse_processor_init.argtypes = [ctypes.POINTER(Processor)]
        self.lib.switch2_nmouse_process.argtypes = [
            ctypes.POINTER(Processor), ctypes.c_uint64, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint32, ctypes.POINTER(Motion)]
        p, m = Processor(), Motion()
        self.lib.switch2_nmouse_processor_init(ctypes.byref(p))
        p.settings.sensitivity_x = 2
        p.settings.sensitivity_y = 3
        p.settings.invert_y = 1
        self.assertEqual(self.lib.switch2_nmouse_process(
            ctypes.byref(p), 10, 4, 5, 1, ctypes.byref(m)), 1)
        self.assertEqual((m.xrel, m.yrel, m.button_pressed), (8, -15, 1))
        self.assertEqual(self.lib.switch2_nmouse_process(
            ctypes.byref(p), 10, 99, 99, 0, ctypes.byref(m)), 0)
        self.assertEqual(self.lib.switch2_nmouse_process(
            ctypes.byref(p), 11, 1, 2, 0, ctypes.byref(m)), 1)
        self.assertEqual(m.button_released, 1)

    def test_poll_accepts_samples_after_late_connection(self):
        host = ROOT / "port/switch2/host"
        source = (host / "switch2_text_nmouse.c").read_text()
        poll = source[source.index("unsigned switch2_nmouse_tracking_joycons("):
                      source.index("void switch2_text_nmouse_poll(void)")]
        stub = r"""
#include <assert.h>
#include "switch2_input.h"
#include "switch2_text_nmouse.h"
typedef int Result;
typedef int s32;
typedef unsigned u32;
typedef unsigned HidNpadIdType;
typedef unsigned HidNmouseHandle;
typedef struct { uint64_t sampling_number; int delta_x, delta_y; uint32_t buttons, flags; } HidNmouseStateWithDelta;
#define R_FAILED(rc) ((rc) != 0)
#define BIT(n) (1u << (n))
#define HID_NMOUSE_HANDLES_PER_NPAD 2
enum { HidNmouseType_JoyLeft = 2, HidNmouseType_JoyRight = 4 };
enum { HidMouseButton_Left = 1, HidMouseButton_Right = 2, SDL_BUTTON_LEFT = 1, SDL_BUTTON_RIGHT = 3 };
static int nmouse_ready = 1, nmouse_has_handle, nmouse_mode = SWITCH2_NMOUSE_AUTO, nmouse_active_mode = -1;
static int connected, total_x;
static unsigned tracking;
static unsigned nmouse_handle;
static uint32_t nmouse_suppression[4];
static float nmouse_accum_x, nmouse_accum_y;
static struct switch2_nmouse_processor nmouse_processor;
static void warthog_log(const char *level, const char *format, ...) { (void)level; (void)format; }
static int nmouse_source_types_for_mode(int mode) {
    if (mode == SWITCH2_NMOUSE_LEFT) return HidNmouseType_JoyLeft;
    if (mode == SWITCH2_NMOUSE_RIGHT) return HidNmouseType_JoyRight;
    return HidNmouseType_JoyLeft | HidNmouseType_JoyRight;
}
static Result hidSetMergedNmouseSourceTypes(int sources) { return !sources; }
static Result hidGetNmouseHandles(HidNmouseHandle *handles, s32 count, HidNpadIdType id, s32 *written) {
    assert(count == 2);
    if (id != 0 || !connected) {
        *written = 0;
        return 0;
    }
    handles[0] = 2;
    handles[1] = 4;
    *written = 2;
    return 0;
}
static Result hidGetNmouseTypeSet(HidNmouseHandle handle, u32 *type) {
    *type = handle;
    return 0;
}
static Result hidGetMergedNmouseHandle(HidNmouseHandle *handle) {
    *handle = 1;
    return !connected;
}
static Result hidGetNmouseStatesWithDelta(HidNmouseHandle handle,
    HidNmouseStateWithDelta *states, size_t count, size_t *written) {
    assert(count > 0);
    if (!connected) return 1;
    states[0] = (HidNmouseStateWithDelta){
        .sampling_number = 1, .delta_x = handle == 1 ? 4 : 0, .flags = tracking & handle ? BIT(1) : 0
    };
    *written = 1;
    return 0;
}
static void push_mouse_button(unsigned b, int down, uint32_t id) { (void)b; (void)down; (void)id; }
static void push_mouse_motion(int x, int y, uint32_t id) {
    assert(y == 0 && id == SWITCH2_NMOUSE_DEVICE_ID);
    total_x += x;
}
static void nmouse_reset_pointer(void) {
    struct switch2_nmouse_motion motion;
    switch2_nmouse_disconnect(&nmouse_processor, &motion);
    nmouse_has_handle = 0;
}
"""
        main = r"""
int main(void) {
    switch2_nmouse_processor_init(&nmouse_processor);
    nmouse_poll();
    assert(!nmouse_has_handle && total_x == 0);
    connected = 1;
    nmouse_poll();
    assert(nmouse_has_handle && total_x == 4);
    nmouse_poll();
    assert(total_x == 4);
    connected = 0;
    nmouse_poll();
    assert(!nmouse_has_handle);
    connected = 1;
    nmouse_poll();
    assert(nmouse_has_handle && total_x == 8);
    assert(switch2_nmouse_tracking_joycons(0) == 0);
    tracking = HidNmouseType_JoyRight;
    assert(switch2_nmouse_tracking_joycons(0) == SWITCH2_JOYCON_RIGHT);
    assert(switch2_nmouse_tracking_joycons(1) == 0);
    nmouse_mode = SWITCH2_NMOUSE_LEFT;
    assert(switch2_nmouse_tracking_joycons(0) == 0);
    tracking |= HidNmouseType_JoyLeft;
    assert(switch2_nmouse_tracking_joycons(0) == SWITCH2_JOYCON_LEFT);
    nmouse_mode = SWITCH2_NMOUSE_OFF;
    assert(switch2_nmouse_tracking_joycons(0) == 0);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            probe = pathlib.Path(tmp) / "probe.c"
            executable = probe.with_suffix("")
            probe.write_text(stub + poll + main)
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(host),
                 str(probe), str(host / "switch2_text_nmouse.c"), "-o", str(executable)],
                check=True,
            )
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
