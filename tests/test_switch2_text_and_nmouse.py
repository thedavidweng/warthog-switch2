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


if __name__ == "__main__":
    unittest.main()
