import unittest
import tempfile
import subprocess
import sys
import hashlib
import struct
import zipfile
import ctypes
import io
from pathlib import Path

from tools import switch2_audit
from tests.test_switch2_build import write_nro, write_elf, SWITCH2_MAP

ROOT = Path(__file__).resolve().parents[1]

class UpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        library = Path(cls.tmp.name) / "update.dylib"
        subprocess.run(["clang", "-std=c11", "-shared", "-fPIC",
                        str(ROOT / "port/switch2/host/switch2_update.c"),
                        str(ROOT / "chupathingyce/port/third_party/tomlc17/tomlc17.c"),
                        "-I", str(ROOT / "chupathingyce/port/third_party/tomlc17"),
                        "-o", str(library)], check=True, capture_output=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.switch2_update_asset_name.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.switch2_update_url_allowed.argtypes = [ctypes.c_char_p]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_asset_and_repository_restrictions(self):
        out = ctypes.create_string_buffer(80)
        self.assertTrue(self.lib.switch2_update_asset_name(b"release", out, len(out)))
        self.assertEqual(b"warthog-switch2-release.zip", out.value)
        self.assertFalse(self.lib.switch2_update_asset_name(b"other", out, len(out)))
        for url in (b"http://github.com/thedavidweng/warthog-switch2/releases/x",
                    b"https://github.com/ChupathingyCE/warthog-switch/releases/x",
                    b"https://github.com/thedavidweng/warthog-switch2/releases/halo-switch-release.zip"):
            self.assertFalse(self.lib.switch2_update_url_allowed(url))
        self.assertTrue(self.lib.switch2_update_url_allowed(
            b"https://github.com/thedavidweng/warthog-switch2/releases/download/build-1/warthog-switch2-release.zip"))

    def test_nro_requires_switch2_assets(self):
        self.lib.switch2_update_verify_nro.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "warthog.nro"
            write_nro(path)
            data = path.read_bytes()
            self.assertTrue(self.lib.switch2_update_verify_nro(data, len(data)))
            self.assertFalse(self.lib.switch2_update_verify_nro(data[:128], 128))
            self.assertFalse(self.lib.switch2_update_verify_nro(data.replace(b"OUN0", b"NRO0"), len(data)))

    def test_install_preserves_user_data_and_rejects_bad_entries(self):
        self.lib.switch2_update_apply_zip.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t,
                                                     ctypes.c_char_p, ctypes.c_size_t]
        self.lib.switch2_update_finish_pending.argtypes = [ctypes.c_char_p]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / "switch/warthog"
            app.mkdir(parents=True)
            for name in ("maps/ui.map", "maps_ce/test.map", "save/slot0", "config.toml"):
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"keep")
            nro = root / "valid.nro"
            write_nro(nro)
            def archive(extra=(), compression=zipfile.ZIP_STORED):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", compression) as z:
                    z.writestr("switch/warthog/warthog.nro", nro.read_bytes())
                    z.writestr("switch/warthog/menus/classic/main.xml", b"menu")
                    for name, contents in extra:
                        z.writestr("switch/warthog/" + name, contents)
                return buffer.getvalue()
            error = ctypes.create_string_buffer(256)
            def apply(data):
                return self.lib.switch2_update_apply_zip(str(app).encode(), data, len(data), error, len(error))
            for data in (archive([("config.toml", b"bad")]), archive([("save/x", b"bad")]),
                         archive([("../escape.xml", b"bad")]), archive([("menus/main.xml", b"bad")]),
                         archive(compression=zipfile.ZIP_DEFLATED)):
                self.assertFalse(apply(data))
            data = bytearray(archive())
            data[data.index(nro.read_bytes()) + 10] ^= 1
            self.assertFalse(apply(bytes(data)))
            for field in (10, 16, 20, 24, 46):
                data = bytearray(archive())
                central = data.index(b"PK\x01\x02")
                data[central + field] ^= 1
                self.assertFalse(apply(bytes(data)), field)
            data = bytearray(archive())
            data[-12] ^= 1
            self.assertFalse(apply(bytes(data)))
            self.assertTrue(apply(archive()), error.value)
            self.assertEqual(nro.read_bytes(), (app / "warthog.nro").read_bytes())
            self.assertTrue(self.lib.switch2_update_finish_pending(str(app).encode()))
            self.assertEqual(b"menu", (app / "menus/classic/main.xml").read_bytes())
            for name in ("maps/ui.map", "maps_ce/test.map", "save/slot0", "config.toml"):
                self.assertEqual(b"keep", (app / name).read_bytes())

    def test_interrupted_menu_swap(self):
        self.lib.switch2_update_finish_pending.argtypes = [ctypes.c_char_p]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "menus.old").mkdir()
            (root / "menus.old/old.xml").write_text("old")
            (root / "menus.new").mkdir()
            (root / "menus.new/new.xml").write_text("new")
            self.assertTrue(self.lib.switch2_update_finish_pending(str(root).encode()))
            self.assertEqual("new", (root / "menus/new.xml").read_text())
            self.assertFalse((root / "menus.old").exists())

    def test_update_check(self):
        callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p, ctypes.c_size_t)
        self.lib.switch2_update_check.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, callback_type,
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        libc = ctypes.CDLL(None)
        libc.malloc.argtypes = [ctypes.c_size_t]
        libc.malloc.restype = ctypes.c_void_p
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nro = root / "valid.nro"
            write_nro(nro)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as z:
                z.writestr("switch/warthog/warthog.nro", nro.read_bytes())
                z.writestr("switch/warthog/menus/classic/main.xml", b"new")
            payload = stream.getvalue()
            for name in ("maps/ui.map", "save/slot0"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"keep")
            config = root / "config.toml"
            calls = []
            target = [b"https://github.com/thedavidweng/warthog-switch2/releases/tag/build-2"]
            @callback_type
            def http(_ctx, url, follow, out, size, location, loc_size):
                calls.append((url, follow))
                if not follow:
                    ctypes.memmove(location, target[0] + b"\0", len(target[0]) + 1)
                    return 302
                ptr = libc.malloc(len(payload))
                ctypes.memmove(ptr, payload, len(payload))
                out[0], size[0] = ptr, len(payload)
                return 200
            error = ctypes.create_string_buffer(256)
            def check(build):
                return self.lib.switch2_update_check(str(root).encode(), b"release", build,
                                                      http, None, error, len(error))
            config.write_text("[update]\nauto = false\n")
            self.assertEqual(0, check(1))
            config.write_text("update = { auto = false }\n")
            self.assertEqual(0, check(1))
            config.write_text("[update]\nauto = true\n")
            self.assertEqual(0, check(0))
            self.assertEqual([], calls)
            self.assertEqual(0, check(2))
            target[0] = b"https://github.com/ChupathingyCE/warthog-switch/releases/tag/build-3"
            self.assertEqual(-1, check(1))
            target[0] = b"https://github.com/thedavidweng/warthog-switch2/releases/tag/build-3"
            self.assertEqual(1, check(2), error.value)
            self.assertEqual(nro.read_bytes(), (root / "warthog.nro").read_bytes())
            self.assertEqual(b"new", (root / "menus.new/classic/main.xml").read_bytes())
            self.assertEqual(b"keep", (root / "maps/ui.map").read_bytes())
            self.assertEqual(b"keep", (root / "save/slot0").read_bytes())
            self.assertEqual("[update]\nauto = true\n", config.read_text())
            self.assertEqual(1, sum(follow for _, follow in calls))


class ReleaseAuditTests(unittest.TestCase):
    def test_workflow_publishes_both_switch2_flavors_and_symbols(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        self.assertIn("  switch2:\n", workflow)
        self.assertIn("needs: [switch, switch2]", workflow)
        self.assertIn("tools/switch2_audit.py --package", workflow)
        self.assertIn("SHA256SUMS.txt", workflow)

    def test_symbol_archive_matches_flavor_and_embedded_nacp(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / "card/switch/warthog"
            app.mkdir(parents=True)
            nro = app / "warthog.nro"
            write_nro(nro)
            elf = root / "warthog.elf"
            write_elf(elf)
            data = nro.read_bytes()
            size = struct.unpack_from("<I", data, 0x18)[0]
            offset, length = struct.unpack_from("<QQ", data, size + 24)
            nacp = data[size + offset:size + offset + length]
            symbols = root / "symbols.zip"
            def make_symbols(map_text, nacp_data):
                with zipfile.ZipFile(symbols, "w") as archive:
                    archive.write(elf, "warthog.elf")
                    archive.writestr("warthog.elf.map", map_text)
                    archive.writestr("warthog.nacp", nacp_data)
            make_symbols(SWITCH2_MAP, nacp)
            baseline = switch2_audit.audit_package(root / "card")
            self.assertEqual(baseline, switch2_audit.audit_package(root / "card", "release", symbols))
            self.assertGreater(len(switch2_audit.audit_package(root / "card", "debug", symbols)), len(baseline))
            make_symbols(SWITCH2_MAP, bytes(len(nacp)))
            self.assertGreater(len(switch2_audit.audit_package(root / "card", "release", symbols)), len(baseline))

    def test_package_produces_notices_and_release_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            build = root / "build/switch2"
            (build / "menus").mkdir(parents=True)
            write_nro(build / "warthog.nro")
            write_elf(build / "warthog.elf")
            (build / "warthog.elf.map").write_text(SWITCH2_MAP)
            data = (build / "warthog.nro").read_bytes()
            size = struct.unpack_from("<I", data, 0x18)[0]
            offset, length = struct.unpack_from("<QQ", data, size + 24)
            (build / "warthog.nacp").write_bytes(data[size + offset:size + offset + length])
            (build / "menus/menu.xml").write_text("<menu/>")
            result = subprocess.run([sys.executable, str(ROOT / "tools/switch_package.py"),
                                     "--target", "switch2", "--out", str(root / "card"),
                                     "--release-dir", str(root / "release"), "--flavor", "release"],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / "card/switch/warthog/THIRD-PARTY-NOTICES.txt").is_file())
            notices = (root / "card/switch/warthog/THIRD-PARTY-NOTICES.txt").read_text()
            for text in ("Copyright (C) 2018-2020 fincs",
                         "Copyright (C) 2026 PalindromicBreadLoaf",
                         "Copyright 2017-2018 libnx Authors",
                         "Permission to use, copy, modify, and/or distribute this software",
                         "Permission is hereby granted, free of charge",
                         "The origin of this software must not be misrepresented"):
                self.assertIn(text, notices)
            for name in ("expat/COPYING", "mbedtls/LICENSE", "musl-math/COPYRIGHT"):
                text = (ROOT / "chupathingyce/port/third_party" / name).read_text()
                self.assertIn(text, notices)
            self.assertTrue((root / "release/warthog-switch2-release.zip").is_file())
            self.assertTrue((root / "release/warthog-switch2-release-symbols.zip").is_file())
            self.assertTrue((root / "release/SHA256SUMS.txt").is_file())
            (build / "warthog.elf.map").write_text(SWITCH2_MAP.replace("libdrako3d.a", "libdrako3dd.a"))
            bad = subprocess.run([sys.executable, str(ROOT / "tools/switch_package.py"),
                                  "--target", "switch2", "--out", str(root / "bad-card"),
                                  "--release-dir", str(root / "bad-release"), "--flavor", "release"],
                                 cwd=root, capture_output=True, text=True)
            self.assertNotEqual(0, bad.returncode)
            self.assertFalse((root / "bad-release/SHA256SUMS.txt").exists())
            archive_path = root / "release/warthog-switch2-release.zip"
            self.assertEqual([], switch2_audit.audit_package(root / "card"))
            self.assertEqual([], switch2_audit.audit_package(archive_path))
            app = root / "card/switch/warthog"
            for forbidden in ("ui.map", "disc.iso", "loading.tga", "maxwell.dksh"):
                injected = app / forbidden
                injected.write_bytes(b"data")
                self.assertTrue(switch2_audit.audit_package(root / "card"), forbidden)
                injected.unlink()
            write_nro(app / "warthog.nro", magic=b"NRO0")
            self.assertTrue(switch2_audit.audit_package(root / "card"))
            with zipfile.ZipFile(archive_path) as archive:
                self.assertTrue(all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist()))
                self.assertIn("switch/warthog/menus/menu.xml", archive.namelist())
            with zipfile.ZipFile(root / "release/warthog-switch2-release-symbols.zip") as archive:
                self.assertEqual({"warthog.elf", "warthog.elf.map", "warthog.nacp"}, set(archive.namelist()))
            for line in (root / "release/SHA256SUMS.txt").read_text().splitlines():
                digest, filename = line.split("  ")
                self.assertEqual(digest, hashlib.sha256((root / "release" / filename).read_bytes()).hexdigest())
            deflated = root / "deflated.zip"
            with zipfile.ZipFile(archive_path) as original, zipfile.ZipFile(deflated, "w", zipfile.ZIP_DEFLATED) as output:
                for name in original.namelist():
                    output.writestr(name, original.read(name))
            self.assertTrue(switch2_audit.audit_package(deflated))

    def test_flavor_requires_matching_renderer(self):
        debug = "libounce.a libdrako3dd.a libuam2rt.a"
        release = "libounce.a libdrako3d.a libuam2rt.a"
        self.assertEqual([], switch2_audit.map_problems(debug, "debug"))
        self.assertEqual([], switch2_audit.map_problems(release, "release"))
        self.assertTrue(switch2_audit.map_problems(debug, "release"))
        self.assertTrue(switch2_audit.map_problems(release, "debug"))

    def test_package_rejects_forbidden_files_and_missing_notices(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / "switch/warthog"
            app.mkdir(parents=True)
            (app / "ui.map").write_bytes(b"game data")
            problems = switch2_audit.audit_package(root)
            self.assertTrue(any("ui.map" in problem for problem in problems))
            self.assertTrue(any("THIRD-PARTY-NOTICES.txt" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
