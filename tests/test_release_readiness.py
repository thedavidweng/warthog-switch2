import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATUS_WORDS = (
    "Implemented",
    "Compiled",
    "Tested on host",
    "Tested on hardware",
    "Verified against upstream",
    "Not yet supported",
)
REQUIRED_DOCS = (
    "README.md",
    "port/switch2/README.md",
    "docs/status-matrix.md",
    "docs/troubleshooting.md",
    "docs/architecture.md",
    "docs/upstream-sync.md",
    "docs/release-checklist.md",
    "docs/adr/0001-lp64-native-abi.md",
    "docs/adr/0002-drako3d-uam2-renderer.md",
    "docs/adr/0003-sdl2-host-sdl3-seam.md",
    "docs/adr/0004-production-drako3d-parity.md",
    "docs/campaign-status.md",
    "docs/gameshare.md",
    "docs/lifecycle.md",
    "docs/mcc-investigation.md",
    "docs/networking.md",
    "docs/switch1-caps-review.md",
)
MAJOR_SUBSYSTEMS = (
    "Installation",
    "Extraction",
    "Self-Update",
    "Native LP64",
    "Drako3D",
    "shader cache",
    "Campaign",
    "Saves",
    "Controllers",
    "Gyro",
    "swkbd",
    "KBM",
    "Nmouse",
    "Split-Screen",
    "Display",
    "120 Hz",
    "VRR",
    "4K60",
    "Lifecycle",
    "Clocks",
    "Networking",
    "HTTPS",
    "Custom Edition",
    "MCC",
    "GameShare",
    "Performance",
)
TOOLS = {
    path.name
    for path in (ROOT / "tools").glob("*.py")
}


def documents():
    return [ROOT / "README.md", ROOT / "port/switch2/README.md", *DOCS.glob("*.md")]


class ReleaseReadinessTests(unittest.TestCase):
    def test_required_documents_exist_and_are_non_empty(self):
        for relative in REQUIRED_DOCS:
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertTrue(path.read_text(encoding="utf-8").strip(), relative)

    def test_status_matrix_is_complete_and_honest(self):
        text = (DOCS / "status-matrix.md").read_text(encoding="utf-8")
        for subsystem in MAJOR_SUBSYSTEMS:
            self.assertIn(subsystem.lower(), text.lower())
        for status in STATUS_WORDS:
            self.assertIn(status, text)
        for forbidden in ("coming soon", "WIP", "TODO", "NX2", "4K120"):
            self.assertNotIn(forbidden, text)
        for pending in ("gameplay", "campaign", "Drako3D", "Nmouse", "GameShare"):
            self.assertNotRegex(
                text,
                rf"(?is)(?:{re.escape(pending)}.{{0,180}}Tested on hardware|"
                rf"Tested on hardware.{{0,180}}{re.escape(pending)})",
            )

    def test_document_links_and_tool_commands_are_real(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for link in re.findall(r"\]\((docs/[^)#]+)", readme):
            self.assertTrue((ROOT / link).is_file(), link)
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents())
        for name in re.findall(r"tools/([a-zA-Z0-9_]+\.py)", text):
            self.assertIn(name, TOOLS, name)
        self.assertNotIn("It draws nothing and plays nothing", (ROOT / "port/switch2/README.md").read_text(encoding="utf-8"))
        self.assertNotIn("| Drako3D renderer and Ampere shader compilation | Not yet supported", readme)
        self.assertNotIn("| Gameplay, campaign, multiplayer on Switch 2 | Not yet supported", readme)
        self.assertNotIn("| Switch 2 display modes", readme)
        self.assertNotIn("| Joy-Con 2 `Nmouse` aiming | Not yet supported", readme)

    def test_documents_have_no_personal_data_or_forbidden_release_assets(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents())
        self.assertNotRegex(text, r"/Users/|/home/|(?:^|[^\d])192\.168\.\d+\.\d+|(?:^|[^\d])10\.\d+\.\d+\.\d+|(?:^|[^\d])172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+")
        self.assertNotRegex(text, r"<[^>\s]+@[^>\s]+>")

    def test_original_switch_configure_has_a_safe_builddir(self):
        configure = (ROOT / "chupathingyce/configure.py").read_text(encoding="utf-8")
        self.assertIn('build_dir=Path("build")', configure)
        self.assertIn("--console-port", configure)

    def test_packager_contract_is_present(self):
        package = (ROOT / "tools/switch_package.py").read_text(encoding="utf-8")
        audit = (ROOT / "tools/switch2_audit.py").read_text(encoding="utf-8")
        for value in ("ZIP_STORED", "SHA256SUMS.txt", "warthog-switch2-{args.flavor}"):
            self.assertIn(value, package)
        docs = "\n".join(path.read_text(encoding="utf-8") for path in documents())
        self.assertIn("save/", docs)
        self.assertIn("maps_ce/", docs)
        for value in ("gpl-3.0-or-later", "zlib", "isc", "mit", "nx2_platform", "nx2_gameshare"):
            self.assertIn(value, audit.lower() + package.lower())


if __name__ == "__main__":
    unittest.main()
