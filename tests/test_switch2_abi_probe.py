import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AbiProbeTest(unittest.TestCase):
    def test_probe_and_decision_are_present(self):
        self.assertTrue((ROOT / "port/switch2/probe/abi_probe.c").is_file())
        decision = (ROOT / "docs/adr/0001-lp64-native-abi.md").read_text()
        for term in ("HALO_64BIT", "ILP32", "Tested on hardware", "host_mman.c"):
            self.assertIn(term, decision)

    def test_toolchain_build_and_audit(self):
        if not shutil.which("docker"):
            self.skipTest("Docker is not installed")
        image = subprocess.run(
            ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if image.returncode:
            self.skipTest("pinned local toolchain image is not available")
        script = ROOT / "scripts/switch2/build.sh"
        for args in (("configure",), ("ninja", "switch2", "switch2-probe-abi"), ("audit",)):
            subprocess.run([str(script), *args], cwd=ROOT, check=True)
        for name in ("abi_probe.elf", "abi_probe.nro"):
            self.assertTrue((ROOT / "build/switch2" / name).is_file())


if __name__ == "__main__":
    unittest.main()
