import unittest
import tempfile
import subprocess
import sys
import hashlib
import struct
import zipfile
from pathlib import Path

from tools import switch2_audit
from tests.test_switch2_build import write_nro, write_elf, SWITCH2_MAP

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAuditTests(unittest.TestCase):
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
