"""The Switch 2 development loop (ticket #4): package, deploy, logs, symbols.

Run with: python3 -m unittest discover -s tests

The tools are exercised the way a developer uses them: as commands, against a
real FTP server that happens to be a Python one on the loopback interface, and
against an ELF the test writes. Nothing here needs a console.

The FTP server is here rather than a mock library because the tools speak
FTP: a stand-in that answered at the ftplib level would not prove that the
console's commands (MKD, STOR, SIZE, RETR, NLST, DELE) are the ones sent.
"""

import os
import socket
import socketserver
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tools" / "switch_package.py"
DEPLOY = ROOT / "tools" / "switch_deploy.py"
LOGS = ROOT / "tools" / "switch_logs.py"
SYMBOLS = LOGS

sys.path.insert(0, str(ROOT / "tools"))


def run(tool, *arguments, env=None, cwd=ROOT):
    """a tool run as a developer runs it, with the console's address unset"""
    environment = {name: value for name, value in os.environ.items()
                   if not name.startswith("WARTHOG_SWITCH2_")}
    environment.update(env or {})
    return subprocess.run([sys.executable, str(tool), *arguments], cwd=cwd,
                          capture_output=True, text=True, env=environment)


class MockFtp:
    """A small FTP server over a dict, for the commands the tools send.

    USER/PASS always succeed (the console's server is anonymous), CWD and
    MKD are checked against the directories it holds, and STOR, RETR, SIZE,
    NLST and DELE work on the files. PASV is the only transfer mode, which is
    what ftplib asks for.
    """

    def __init__(self, files=None, directories=("/", "/switch")):
        self.files = dict(files or {})
        self.directories = set(directories)
        self.commands = []
        self.deleted = []
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), self.handler())
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    # ---------- lifecycle

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exception):
        self.server.shutdown()
        self.server.server_close()

    @property
    def port(self):
        return self.server.server_address[1]

    def path(self, name):
        return "/switch/warthog/" + name

    # ---------- the protocol

    def handler(self):
        server = self

        class Handler(socketserver.StreamRequestHandler):
            def setup(self):
                super().setup()
                self.cwd = "/"
                self.passive = None

            def reply(self, line):
                self.wfile.write(line.encode() + b"\r\n")
                self.wfile.flush()

            def absolute(self, name):
                if name.startswith("/"):
                    return name.rstrip("/") or "/"
                joined = self.cwd.rstrip("/") + "/" + name
                return joined.rstrip("/") or "/"

            def handle(self):
                self.reply("220 mock ftp ready")
                while True:
                    line = self.rfile.readline()
                    if not line:
                        return
                    text = line.decode("utf-8", "replace").rstrip("\r\n")
                    server.commands.append(text)
                    verb, _, argument = text.partition(" ")
                    verb = verb.upper()
                    if verb == "USER":
                        self.reply("331 password required")
                    elif verb == "PASS":
                        self.reply("230 logged in")
                    elif verb in ("TYPE", "NOOP", "OPTS"):
                        self.reply("200 ok")
                    elif verb == "PWD":
                        self.reply('257 "%s"' % self.cwd)
                    elif verb == "CWD":
                        target = self.absolute(argument)
                        if target in server.directories:
                            self.cwd = target
                            self.reply("250 changed")
                        else:
                            self.reply("550 no such directory")
                    elif verb == "MKD":
                        target = self.absolute(argument)
                        if target in server.directories:
                            self.reply("550 already there")
                        else:
                            server.directories.add(target)
                            self.reply('257 "%s" created' % target)
                    elif verb == "SIZE":
                        target = self.absolute(argument)
                        if target in server.files:
                            self.reply("213 %d" % len(server.files[target]))
                        else:
                            self.reply("550 no such file")
                    elif verb == "DELE":
                        target = self.absolute(argument)
                        if target in server.files:
                            del server.files[target]
                            server.deleted.append(target)
                            self.reply("250 deleted")
                        else:
                            self.reply("550 no such file")
                    elif verb == "PASV":
                        self.open_passive()
                    elif verb in ("STOR", "RETR", "NLST", "LIST"):
                        self.transfer(verb, argument)
                    elif verb == "QUIT":
                        self.reply("221 bye")
                        return
                    else:
                        self.reply("502 not implemented")

            def open_passive(self):
                self.close_passive()
                self.passive = socket.socket()
                self.passive.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.passive.bind(("127.0.0.1", 0))
                self.passive.listen(1)
                port = self.passive.getsockname()[1]
                self.reply("227 Entering Passive Mode (127,0,0,1,%d,%d)" % (port >> 8, port & 0xFF))

            def close_passive(self):
                if self.passive:
                    self.passive.close()
                    self.passive = None

            def transfer(self, verb, argument):
                if not self.passive:
                    self.reply("425 use PASV")
                    return
                target = self.absolute(argument)
                if verb == "STOR":
                    if self.absolute("/").rstrip("/") or True:
                        parent = target.rsplit("/", 1)[0] or "/"
                        if parent not in server.directories:
                            self.reply("550 no such directory")
                            self.close_passive()
                            return
                    self.reply("150 ready")
                    connection, _ = self.passive.accept()
                    server.files[target] = b""
                    with connection:
                        while True:
                            chunk = connection.recv(65536)
                            if not chunk:
                                break
                            server.files[target] += chunk
                elif verb == "RETR":
                    if target not in server.files:
                        self.reply("550 no such file")
                        self.close_passive()
                        return
                    self.reply("150 sending")
                    connection, _ = self.passive.accept()
                    with connection:
                        connection.sendall(server.files[target])
                else:
                    if target not in server.directories:
                        self.reply("550 no such directory")
                        self.close_passive()
                        return
                    self.reply("150 listing")
                    connection, _ = self.passive.accept()
                    prefix = target.rstrip("/") + "/"
                    names = sorted(path[len(prefix):] for path in
                                   list(server.files) + list(server.directories)
                                   if path.startswith(prefix) and "/" not in path[len(prefix):]
                                   and path != target)
                    with connection:
                        connection.sendall("".join(name + "\r\n" for name in names).encode())
                self.close_passive()
                self.reply("226 transfer complete")

        return Handler


class LogsTest(unittest.TestCase):
    def setUp(self):
        self.logs = tempfile.TemporaryDirectory()
        self.addCleanup(self.logs.cleanup)

    def run_logs(self, *arguments):
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith("WARTHOG_SWITCH2_")}
        program = ("import sys; from pathlib import Path; "
                   "sys.path.insert(0, sys.argv[1]); import switch_logs; "
                   "switch_logs.SWITCH2_LOCAL = Path(sys.argv[2]); "
                   "switch_logs.main(sys.argv[3:])")
        return subprocess.run([sys.executable, "-c", program, str(ROOT / "tools"),
                               self.logs.name, *arguments], cwd=ROOT, env=environment,
                              capture_output=True, text=True)

    def test_fetches_and_classifies_latest_run(self):
        log = (b"--- launch ---\nfirmware: 20.0\nlaunch context: AppletType Application\n"
               b"renderer: Drako3D\nuam2rt: ready\nWarthog for Switch 2 1 (debug build)\n"
               b"FAULT_KIND: CPU_EXCEPTION\n")
        folder = "/switch/warthog/logs"
        with MockFtp({folder + "/warthog.log": log, folder + "/ram_probe.log": b"probe"},
                     directories=("/", "/switch", "/switch/warthog", folder)) as ftp:
            result = self.run_logs("--target", "switch2", "--host", "127.0.0.1", "--port", str(ftp.port))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for item in ("CPU_EXCEPTION", "20.0", "AppletType", "Drako3D", "uam2rt"):
                self.assertIn(item, result.stdout)
            self.assertEqual(b"probe", (Path(self.logs.name) / "ram_probe.log").read_bytes())

    def test_gpu_fault_and_clean_exit_are_distinct(self):
        folder = "/switch/warthog/logs"
        for content, expected in ((b"FAULT_KIND: GPU_FAULT\n", "GPU_FAULT"),
                                  (b"FAULT_KIND: DIAG_ABORT\nresult: 0x1a80a\n", "DIAG_ABORT"),
                                  (b"FAULT_KIND: C_ABORT\n", "C_ABORT"),
                                  (b"startup complete; returning to the homebrew menu\n", "clean exit")):
            with self.subTest(expected=expected), MockFtp(
                {folder + "/warthog.log": b"--- launch ---\n" + content},
                directories=("/", "/switch", "/switch/warthog", folder)) as ftp:
                result = self.run_logs("--target", "switch2", "--host", "127.0.0.1", "--port", str(ftp.port))
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(expected, result.stdout)

    def test_symbolizes_synthetic_elf_without_toolchain(self):
        # ELF64 with a string table and one function symbol at 0x100.
        with tempfile.TemporaryDirectory() as directory:
            elf = Path(directory) / "test.elf"
            data = bytearray(64 + 3 * 64 + 16 + 48)
            data[:6] = b"\x7fELF\x02\x01"
            struct.pack_into("<Q", data, 40, 64)
            struct.pack_into("<HH", data, 58, 64, 3)
            struct.pack_into("<IIQQQQIIQQ", data, 128, 0, 3, 0, 0, 256, 16, 0, 0, 1, 0)
            struct.pack_into("<IIQQQQIIQQ", data, 192, 0, 2, 0, 0, 272, 48, 1, 1, 8, 24)
            data[256:262] = b"\0test\0"
            struct.pack_into("<IBBHQQ", data, 296, 1, 0x12, 0, 1, 0x100, 0x20)
            elf.write_bytes(data)
            import switch_logs
            with mock.patch.object(switch_logs.shutil, "which", return_value=None):
                self.assertEqual({0x104: "test+0x4"}, switch_logs.symbolize(elf, [0x104]))

    def test_real_elf_resolves_fault_function_to_source(self):
        import switch_logs
        elf = ROOT / "build/switch2/warthog.elf"
        if not elf.is_file() or not (shutil.which("aarch64-none-elf-addr2line") or shutil.which("docker")):
            self.skipTest("requires the Switch 2 ELF and addr2line toolchain")
        symbols = switch_logs.elf_symbols(elf)
        address = next(value for value, _, name in symbols if name == "warthog_deliberate_test_fault")
        folder = "/switch/warthog/logs"
        log = ("--- launch ---\nFAULT_KIND: CPU_EXCEPTION\nFRAME #00: 0x1 "
               "(warthog.elf+0x%x)\n" % address).encode()
        with MockFtp({folder + "/warthog.log": log},
                     directories=("/", "/switch", "/switch/warthog", folder)) as ftp:
            result = self.run_logs("--target", "switch2", "--host", "127.0.0.1",
                                   "--port", str(ftp.port), "--elf", str(elf))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("warthog_deliberate_test_fault", result.stdout)
            self.assertIn("main.c:", result.stdout)


class PackageTest(unittest.TestCase):
    """tools/switch_package.py lays out the card for the target it is given."""

    def test_switch2_package_prefers_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            build = repo / "build/switch2"
            build.mkdir(parents=True)
            (build / "warthog.nro").write_bytes(b"local nro")
            menus = build / "menus"
            menus.mkdir()
            (menus / "local.xml").write_text("local menu")
            brokers = repo / "chupathingyce/port/assets/network"
            brokers.mkdir(parents=True)
            (brokers / "brokers.txt").write_text("local broker")
            out = repo / "out"
            result = run(PACKAGE, "--target", "switch2", "--out", str(out), cwd=repo)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            card = out / "switch/warthog"
            self.assertEqual(b"local nro", (card / "warthog.nro").read_bytes())
            self.assertEqual("local broker", (card / "brokers.txt").read_text())
            self.assertEqual("local menu", (card / "menus/local.xml").read_text())

    def test_switch2_package_lays_out_the_warthog_card_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            nro = Path(directory) / "warthog.nro"
            nro.write_bytes(b"HOMEBREWNRO0" + bytes(64))
            out = Path(directory) / "out"
            result = run(PACKAGE, "--target", "switch2", "--nro", str(nro), "--out", str(out))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            card = out / "switch" / "warthog"
            self.assertEqual(nro.read_bytes(), (card / "warthog.nro").read_bytes())
            # a Switch 2 program is the whole game: no guest image, and the
            # maps are the player's rather than the build's
            for absent in ("halo_guest.elf", "warthog.elf", "maps"):
                with self.subTest(absent=absent):
                    self.assertFalse((card / absent).exists())

    def test_switch2_package_refuses_a_build_that_is_not_there(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(PACKAGE, "--target", "switch2", "--nro", str(Path(directory) / "none.nro"),
                         "--out", str(Path(directory) / "out"))
            self.assertEqual(1, result.returncode)
            self.assertIn("run ninja switch2 first", result.stderr)


class DeployTest(unittest.TestCase):
    """tools/switch_deploy.py puts the Switch 2 build on the card."""

    def repo(self):
        """a temporary repository with a Switch 2 build in it"""
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(directory)], check=False))
        build = directory / "build" / "switch2"
        build.mkdir(parents=True)
        (build / "warthog.nro").write_bytes(b"HOMEBREWNRO0" + bytes(128))
        return directory

    def test_switch2_without_an_address_says_how_to_give_one(self):
        result = run(DEPLOY, "--target", "switch2", cwd=self.repo())
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--host", result.stderr)
        self.assertIn("WARTHOG_SWITCH2_HOST", result.stderr)

    def test_switch2_uploads_the_program_and_makes_the_card_folders(self):
        with MockFtp() as ftp:
            result = run(DEPLOY, "--target", "switch2", cwd=self.repo(),
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": str(ftp.port)})
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"HOMEBREWNRO0" + bytes(128), ftp.files["/switch/warthog/warthog.nro"])
            # the card folders the destination needs were made, not assumed
            self.assertIn("/switch/warthog", ftp.directories)

    def test_the_command_line_address_wins_over_the_environment(self):
        with MockFtp() as ftp:
            result = run(DEPLOY, "--target", "switch2", "--host", "127.0.0.1",
                         "--port", str(ftp.port), cwd=self.repo(),
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": "1"})
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("/switch/warthog/warthog.nro", ftp.files)

    def test_switch2_uploads_the_broker_list_when_the_build_has_one(self):
        repo = self.repo()
        brokers = repo / "chupathingyce" / "port" / "assets" / "network"
        brokers.mkdir(parents=True)
        (brokers / "brokers.txt").write_text("broker\n")
        with MockFtp() as ftp:
            result = run(DEPLOY, "--target", "switch2", cwd=repo,
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": str(ftp.port)})
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"broker\n", ftp.files["/switch/warthog/brokers.txt"])

    def test_build_configures_builds_packages_and_uploads(self):
        repo = self.repo()
        script = repo / "scripts/switch2/build.sh"
        script.parent.mkdir(parents=True)
        script.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\" >> build-steps\n")
        script.chmod(0o755)
        with MockFtp() as ftp:
            result = run(DEPLOY, "--target", "switch2", "--build", cwd=repo,
                         env={"WARTHOG_SWITCH2_HOST": "127.0.0.1",
                              "WARTHOG_SWITCH2_PORT": str(ftp.port)})
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("configure\nbuild\n", (repo / "build-steps").read_text())
            packaged = repo / "build/switch2/package/switch/warthog/warthog.nro"
            self.assertEqual(packaged.read_bytes(), ftp.files["/switch/warthog/warthog.nro"])

    def test_remote_size_falls_back_to_list_when_ftp_size_returns_zero(self):
        import switch_deploy

        class FakeFtp:
            def __init__(self, lines):
                self._lines = lines

            def size(self, name):
                return 0

            def retrlines(self, cmd, callback):
                self.last_cmd = cmd
                for line in self._lines:
                    callback(line)

        exact = FakeFtp(["-rw-r--r-- 1 switch switch 1234 Nov 26 01:41 warthog.nro"])
        self.assertEqual(1234, switch_deploy._remote_size(exact, "warthog.nro", 1234))
        self.assertEqual("LIST", exact.last_cmd)

        truncated = FakeFtp(["-rw-r--r-- 1 switch switch 500 Nov 26 01:41 warthog.nro"])
        self.assertEqual(500, switch_deploy._remote_size(truncated, "warthog.nro", 1234))


if __name__ == "__main__":
    unittest.main()
