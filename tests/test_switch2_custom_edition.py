import ctypes
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CustomEditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.library = Path(cls.tmp.name) / "custom_edition.dylib"
        subprocess.run(
            ["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
             str(ROOT / "port/switch2/host/switch2_custom_edition.c"), "-o", str(cls.library)],
            check=True,
        )
        cls.lib = ctypes.CDLL(str(cls.library))
        cls.lib.switch2_ce_validate_map.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_ce_validate_map.restype = ctypes.c_int
        cls.lib.switch2_ce_enumerate.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_ce_enumerate.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def write_map(self, path, version, magic=b"head", footer=b"foot", size=0x1000):
        data = bytearray(size)
        data[:4] = magic
        data[4:8] = version.to_bytes(4, "little")
        data[8:12] = size.to_bytes(4, "little")
        data[0x10:0x14] = (0x800).to_bytes(4, "little")
        data[0x14:0x18] = (0x20).to_bytes(4, "little")
        data[0x7FC:0x800] = footer
        path.write_bytes(data)

    def validate(self, path):
        version = ctypes.c_uint32()
        message = ctypes.create_string_buffer(256)
        result = self.lib.switch2_ce_validate_map(
            str(path).encode(), ctypes.byref(version), message, len(message))
        return result, version.value, message.value.decode()

    def test_supported_versions_and_both_layouts_enumerate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "switch" / "warthog"
            legacy = Path(temp) / "switch" / "ChupaThingyCE"
            (root / "maps_ce").mkdir(parents=True)
            (legacy / "maps_ce").mkdir(parents=True)
            self.write_map(root / "maps_ce" / "ce.map", 609)
            self.write_map(legacy / "maps_ce" / "pc.map", 7)
            message = ctypes.create_string_buffer(256)
            result = self.lib.switch2_ce_enumerate(
                str(root).encode(), str(legacy).encode(), None, None, message, len(message))
            self.assertEqual(result, 2)
            self.assertIn("Found 2", message.value.decode())

    def test_rejects_versions_and_corrupt_headers_with_specific_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cases = [(8, "version 8"), (13, "version 13"), (5, "version 5")]
            for version, text in cases:
                path = folder / f"{version}.map"
                self.write_map(path, version)
                result, _, message = self.validate(path)
                self.assertLess(result, 0)
                self.assertIn(text, message)
            bad = folder / "bad.map"
            self.write_map(bad, 609, magic=b"nope")
            self.assertIn("corrupt cache header", self.validate(bad)[2])
            short = folder / "short.map"
            short.write_bytes(b"head")
            self.assertIn("truncated", self.validate(short)[2])

    def test_build_and_address_window_guards(self):
        build = (ROOT / "port/switch2/engine_build.py").read_text()
        mman = (ROOT / "port/switch2/host/switch2_mman.h").read_text()
        self.assertIn("-DHALO_CUSTOM_EDITION", build)
        self.assertIn("SWITCH2_XBOX_WINDOW_LOW 0x40000000ULL", mman)
        self.assertLess(0x40440000, 0x40000000 + 0x60000000)
        self.assertIn("0x50000000", (ROOT / "port/switch2/overrides/port/linux/src/xbox_heap.c").read_text())

    def test_documentation_keeps_mcc_guard(self):
        readme = (ROOT / "README.md").read_text()
        investigation = (ROOT / "docs/mcc-investigation.md").read_text()
        self.assertIn("retail Xbox", readme)
        self.assertIn("MCC map support is not", readme)
        self.assertIn("Not yet supported", investigation)
        self.assertIn("version 13", investigation)
        self.assertIn("retail Xbox Halo: Combat Evolved", investigation)


if __name__ == "__main__":
    unittest.main()
