"""The Switch 2 build graph and artifact audit (ticket #3).

Run with: python3 -m unittest discover -s tests

Every expectation here comes from the ticket's acceptance criteria rather than
from the files under test: a Switch 2 NRO with valid NACP metadata, a linker
map that shows Switch 2 linkage only, a pinned toolchain, and the original
Switch target still configuring.

The artifacts the audit reads are synthesized here rather than built: the
toolchain image is not needed to check that the audit notices a Maxwell NRO,
a missing symbol table or an original-Switch library in the map.
"""

import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "chupathingyce"
CONFIGURE = GAME / "configure.py"
UPSTREAM = ROOT / "UPSTREAM.json"
DOCKERFILE = ROOT / "scripts" / "switch2" / "Dockerfile"
AUDIT = ROOT / "tools" / "switch2_audit.py"
BUILD_SCRIPT = ROOT / "scripts" / "switch2" / "build.sh"

sys.path.insert(0, str(ROOT / "tools"))

NACP_TITLE = "Warthog"
NACP_AUTHOR = "thedavidweng, ChupathingyCE contributors"
NACP_VERSION = json.loads(UPSTREAM.read_text(encoding="utf-8"))["switch2_version"]

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 16 + b"\xff\xd9"


def write_elf(path, sections=(".debug_info", ".symtab"), oun0=True):
    """An ELF64 little-endian AArch64 file whose section names are `sections`."""
    names = ["", ".shstrtab"] + [name for name in sections if name != ".shstrtab"]
    table = b""
    offsets = {}
    for name in names:
        offsets[name] = len(table)
        table += name.encode() + b"\x00"
    headers = [bytes(64)]  # the null section
    data_offset = 0x100
    payload = b""
    for index, name in enumerate(names[1:], start=1):
        content = b""
        if name == ".shstrtab":
            content = table
        elif name == ".crt0" and oun0:
            content = b"OUN0" + bytes(60)
        headers.append(struct.pack(
            "<IIQQQQIIQQ",
            offsets[name],            # sh_name
            3 if name == ".shstrtab" else 1,  # sh_type
            0,                        # sh_flags
            0,                        # sh_addr
            data_offset + len(payload),  # sh_offset
            len(content),             # sh_size
            0, 0, 1, 0,               # link, info, addralign, entsize
        ))
        payload += content
    if oun0 and ".crt0" not in names:
        payload += b"\x00\x00OUN0"
    shstrndx = 1
    shoff = data_offset + len(payload)
    ident = b"\x7fELF" + bytes([2, 1, 1]) + bytes(9)
    header = ident + struct.pack(
        "<HHIQQQIHHHHHH",
        2,        # e_type ET_EXEC
        0xB7,     # e_machine AArch64
        1,        # e_version
        0,        # e_entry
        0,        # e_phoff
        shoff,    # e_shoff
        0,        # e_flags
        64, 56, 0, 64, len(headers), shstrndx,
    )
    body = header + bytes(data_offset - len(header)) + payload + b"".join(headers)
    Path(path).write_bytes(body)


def write_nro(path, *, magic=b"HOMEBREWNRO0", mod0=True, oun0=True, aset=True,
              title=NACP_TITLE, author=NACP_AUTHOR, version=NACP_VERSION,
              icon=JPEG, nacp_size=16384):
    """A Switch 2 homebrew NRO with its asset section, as elf2nro writes one."""
    nro_size = 0x1000
    body = bytearray(nro_size)
    struct.pack_into("<II", body, 0, 0, 0x100)
    body[8:20] = magic
    struct.pack_into("<I", body, 0x18, nro_size)
    if mod0:
        body[0x100:0x104] = b"MOD0"
    if oun0:
        body[0x120:0x124] = b"OUN0"
    if not aset:
        Path(path).write_bytes(bytes(body))
        return
    nacp = bytearray(nacp_size)
    nacp[:len(title)] = title.encode()
    nacp[0x200:0x200 + len(author)] = author.encode()
    nacp[0x3060:0x3060 + len(version)] = version.encode()
    header_size = 0x38
    icon_offset = header_size
    nacp_offset = icon_offset + len(icon)
    asset = bytearray(header_size)
    asset[0:4] = b"ASET"
    struct.pack_into("<I", asset, 4, 0)
    struct.pack_into("<QQQQ", asset, 8, icon_offset, len(icon), nacp_offset, len(nacp))
    Path(path).write_bytes(bytes(body) + bytes(asset) + icon + bytes(nacp))


SWITCH2_MAP = """Archive member included to satisfy reference by file (symbol)

/opt/devkitpro/libounce/lib/libounce.a(switch_crt0.o)
                              (_start)
/opt/devkitpro/libounce/lib/libounce.a(heap_pages.o)
                              /opt/devkitpro/libounce/lib/libounce.a(malloc.o) (_heapPagesInitialize)
/opt/devkitpro/portlibs/switch2/lib/libuam2rt.a(libuam2rt.a.o)
                              main.o (uam2rt_init)
/opt/devkitpro/libounce/lib/libdrako3d.a(dk_device.o)
                              main.o (dkDeviceCreate)
"""


class Switch2AuditTest(unittest.TestCase):
    """tools/switch2_audit.py reads the artifacts and reports what is wrong."""

    @classmethod
    def setUpClass(cls):
        import switch2_audit

        cls.audit = staticmethod(switch2_audit.audit)

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.directory)], check=False))

    def write_build(self, **overrides):
        """a build/switch2 that passes, with the named artifact replaced"""
        write_nro(self.directory / "warthog.nro", **overrides.get("nro", {}))
        write_elf(self.directory / "warthog.elf", **overrides.get("elf", {}))
        nro = (self.directory / "warthog.nro").read_bytes()
        if len(nro) > 0x1000 + 0x38:
            _, _, nacp_offset, nacp_size = struct.unpack_from("<QQQQ", nro, 0x1000 + 8)
            nacp = nro[0x1000 + nacp_offset:0x1000 + nacp_offset + nacp_size]
        else:
            nacp = bytes(16384)
        (self.directory / "warthog.nacp").write_bytes(nacp)
        (self.directory / "warthog.elf.map").write_text(overrides.get("map", SWITCH2_MAP), encoding="utf-8")

    def problems(self):
        return self.audit(self.directory)

    def assert_complains(self, fragment):
        found = [problem for problem in self.problems() if fragment.lower() in problem.lower()]
        self.assertTrue(found, "no problem mentions %r; got %r" % (fragment, self.problems()))

    # ---------- the build that passes

    def test_a_complete_switch2_build_has_no_problems(self):
        self.write_build()
        self.assertEqual([], self.problems())

    # ---------- the NRO

    def test_a_maxwell_nro_is_refused(self):
        self.write_build(nro={"magic": b"NRO0" + b"\x00" * 8})
        self.assert_complains("HOMEBREWNRO0")

    def test_a_missing_mod0_header_is_refused(self):
        self.write_build(nro={"mod0": False})
        self.assert_complains("MOD0")

    def test_an_nro_without_the_ounce_module_header_is_refused(self):
        self.write_build(nro={"oun0": False})
        self.assert_complains("OUN0")

    def test_an_nro_without_its_asset_section_is_refused(self):
        self.write_build(nro={"aset": False})
        self.assert_complains("ASET")

    def test_an_icon_that_is_not_a_jpeg_is_refused(self):
        self.write_build(nro={"icon": b"\x89PNG\r\n\x1a\n" + b"\x00" * 32})
        self.assert_complains("jpeg")

    def test_a_nacp_of_the_wrong_size_is_refused(self):
        self.write_build(nro={"nacp_size": 0x100})
        self.assert_complains("16384")

    def test_the_nacp_carries_the_title_author_and_version(self):
        self.write_build(nro={"title": "ChupaThingyCE"})
        self.assert_complains("title")
        self.write_build(nro={"author": "nobody"})
        self.assert_complains("author")
        self.write_build(nro={"version": "1.0.0"})
        self.assert_complains("version")

    def test_a_missing_artifact_is_named(self):
        self.write_build()
        (self.directory / "warthog.nacp").unlink()
        self.assert_complains("warthog.nacp")

    # ---------- the ELF

    def test_an_elf_without_debug_info_is_refused(self):
        self.write_build(elf={"sections": (".symtab",)})
        self.assert_complains(".debug_info")

    def test_an_elf_without_a_symbol_table_is_refused(self):
        self.write_build(elf={"sections": (".debug_info",)})
        self.assert_complains(".symtab")

    def test_an_elf_without_the_ounce_module_header_is_refused(self):
        self.write_build(elf={"oun0": False})
        self.assert_complains("OUN0")

    # ---------- the linker map

    def test_a_map_without_libounce_is_refused(self):
        self.write_build(map=SWITCH2_MAP.replace("/opt/devkitpro/libounce/lib/libounce.a", "/opt/devkitpro/libnx/lib/libnx.a"))
        self.assert_complains("libounce.a")

    def test_a_map_without_drako3d_is_refused(self):
        self.write_build(map=SWITCH2_MAP.replace("/libdrako3d.a", "/libdeko3d.a"))
        self.assert_complains("libdrako3d.a")

    def test_a_map_without_the_uam2_runtime_is_refused(self):
        without_uam2 = "\n".join(line for line in SWITCH2_MAP.splitlines() if "uam2" not in line)
        self.write_build(map=without_uam2)
        self.assert_complains("libuam2rt.a")

    def test_an_original_switch_library_in_the_map_is_refused(self):
        for library in ("/opt/devkitpro/libnx/lib/libnx.a", "/opt/devkitpro/libnx/lib/libdeko3d.a",
                        "/opt/devkitpro/portlibs/switch/lib/libEGL.a",
                        "/opt/devkitpro/portlibs/switch/lib/libGLESv2.a",
                        "/opt/devkitpro/portlibs/switch/lib/libglapi.a",
                        "/opt/devkitpro/portlibs/switch/lib/libdrm_nouveau.a",
                        "/opt/devkitpro/portlibs/switch/lib/libnvtegra.a",
                        "/opt/devkitpro/portlibs/switch/lib/libnvidia.a",
                        "/opt/devkitpro/portlibs/switch/lib/libnvdrv.a"):
            with self.subTest(library=library):
                self.write_build(map=SWITCH2_MAP + library + "(member.o)\n")
                self.assertTrue(self.problems(), "%s went unnoticed" % library)

    def test_a_build_machine_path_in_the_map_is_refused(self):
        self.write_build(map=SWITCH2_MAP + "/Users/someone/checkout/port/switch2/host/main.c\n")
        self.assert_complains("home directory")

    def test_the_c_only_portlibs_shared_with_switch_1_are_allowed(self):
        # libounce's switch2_rules shares portlibs/switch's C-only libraries
        # (libSDL2.a, libz.a), so the path alone is not a fault; the Switch 1
        # GPU libraries from it are refused by name above.
        self.write_build(map=SWITCH2_MAP
                         + "/opt/devkitpro/portlibs/switch/lib/libSDL2.a(SDL_switchvideo.o)\n"
                         + "/opt/devkitpro/portlibs/switch/lib/libz.a(adler32.o)\n")
        self.assertEqual([], self.problems())

    # ---------- the command line

    def test_the_command_line_fails_on_a_broken_build(self):
        self.write_build(nro={"oun0": False})
        result = subprocess.run([sys.executable, str(AUDIT), str(self.directory)],
                                capture_output=True, text=True)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("OUN0", result.stdout + result.stderr)

    def test_the_command_line_passes_a_good_build(self):
        self.write_build()
        result = subprocess.run([sys.executable, str(AUDIT), str(self.directory)],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class ToolchainPinTest(unittest.TestCase):
    """The Dockerfile builds what UPSTREAM.json pins, and nothing else.

    A pin that drifts between the two is the failure this catches: the image
    would build a different Drako3D or UAM2 than the record says, and the
    artifacts would still pass the audit.
    """

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(UPSTREAM.read_text(encoding="utf-8"))
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    def argument(self, name):
        found = re.search(r"^ARG\s+%s=(\S+)\s*$" % name, self.dockerfile, re.MULTILINE)
        self.assertIsNotNone(found, "scripts/switch2/Dockerfile has no ARG %s" % name)
        return found.group(1)

    def test_the_build_tools_are_pinned_to_upstream_json(self):
        dependencies = self.record["dependencies"]
        for name, dependency in (("DRAKO3D_COMMIT", "drako3d"), ("UAM2_COMMIT", "uam2"),
                                 ("DRAKOTOOLS_COMMIT", "drakotools")):
            with self.subTest(argument=name):
                self.assertEqual(dependencies[dependency]["commit"], self.argument(name))

    def test_the_base_image_is_pinned_by_digest(self):
        found = re.search(r"^FROM\s+\S+@sha256:([0-9a-f]{64})\s+AS\s+\w+", self.dockerfile, re.MULTILINE)
        self.assertIsNotNone(found, "the base image is not pinned by digest")
        digest = found.group(1)
        self.assertIn(digest, self.record["dependencies"]["ounce-devkit"]["note"],
                      "UPSTREAM.json's ounce-devkit note does not record the base image's digest")

    def test_the_image_installs_the_platform_the_build_links(self):
        # libounce is the platform, and the three things devkitPro does not
        # ship (Drako3D, the UAM2 runtime, drakotools) are built from source.
        for package, pin in (("libounce", "libounce"), ("libkaihen", "kaihen"), ("ouncevk", "ouncevk")):
            version = self.record["dependencies"][pin]["release"]
            self.assertIn(f"${{OUNCE_REPO_URL}}/{package}-{version}-1-any.pkg.tar.zst", self.dockerfile)
        self.assertIn("RemoteFileSigLevel = Required", self.dockerfile)
        self.assertLess(self.dockerfile.index("rm /etc/apt/sources.list.d/devkitpro.list"),
                        self.dockerfile.index("apt-get update"))
        self.assertNotRegex(self.dockerfile, r"\bdkp-pacman\s+-S[a-z]*y")
        for header in ("drako3d.h", "libdrako3d.a", "uam2rt.h", "libuam2rt.a"):
            with self.subTest(header=header):
                self.assertIn(header, self.dockerfile)


class ConfigureTest(unittest.TestCase):
    """configure.py: the Switch 2 graph when it can, a comment when it cannot."""

    def configure(self, port, *arguments):
        """configure.py run in a temporary directory, as a contributor's is"""
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(directory)], check=False))
        result = subprocess.run([sys.executable, str(CONFIGURE), "--console-port", str(port), *arguments],
                                cwd=directory, capture_output=True, text=True)
        return result, directory

    def test_switch2_configures_without_a_toolchain_and_says_why(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(empty)], check=False))
        result, directory = self.configure(ROOT / "port" / "switch2", "--devkitpro", str(empty))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        graph = (directory / "build.ninja").read_text(encoding="utf-8")
        self.assertIn("# Switch 2 build: no libounce", graph)

    def test_the_original_switch_still_configures(self):
        result, directory = self.configure(ROOT / "port" / "switch")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue((directory / "build.ninja").is_file())


class WorkflowTest(unittest.TestCase):
    """CI builds both consoles, and the Switch 2 job is gated by the audit."""

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        cls.jobs = list(yaml_jobs(cls.text))

    def test_the_switch_job_is_kept(self):
        self.assertIn("switch", self.jobs)

    def test_a_switch2_job_builds_and_audits(self):
        self.assertIn("switch2", self.jobs)
        job = yaml_job_body(self.text, "switch2")
        for step in ("scripts/switch2/build.sh image", "scripts/switch2/build.sh configure",
                     "scripts/switch2/build.sh build", "scripts/switch2/build.sh audit"):
            with self.subTest(step=step):
                self.assertIn(step, job)

    def test_the_switch2_job_uploads_the_nro_and_the_elf(self):
        job = yaml_job_body(self.text, "switch2")
        for artifact in ("build/switch2/warthog.nro", "build/switch2/warthog.elf"):
            with self.subTest(artifact=artifact):
                self.assertIn(artifact, job)

    def test_port_tests_compile_the_switch2_graph(self):
        text = (ROOT / ".github" / "workflows" / "port-tests.yml").read_text(encoding="utf-8")
        self.assertIn("port/switch2/build.py", text)


def yaml_jobs(text):
    """the job names under `jobs:`, in a workflow file, without a YAML parser"""
    names = []
    inside = False
    for line in text.splitlines():
        if line.startswith("jobs:"):
            inside = True
            continue
        if inside:
            if line and not line.startswith(" "):
                break
            found = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
            if found:
                names.append(found.group(1))
    return names


def yaml_job_body(text, name):
    """one job's block, so a step is not found in another job's"""
    lines = text.splitlines()
    start = lines.index("  %s:" % name)
    body = []
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", line):
            break
        body.append(line)
    return "\n".join(body)


if __name__ == "__main__":
    unittest.main()
