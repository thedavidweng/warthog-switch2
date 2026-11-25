"""Host checks for the Switch 2 game-data preparation boundary."""

import ctypes
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

def image(path, offset=0):
    def table(entries):
        result = bytearray(2048)
        pos = 0
        for index, (name, sector, size, directory) in enumerate(entries):
            encoded = name.encode()
            next_pos = (pos + 14 + len(encoded) + 3) & ~3
            struct.pack_into("<HHIIBB", result, pos, 0,
                             next_pos // 4 if index + 1 < len(entries) else 0,
                             sector, size, 16 if directory else 0, len(encoded))
            result[pos + 14:pos + 14 + len(encoded)] = encoded
            pos = next_pos
        return result

    with path.open("wb") as f:
        def put(sector, data):
            f.seek(offset + sector * 2048)
            f.write(data)
        descriptor = bytearray(2048)
        descriptor[:20] = b"MICROSOFT*XBOX*MEDIA"
        struct.pack_into("<II", descriptor, 20, 33, 2048)
        put(32, descriptor)
        put(33, table([("maps", 34, 2048, True), ("bink", 35, 2048, True)]))
        put(34, table([("ui.map", 36, 2, False), ("bloodgulch.map", 37, 5, False)]))
        put(35, table([("intro.bik", 38, 3, False)]))
        put(36, b"ui")
        put(37, b"blood")
        put(38, b"bik")


class GameDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        library = Path(cls.build.name) / "gamedata.dylib"
        subprocess.run(
            ["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
             str(ROOT / "port/switch2/host/switch2_gamedata.c"),
             str(ROOT / "port/switch2/host/switch2_custom_edition.c"), "-o", str(library)],
            check=True,
        )
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.switch2_gamedata_prepare.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
        ]
        cls.lib.switch2_gamedata_prepare.restype = ctypes.c_int
        cls.lib.switch2_gamedata_prepare_limited.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
        ]
        cls.lib.switch2_gamedata_prepare_limited.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def test_missing_data_names_where_to_place_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "warthog"
            root.mkdir()
            message = ctypes.create_string_buffer(512)
            status = self.lib.switch2_gamedata_prepare(
                bytes(root), bytes(Path(directory) / "legacy"), 0, None, None,
                message, len(message),
            )
            self.assertEqual(status, 1)
            self.assertIn(b"maps", message.value)
            self.assertIn(b"disc image", message.value)

    def test_legacy_data_is_merged_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "warthog"
            legacy = Path(directory) / "legacy"
            (legacy / "maps").mkdir(parents=True)
            (legacy / "maps" / "UI.MAP").write_bytes(b"map")
            (legacy / "save").mkdir()
            (legacy / "save" / "old").write_bytes(b"save")
            (legacy / "config.toml").write_text("old")
            root.mkdir()
            (root / "config.toml").write_text("new")
            message = ctypes.create_string_buffer(512)
            status = self.lib.switch2_gamedata_prepare(
                bytes(root), bytes(legacy), 0, None, None, message, len(message))
            self.assertEqual(status, 0, message.value)
            self.assertEqual((root / "maps" / "UI.MAP").read_bytes(), b"map")
            self.assertEqual((root / "save" / "old").read_bytes(), b"save")
            self.assertEqual((root / "config.toml").read_text(), "new")
            self.assertEqual((legacy / "config.toml").read_text(), "old")
            self.assertTrue((root / "maps_ce").is_dir())
            self.assertFalse((root / "bink").exists())

    def test_extract_disc_images(self):
        for offset in (0, 0x18300000):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "warthog"
                root.mkdir()
                image(root / ("disc.iso" if offset else "disc.xiso"), offset)
                message = ctypes.create_string_buffer(512)
                events = []
                callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                                ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64)
                callback = callback_type(lambda ctx, i, n, path, done, total:
                                         events.append((i, n, done, total)))
                status = self.lib.switch2_gamedata_prepare(
                    bytes(root), bytes(Path(directory) / "legacy"), 0,
                    ctypes.cast(callback, ctypes.c_void_p), None, message, len(message))
                self.assertEqual(status, 0, message.value)
                self.assertEqual((root / "maps/ui.map").read_bytes(), b"ui")
                self.assertEqual((root / "maps/bloodgulch.map").read_bytes(), b"blood")
                self.assertEqual((root / "bink/intro.bik").read_bytes(), b"bik")
                self.assertTrue(events)
                self.assertEqual(events[-1][2], events[-1][3])
                self.assertEqual([e[2] for e in events], sorted(e[2] for e in events))

    def test_interrupted_copy_resumes_completed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "warthog"
            root.mkdir()
            image(root / "disc.xiso")
            legacy = bytes(Path(directory) / "legacy")
            message = ctypes.create_string_buffer(512)
            status = self.lib.switch2_gamedata_prepare_limited(
                bytes(root), legacy, 0, 3, None, None, message, len(message))
            self.assertNotEqual(status, 0)
            self.assertEqual((root / "maps.partial/ui.map").read_bytes(), b"ui")
            self.assertTrue((root / "maps.partial/bloodgulch.map.part").exists())
            self.assertFalse((root / "maps/ui.map").exists())
            saved = (root / "maps.partial/ui.map").stat().st_ino
            status = self.lib.switch2_gamedata_prepare(
                bytes(root), legacy, 0, None, None, message, len(message))
            self.assertEqual(status, 0, message.value)
            self.assertEqual((root / "maps/ui.map").stat().st_ino, saved)
            self.assertEqual((root / "maps/bloodgulch.map").read_bytes(), b"blood")
            self.assertFalse((root / "maps/bloodgulch.map.part").exists())

    def test_diagnostics_and_space_precheck(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "warthog"
            root.mkdir()
            legacy = bytes(Path(directory) / "legacy")
            message = ctypes.create_string_buffer(512)
            def prepare(free=0):
                return self.lib.switch2_gamedata_prepare(bytes(root), legacy, free, None, None,
                                                         message, len(message))
            (root / "maps").mkdir()
            self.assertEqual(prepare(), 2)
            self.assertIn(b"maps/ui.map", message.value)
            (root / "disc.iso").write_bytes(b"not a disc")
            self.assertEqual(prepare(), 3)
            self.assertIn(b"disc image", message.value)
            image(root / "disc.iso")
            self.assertEqual(prepare(1), 4)
            self.assertIn(b"MiB", message.value)
            self.assertFalse((root / "maps.partial").exists())

    def test_extract_merges_incomplete_maps_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "warthog"
            (root / "maps").mkdir(parents=True)
            (root / "maps/bloodgulch.map").write_bytes(b"existing")
            image(root / "disc.iso")
            message = ctypes.create_string_buffer(512)
            status = self.lib.switch2_gamedata_prepare(
                bytes(root), bytes(Path(directory) / "legacy"), 0, None, None, message, len(message))
            self.assertEqual(status, 0, message.value)
            self.assertEqual((root / "maps/bloodgulch.map").read_bytes(), b"existing")
            self.assertEqual((root / "maps/ui.map").read_bytes(), b"ui")
            self.assertFalse((root / "save").exists())
            self.assertTrue((root / "maps_ce").is_dir())
