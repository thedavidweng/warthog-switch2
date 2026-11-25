"""The repository's own documentation and upstream record (ticket #2).

Run with: python3 -m unittest discover -s tests

Every expectation here comes from the project spec (issue #1, "Verified
technical baseline") rather than from the files under test, so a drift in
`UPSTREAM.json`, `AGENTS.md`, `GLOSSARY.md` or `README.md` fails a check
instead of silently rewriting what "correct" means.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPSTREAM = ROOT / "UPSTREAM.json"
AGENTS = ROOT / "AGENTS.md"
GLOSSARY = ROOT / "GLOSSARY.md"
README = ROOT / "README.md"
ADR_DIR = ROOT / "docs" / "adr"

# Documents that ship to contributors and coding agents, and so must carry no
# personal paths or private addresses.
PUBLIC_DOCS = [README, AGENTS, GLOSSARY, UPSTREAM, *sorted((ROOT / "docs").rglob("*.md"))]

# The revisions reviewed for this port (issue #1, "Verified technical baseline").
UPSTREAM_COMMIT = "366f43cbe060fcc554c00d834075d5d8f7f8e534"
ENGINE_COMMIT = "2e5eac00e3d6655e094fbbcd13253ac2b10ee773"
OUNCEBREW_COMMITS = {
    "ounce-devkit": "5e957599bd498643d82e5470aec80da67a12685d",
    "libounce": "03af07a739a9a3b48704500cffcd6155692cc194",
    "kaihen": "3b23b5dc6e75539855eca69ffdda371ce69631bb",
    "drako3d": "93ba2e7fbf2d3dc648f9f9f08e8b3aef4a70945d",
    "uam2": "11f145faa1c13bc78da3c8bea55160b4cd672e40",
    "drakotools": "6569f54518b6cea88ef59c1b9486b3d163d31313",
    "ouncevk": "97d70925dcd8ccab07f308e9dfd0ee5812e4a01c",
}
DOLPHIN_NX_COMMIT = "7fb685b353e19a9a5848e9bd658945d1f9cd382a"
BO2_COMMIT = "e024537c1009a8930c92f6a940525cc914b7bd09"
MIT_HELPERS = ("nx2_platform", "nx2_gameshare")

SHA1 = re.compile(r"^[0-9a-f]{40}$")


def read(path):
    return path.read_text(encoding="utf-8")


def entries(node):
    """every dict under `node`, keyed by the name it is filed under."""
    found = {}
    if not isinstance(node, dict):
        return found
    for name, value in node.items():
        if isinstance(value, dict):
            found[name] = value
    return found


class UpstreamRecordTest(unittest.TestCase):
    """UPSTREAM.json is the one authority for what this port builds against."""

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(read(UPSTREAM))

    def test_schema_and_sections(self):
        self.assertEqual(1, self.record["schema"])
        for section in ("upstream", "submodules", "dependencies", "references"):
            self.assertIn(section, self.record, "UPSTREAM.json has no %r section" % section)

    def test_direct_upstream(self):
        upstream = self.record["upstream"]
        self.assertEqual("https://github.com/ChupathingyCE/warthog-switch", upstream["repository"])
        self.assertEqual(UPSTREAM_COMMIT, upstream["commit"])
        self.assertEqual("GPL-3.0-or-later", upstream["license"])
        self.assertEqual("build-7", upstream["release"])
        self.assertEqual("0.9.1a", upstream["version"])

    def test_pinned_engine_submodule(self):
        engine = self.record["submodules"]["chupathingyce"]
        self.assertEqual("chupathingyce", engine["path"])
        self.assertEqual("https://github.com/ChupathingyCE/chupathingyce.git", engine["repository"])
        self.assertEqual(ENGINE_COMMIT, engine["commit"])
        self.assertEqual("GPL-3.0-or-later", engine["license"])

    def test_ouncebrew_components(self):
        dependencies = entries(self.record["dependencies"])
        for name, commit in OUNCEBREW_COMMITS.items():
            self.assertIn(name, dependencies, "no pin for %s" % name)
            self.assertEqual(commit, dependencies[name]["commit"], name)
            self.assertTrue(dependencies[name]["license"], "%s records no license" % name)

    def test_drako3d_is_the_production_renderer_and_ouncevk_contingency(self):
        dependencies = entries(self.record["dependencies"])
        self.assertEqual("Zlib", dependencies["drako3d"]["license"])
        self.assertEqual("contingency", dependencies["ouncevk"]["role"])

    def test_dolphin_nx_reference_and_mit_helpers(self):
        reference = self.record["references"]["dolphin_nx"]
        self.assertEqual("https://github.com/NaGaa95/dolphin-nx", reference["repository"])
        self.assertEqual(DOLPHIN_NX_COMMIT, reference["commit"])
        self.assertEqual("1.2.3", reference["version"])
        self.assertIn("GPL-2.0-or-later", reference["license"])
        helpers = reference["mit_helpers"]
        for helper in MIT_HELPERS:
            self.assertIn(helper, helpers, "no MIT provenance for %s" % helper)
            files = [Path(name).name for name in helpers[helper]["files"]]
            for suffix in (".c", ".h"):
                self.assertIn(helper + suffix, files, "%s%s is not recorded" % (helper, suffix))

    def test_bo2_requiem_is_reference_only(self):
        reference = self.record["references"]["bo2_requiem_nx"]
        self.assertEqual("https://github.com/HDErick/BO2-Requiem-NX", reference["repository"])
        self.assertEqual(BO2_COMMIT, reference["commit"])
        self.assertEqual("reference-only", reference["role"])

    def test_every_pin_is_a_full_commit(self):
        def walk(node, trail):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, trail + [key])
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, trail + [str(index)])
            elif node is not None and "commit" in trail[-1:]:
                self.assertRegex(node, SHA1, "%s is not a full commit hash" % ".".join(trail))

        walk(self.record, [])


class AgentGuideTest(unittest.TestCase):
    """AGENTS.md teaches a new contributor or agent the rules of this port."""

    REQUIRED_SECTIONS = {
        "scope": ("scope",),
        "engine/platform boundary": ("engine", "boundary"),
        "shared Deko3D/Drako3D renderer": ("deko3d", "drako3d"),
        "dependency pinning authority": ("upstream.json",),
        "MIT helper provenance": ("mit", "provenance"),
        "upstream compatibility": ("upstream compatibility",),
        "decision records": ("adr",),
        "build and test": ("build and test",),
        "platform constraints": ("platform constraints",),
        "licensing": ("licens",),
        "hardware workflow": ("hardware",),
        "release requirements": ("release",),
    }

    @classmethod
    def setUpClass(cls):
        cls.text = read(AGENTS)
        cls.headings = re.findall(r"^#{1,6} (.+)$", cls.text, re.MULTILINE)

    def test_required_sections(self):
        headings = [heading.lower() for heading in self.headings]
        for topic, words in self.REQUIRED_SECTIONS.items():
            self.assertTrue(any(all(word in heading for word in words) for heading in headings),
                            "AGENTS.md has no %s section (headings: %s)" % (topic, self.headings))

    def test_keeps_the_agent_skills_section(self):
        self.assertIn("## Agent skills", self.text)
        for pointer in ("docs/agents/issue-tracker.md", "docs/agents/triage-labels.md",
                        "docs/agents/domain.md"):
            self.assertIn(pointer, self.text)

    def test_names_upstream_json_as_the_pin_authority(self):
        self.assertIn("UPSTREAM.json", self.text)
        self.assertIn(UPSTREAM_COMMIT, self.text)
        self.assertIn(ENGINE_COMMIT, self.text)

    def test_documents_the_mit_helpers(self):
        for helper in MIT_HELPERS:
            self.assertIn(helper, self.text)
        self.assertIn("NaGaa95/dolphin-nx", self.text)
        self.assertIn("MIT", self.text)

    def test_documents_the_upstream_compatibility_contract(self):
        self.assertIn("ninja switch", self.text)
        self.assertIn("port/switch/overrides", self.text)

    def test_documents_both_abi_candidates(self):
        self.assertIn("ILP32", self.text)
        self.assertIn("LP64", self.text)
        lowered = self.text.lower()
        for claim in ("lp64-only port", "only native lp64", "native lp64 is the only"):
            self.assertNotIn(claim, lowered)

    def test_documents_the_build_and_test_commands(self):
        self.assertIn("ninja switch2", self.text)
        self.assertIn("python3 -m unittest discover -s tests", self.text)
        self.assertIn("WARTHOG_SWITCH2_HOST", self.text)
        self.assertNotRegex(self.text, r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

    def test_documents_only_commands_that_exist(self):
        documented = set(re.findall(r"tools/([a-z_0-9]+\.py)", self.text))
        for name in documented:
            self.assertTrue((ROOT / "tools" / name).is_file(),
                            "AGENTS.md documents tools/%s, which does not exist" % name)
        self.assertNotIn("switch_deploy.py --switch2", self.text)

    def test_decision_process_points_at_glossary_and_adrs(self):
        self.assertIn("GLOSSARY.md", self.text)
        self.assertIn("docs/adr/", self.text)

    def test_release_requirements_are_concrete(self):
        lowered = self.text.lower()
        for requirement in ("nacp", "attribution", "shader", "verification"):
            self.assertIn(requirement, lowered)

    def test_nx2_naming_is_confined_to_the_mit_helpers(self):
        for match in re.finditer(r"nx2[^\s`)]*", self.text, re.IGNORECASE):
            self.assertIn(match.group(0).lower(), ("nx2_platform", "nx2_gameshare", "nx2_platform.{c,h}",
                                                   "nx2_gameshare.{c,h}"),
                          "%s is NX2 branding, not a helper filename" % match.group(0))

    def test_no_personal_data(self):
        assert_no_personal_data(self, self.text, "AGENTS.md")


class GlossaryTest(unittest.TestCase):
    """One name per concept, so the spec, tickets and code cannot drift apart."""

    TERMS = (
        "Warthog for Switch 2",
        "Ounce",
        "switch2",
        "Drako3D",
        "UAM2",
        "DKSH",
        "kaiHEN",
        "ILP32 guest",
        "LP64",
        "Nmouse",
        "GameShare",
        "Implemented",
        "Compiled",
        "Tested on host",
        "Tested on hardware",
        "Verified against upstream",
        "Not yet supported",
    )

    @classmethod
    def setUpClass(cls):
        cls.text = read(GLOSSARY)

    def test_exists_and_defines_the_terms(self):
        for term in self.TERMS:
            self.assertIn("**%s**" % term, self.text, "GLOSSARY.md does not define %s" % term)

    def test_definitions_carry_their_avoided_synonyms(self):
        self.assertGreaterEqual(self.text.count("_Avoid_:"), len(self.TERMS))

    def test_no_personal_data(self):
        assert_no_personal_data(self, self.text, "GLOSSARY.md")


class ReadmeTest(unittest.TestCase):
    """The README is the public face of a pre-release port."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(README)

    def test_names_the_application(self):
        self.assertIn("Warthog for Switch 2", self.text)

    def test_uses_switch2_and_ounce_naming_without_nx2_branding(self):
        self.assertIn("switch2", self.text)
        self.assertIn("Ounce", self.text)
        for match in re.finditer(r"nx2[^\s`)]*", self.text, re.IGNORECASE):
            self.assertIn(match.group(0).lower(), ("nx2_platform", "nx2_gameshare"),
                          "%s is NX2 branding, not a helper filename" % match.group(0))

    def test_install_layout(self):
        self.assertIn("sdmc:/switch/warthog/", self.text)
        for name in ("warthog.nro", "config.toml", "brokers.txt", "maps_ce/", "save/", "logs/"):
            self.assertIn(name, self.text)

    def test_preserves_upstream_credits(self):
        for credit in ("ChupathingyCE", "thelinkin3000", "ouncebrew", "NaGaa95"):
            self.assertIn(credit, self.text, "README does not credit %s" % credit)

    def test_licensing_notices(self):
        self.assertIn("GPL-3.0-or-later", self.text)
        for notice in ("MIT", "Zlib", "ISC"):
            self.assertIn(notice, self.text, "README does not carry the %s notice" % notice)

    def test_no_affiliation_claim(self):
        lowered = self.text.lower()
        self.assertIn("not affiliated", lowered)
        self.assertIn("nintendo", lowered)
        for claim in ("official nintendo", "endorsed by nintendo", "official port",
                      "authorised by", "authorized by"):
            self.assertNotIn(claim, lowered)

    def test_states_that_game_data_comes_from_the_players_own_disc(self):
        lowered = self.text.lower()
        self.assertIn("your own", lowered)
        self.assertIn("xbox", lowered)
        for claim in ("mcc is enough", "the pc version is enough", "any halo copy will do"):
            self.assertNotIn(claim, lowered)
        # owning the PC or MCC release alone is explicitly not enough
        self.assertIn("is not enough", lowered)

    def test_documents_only_commands_that_exist(self):
        """A documented command is a promise; nothing invented is allowed."""
        documented = set(re.findall(r"tools/([a-z_0-9]+\.py)", self.text))
        for name in documented:
            self.assertTrue((ROOT / "tools" / name).is_file(),
                            "README documents tools/%s, which does not exist" % name)
        # the deploy tool has no --switch2 flag yet (ticket #4 adds it)
        self.assertNotIn("switch_deploy.py --switch2", self.text)

    def test_reports_pre_release_status_honestly(self):
        lowered = self.text.lower()
        self.assertTrue("not yet released" in lowered or "pre-release" in lowered,
                        "README must say the port is pre-release")
        self.assertIn("verification", lowered)

    def test_no_ouncevk_first_claim(self):
        """OunceVK may appear as a named contingency, never as the port's renderer."""
        for paragraph in re.split(r"\n\s*\n", self.text):
            if "OunceVK" not in paragraph:
                continue
            lowered = paragraph.lower()
            for claim in ("vulkan-first", "ouncevk-first", "primary renderer", "main renderer",
                          "production renderer", "the graphics backend"):
                self.assertNotIn(claim, lowered,
                                 "OunceVK is described as %r in: %s" % (claim, paragraph))

    def test_no_personal_data(self):
        assert_no_personal_data(self, self.text, "README.md")


class ConsistencyTest(unittest.TestCase):
    """No second, contradictory copy of the port's story."""

    def test_adr_directory_exists_and_is_explained(self):
        self.assertTrue(ADR_DIR.is_dir(), "docs/adr/ is missing")
        self.assertTrue((ADR_DIR / "README.md").is_file(), "docs/adr/README.md is missing")

    def test_no_document_claims_a_vulkan_or_lp64_only_port(self):
        for path in (README, AGENTS):
            text = read(path).lower()
            for claim in ("ouncevk-first", "vulkan-first", "lp64-only port", "only native lp64"):
                self.assertNotIn(claim, text, "%s still claims %r" % (path.name, claim))

    def test_the_switch_1_port_commands_survive(self):
        for path in (README, AGENTS):
            self.assertIn("ninja switch", read(path))

    def test_public_documents_carry_no_personal_data(self):
        for path in PUBLIC_DOCS:
            assert_no_personal_data(self, read(path), path.name)


def assert_no_personal_data(test, text, name):
    """A committed document names no home directory and no private address."""
    for pattern, what in (
        (r"/Users/[^/\s]+", "a home directory"),
        (r"/home/[^/\s]+", "a home directory"),
        (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "a private address"),
        (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "a private address"),
        (r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", "a private address"),
    ):
        found = re.search(pattern, text)
        test.assertIsNone(found, "%s contains %s: %s" % (name, what, found.group(0) if found else ""))


if __name__ == "__main__":
    unittest.main()
