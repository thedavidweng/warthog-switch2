import unittest
import ctypes
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CertificateTests(unittest.TestCase):
    def test_seed_bundle_and_preserve_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            library = root / "certs.dylib"
            subprocess.run(["clang", "-std=c11", "-shared", "-fPIC",
                            str(ROOT / "port/switch2/host/switch2_certs.c"),
                            "-o", str(library)], check=True, capture_output=True)
            lib = ctypes.CDLL(str(library))
            lib.switch2_seed_certificates.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            self.assertEqual(1, lib.switch2_seed_certificates(str(root).encode(), b"root bundle\n"))
            cert = root / "cacert.pem"
            self.assertEqual(b"root bundle\n", cert.read_bytes())
            cert.write_bytes(b"custom roots\n")
            self.assertEqual(1, lib.switch2_seed_certificates(str(root).encode(), b"other\n"))
            self.assertEqual(b"custom roots\n", cert.read_bytes())
            self.assertFalse((root / "cacert.pem.part").exists())


class MapDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.library = root / "maps.dylib"
        subprocess.run(["clang", "-std=gnu11", "-shared", "-fPIC", "-pthread",
                        str(ROOT / "port/switch2/host/switch2_net_map.c"),
                        "-o", str(self.library)], check=True, capture_output=True)
        self.lib = ctypes.CDLL(str(self.library))
        self.lib.switch2_net_commit_downloaded_map.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        self.lib.switch2_net_commit_downloaded_map.restype = ctypes.c_int
        self.lib.switch2_net_cleanup_stale_map_parts.argtypes = [ctypes.c_char_p]
        self.lib.switch2_net_cleanup_stale_map_parts.restype = ctypes.c_int

    def tearDown(self):
        self.directory.cleanup()

    def test_valid_commit_and_non_clobber(self):
        root = Path(self.directory.name)
        part = root / "download.map.part"
        dest = root / "maps" / "test.map"
        dest.parent.mkdir()
        data = bytearray(2048)
        data[:4] = b"head"
        data[0x7fc:0x800] = b"foot"
        part.write_bytes(data)
        error = ctypes.create_string_buffer(256)
        self.assertEqual(1, self.lib.switch2_net_commit_downloaded_map(
            str(part).encode(), str(dest).encode(), error, len(error)))
        self.assertEqual(bytes(data), dest.read_bytes())
        part.write_bytes(data)
        original = dest.read_bytes()
        self.assertEqual(0, self.lib.switch2_net_commit_downloaded_map(
            str(part).encode(), str(dest).encode(), error, len(error)))
        self.assertEqual(original, dest.read_bytes())
        self.assertFalse(part.exists())

    def test_corrupt_and_truncated_parts_are_removed(self):
        root = Path(self.directory.name)
        dest = root / "existing.map"
        dest.write_bytes(b"keep")
        for data in (b"bad", b"head" + b"\0" * 10):
            part = root / "bad.map.part"
            part.write_bytes(data)
            error = ctypes.create_string_buffer(256)
            self.assertEqual(0, self.lib.switch2_net_commit_downloaded_map(
                str(part).encode(), str(dest).encode(), error, len(error)))
            self.assertFalse(part.exists())
            self.assertEqual(b"keep", dest.read_bytes())

    def test_cleanup_removes_only_staging_files(self):
        root = Path(self.directory.name)
        for folder in ("maps", "maps_ce"):
            path = root / folder
            path.mkdir()
            (path / "old.map.part").write_bytes(b"x")
            (path / "old.tmp").write_bytes(b"x")
            (path / "keep.map").write_bytes(b"map")
        self.assertEqual(1, self.lib.switch2_net_cleanup_stale_map_parts(str(root).encode()))
        for folder in ("maps", "maps_ce"):
            self.assertFalse((root / folder / "old.map.part").exists())
            self.assertFalse((root / folder / "old.tmp").exists())
            self.assertEqual(b"map", (root / folder / "keep.map").read_bytes())


class SocketLifecycleTests(unittest.TestCase):
    def test_network_and_tls_symbols_are_linked(self):
        elf = ROOT / "build/switch2/warthog.elf"
        if not elf.exists():
            self.skipTest("Switch 2 ELF is not built")
        symbols = subprocess.run(["nm", str(elf)], check=True, capture_output=True,
                                 text=True).stdout
        platform = ROOT / "build/switch2/libwarthog_platform.a"
        platform_symbols = subprocess.run(["nm", str(platform)], check=True,
                                          capture_output=True, text=True).stdout
        self.assertIn("posix_socket", symbols)
        self.assertIn("posix_upnp_forward_udp", symbols)
        self.assertIn("mbedtls_ssl_", platform_symbols)
        for name in ("net", "tls"):
            self.assertIn(f"host_{name}.o:", platform_symbols)
            self.assertNotIn(f"switch2_{name}.o:", platform_symbols)
        browser_source = (ROOT / "chupathingyce/port/linux/src/posix_browser.c").read_text()
        self.assertIn("posix_browser_request", browser_source)

    def test_socket_service_is_owned_by_application(self):
        main = (ROOT / "port/switch2/host/main.c").read_text()
        update = main[main.index("static int update_http("):main.index("extern const u8 __start__")]
        self.assertNotIn("socketInitialize", update)
        self.assertNotIn("socketExit", update)
        self.assertIn("socketInitialize(&sockets)", main)
        self.assertIn("sockets.num_bsd_sessions = 8", main)
        self.assertIn("sockets.sb_efficiency = 8", main)
        self.assertIn("sockets.tcp_tx_buf_max_size = 0x80000", main)
        self.assertIn("sockets.tcp_rx_buf_max_size = 0x80000", main)
        self.assertEqual(main.count("socketExit()"), 2)

    def test_browser_verifies_certificates_and_uses_switch_platform(self):
        browser = (ROOT / "chupathingyce/port/linux/src/posix_browser.c").read_text()
        build = (ROOT / "port/switch2/engine_build.py").read_text()
        self.assertIn("MBEDTLS_SSL_VERIFY_REQUIRED", browser)
        self.assertNotIn("MBEDTLS_SSL_VERIFY_NONE", browser)
        self.assertIn("-DHALO_DELTA_PLATFORM=_delta_platform_switch", build)
        self.assertIn("-D__ANDROID__=1", build)

    def test_public_host_cheats_are_gated_by_default(self):
        source = (ROOT / "chupathingyce/source/networking/network_game_globals.c").read_text()
        self.assertIn('!config_boolean("network.host_cheats") && p2p_hosting_public_game()', source)
        expressions = (ROOT / "chupathingyce/source/hs/hs.c").read_text()
        cheats = (ROOT / "chupathingyce/source/game/cheats.c").read_text()
        self.assertIn("network_game_host_cheats_refused() && !hs_expression_changes_no_game(expression)", expressions)
        self.assertIn("!network_game_host_cheats_refused()", cheats)

    def test_protocol_mismatch_reports_both_versions(self):
        source = (ROOT / "chupathingyce/source/networking/network_client_manager.c").read_text()
        self.assertIn("not joining a host of network version %u", source)
        self.assertIn("You are on network version %u. The host is on %u.", source)

    def test_risks_are_documented(self):
        docs = (ROOT / "docs/networking.md").read_text().lower()
        self.assertIn("enforcement", docs)
        self.assertIn("do not\nperform destructive testing against public servers", docs)
        self.assertNotIn("ban-free", docs)
