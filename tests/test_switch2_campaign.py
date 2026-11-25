import ctypes
import pathlib
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class CampaignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        library = pathlib.Path(cls.directory.name) / "campaign.dylib"
        subprocess.run(["cc", "-shared", "-fPIC", "-o", str(library),
                        str(ROOT / "port/switch2/host/switch2_campaign.c")], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.switch2_campaign_mission_id.argtypes = [ctypes.c_size_t]
        cls.lib.switch2_campaign_mission_id.restype = ctypes.c_char_p
        cls.lib.switch2_campaign_validate_map.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_campaign_validate_map.restype = ctypes.c_int
        cls.lib.switch2_campaign_validate_resource.argtypes = [
            ctypes.c_char_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_campaign_validate_resource.restype = ctypes.c_int
        cls.lib.switch2_campaign_write_atomic.argtypes = [
            ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.switch2_campaign_write_atomic.restype = ctypes.c_int
        cls.lib.switch2_campaign_cleanup_stale_part.argtypes = [ctypes.c_char_p]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_campaign_missions(self):
        self.assertEqual(
            [self.lib.switch2_campaign_mission_id(i).decode() for i in range(10)],
            ["a10", "a30", "a50", "b30", "b40", "c10", "c20", "c40", "d20", "d40"])
        self.assertIsNone(self.lib.switch2_campaign_mission_id(10))

    def test_atomic_write_and_interrupted_recovery(self):
        path = pathlib.Path(self.directory.name) / "savegame.bin"
        part = pathlib.Path(str(path) + ".part")
        path.write_bytes(b"previous checkpoint")
        part.write_bytes(b"interrupted")
        self.lib.switch2_campaign_cleanup_stale_part(bytes(path))
        self.assertEqual(path.read_bytes(), b"previous checkpoint")
        self.assertFalse(part.exists())
        data = ctypes.create_string_buffer(b"new checkpoint")
        self.assertTrue(self.lib.switch2_campaign_write_atomic(
            bytes(path), data, len(data) - 1))
        self.assertEqual(path.read_bytes(), b"new checkpoint")
        self.assertFalse(part.exists())

    def test_atomic_write_failure_preserves_destination(self):
        path = pathlib.Path(self.directory.name) / "profile"
        path.write_bytes(b"old profile")
        part = pathlib.Path(str(path) + ".part")
        part.mkdir()
        try:
            data = ctypes.create_string_buffer(b"new profile")
            self.assertFalse(self.lib.switch2_campaign_write_atomic(
                bytes(path), data, len(data) - 1))
            self.assertEqual(path.read_bytes(), b"old profile")
        finally:
            part.rmdir()

    def test_host_relocates_pool_and_cache_pointers(self):
        source = pathlib.Path(self.directory.name) / "relocate.c"
        program = pathlib.Path(self.directory.name) / "relocate"
        source.write_text(r'''
#include "switch2_campaign.h"
#include <stdint.h>
#include <stdlib.h>
int main(void) {
    unsigned char *a = calloc(1, 4096), *b = calloc(1, 4096);
    void *base = a + 64, *first = a + 128, *last = a + 256;
    void *refs[1] = { a + 512 }, *targets[1] = { a + 640 };
    void *next[1] = { 0 }, *previous[1] = { 0 }, *blocks = a + 768;
    struct switch2_campaign_pool_relocation pool = {
        &base, &first, &last, refs, targets, next, previous, 1
    };
    struct switch2_campaign_cache_relocation cache = { &blocks };
    int ok = switch2_campaign_relocate_native_pointers(
        a, b, 4096, &pool, 1, &cache, 1);
    ok = ok && base == b + 64 && first == b + 128 && last == b + 256;
    ok = ok && refs[0] == b + 512 && targets[0] == b + 640;
    ok = ok && blocks == b + 768;
    free(a); free(b);
    return ok ? 0 : 1;
}
''')
        subprocess.run(["cc", "-I", str(ROOT / "port/switch2/host"),
                        "-o", str(program), str(source),
                        str(ROOT / "port/switch2/host/switch2_campaign.c")],
                       check=True)
        subprocess.run([str(program)], check=True)

    def test_missing_map_reports_error(self):
        message = ctypes.create_string_buffer(256)
        path = pathlib.Path(self.directory.name) / "absent.map"
        self.assertFalse(self.lib.switch2_campaign_validate_map(
            str(path).encode(), message, len(message)))
        self.assertIn("absent.map", message.value.decode())
        self.assertIn("open", message.value.decode())

    def test_scenario_header_validation(self):
        path = pathlib.Path(self.directory.name) / "scenario.map"
        header = bytearray(2048)
        header[:4] = b"daeh"
        struct.pack_into("<II", header, 4, 5, len(header))
        header[-4:] = b"toof"
        message = ctypes.create_string_buffer(256)
        def validate():
            return self.lib.switch2_campaign_validate_map(
                str(path).encode(), message, len(message))
        path.write_bytes(header)
        self.assertTrue(validate())
        for content, expected in [
            (header[:32], "truncated"),
            (b"xxxx" + header[4:], "header"),
            (header[:-4] + b"xxxx", "footer"),
            (header[:4] + struct.pack("<I", 999) + header[8:], "version"),
            (header[:8] + struct.pack("<I", 4096) + header[12:], "truncated"),
        ]:
            path.write_bytes(content)
            self.assertFalse(validate())
            self.assertIn(expected, message.value.decode())

    def test_resource_cache_header(self):
        path = pathlib.Path(self.directory.name) / "bitmaps.map"
        message = ctypes.create_string_buffer(256)
        def validate():
            return self.lib.switch2_campaign_validate_resource(
                str(path).encode(), 1, message, len(message))
        path.write_bytes(struct.pack("<IIII", 1, 16, 16, 1) + bytes(12))
        self.assertTrue(validate())
        path.write_bytes(struct.pack("<IIII", 2, 16, 16, 1) + bytes(12))
        self.assertFalse(validate())
        self.assertIn("type", message.value.decode())
        path.write_bytes(struct.pack("<IIII", 1, 16, 16, 2) + bytes(12))
        self.assertFalse(validate())
        self.assertIn("table", message.value.decode())
