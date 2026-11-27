"""Host checks for the shared Drako3D/Deko3D synchronization contract."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from switch2_toolchain import available as switch2_toolchain_available

ROOT = Path(__file__).resolve().parents[1]


class Drako3DParityTests(unittest.TestCase):
    def test_sync_policy_compiles_and_gates_fence_reuse(self):
        program = r'''
#include "switch2_drako3d.h"
#include <stdio.h>
int main(void) {
    struct switch2_drako3d_sync_stats stats = {0};
    if (switch2_drako3d_fence_allows_reuse(9, 10) ||
        switch2_drako3d_fence_allows_reuse(8, 10) ||
        !switch2_drako3d_resize_requires_idle(1) ||
        switch2_drako3d_resize_requires_idle(0) ||
        !switch2_drako3d_hud_requires_clean(1) ||
        switch2_drako3d_hud_requires_clean(0) ||
        switch2_drako3d_copy_invalidate_flags() != 0x11)
        return 1;
    switch2_drako3d_record_upload(&stats, 64);
    switch2_drako3d_record_rollover(&stats);
    switch2_drako3d_record_fence_wait(&stats, 7);
    printf("%llu %llu %llu %llu\n",
           (unsigned long long)stats.upload_bytes,
           (unsigned long long)stats.upload_rollovers,
           (unsigned long long)stats.fence_waits,
           (unsigned long long)stats.fence_wait_us);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sync.c"
            binary = Path(directory) / "sync"
            source.write_text(program)
            subprocess.run(
                ["cc", "-std=c11", "-I", str(ROOT / "port/switch2/host"),
                 str(source), str(ROOT / "port/switch2/host/switch2_drako3d.c"),
                 "-o", str(binary)],
                check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True,
                                    capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "64 1 1 7")

    def test_renderer_keeps_ampere_barrier_invariants(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        hud = (ROOT / "port/switch/host/host_dk_hud.c").read_text()
        self.assertIn("DkInvalidateFlags_Descriptors", source)
        self.assertIn("switch2_drako3d_copy_invalidate_flags", source)
        self.assertIn("queue_wait_idle();", source)
        self.assertIn("armDCacheClean", source)
        self.assertIn("dkCmdBufCopyBufferToImage", source)
        self.assertIn("dkImageDescriptorInitialize", source)
        self.assertIn("dkSamplerDescriptorInitialize", source)
        self.assertIn("armDCacheFlush", hud)

    def test_telemetry_and_adr_document_sync_contract(self):
        perf = (ROOT / "port/switch2/host/switch2_perf.h").read_text()
        adr = (ROOT / "docs/adr/0004-production-drako3d-parity.md").read_text()
        for field in ("upload_bytes", "upload_rollovers", "fence_waits", "fence_wait_us"):
            self.assertIn(field, perf)
        for field in ("upload_bytes", "upload_rollovers", "fence_waits", "fence_wait_us"):
            self.assertIn(field, adr)
        for term in ("Drako3D 0.5.0", "UAM2 0.1.0", "OunceVK", "DEKO3D=200"):
            self.assertIn(term, adr)

    def test_switch2_has_no_experimental_renderer_scaffolding(self):
        files = list((ROOT / "port/switch2").rglob("*"))
        text = "\n".join(path.read_text(errors="ignore") for path in files if path.is_file())
        self.assertNotIn("glCreateShader", text)
        self.assertNotIn("vkCreateInstance", text)
    @unittest.skipUnless(switch2_toolchain_available(), "Switch 2 toolchain image unavailable")
    def test_push_constants_ubo_sizes_are_aligned_to_dk_uniform_buf_alignment(self):
        import re

        build = ROOT / "scripts/switch2/build.sh"
        subprocess.run([str(build), "ninja", "build/switch2/host/host_dk.c.o"],
                       cwd=ROOT, check=True, capture_output=True)
        disasm = subprocess.run(
            [str(build), "/opt/devkitpro/devkitA64/bin/aarch64-none-elf-objdump", "-dr",
             "build/switch2/host/host_dk.c.o"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        ubo_sizes = []
        last_w2 = None
        for line in disasm.splitlines():
            m = re.search(r"\bmov\s+w2,\s*#(0x[0-9a-fA-F]+|\d+)", line)
            if m:
                last_w2 = int(m.group(1), 0)
            if "R_AARCH64_CALL26\tdkCmdBufPushConstants" in line:
                ubo_sizes.append(last_w2)
                last_w2 = None
        self.assertEqual(len(ubo_sizes), 3)
        for size in ubo_sizes:
            self.assertIsNotNone(size)
            self.assertEqual(size % 0x100, 0, f"uboSize {size:#x} is not aligned to DK_UNIFORM_BUF_ALIGNMENT (0x100)")
        self.assertEqual(sorted(ubo_sizes), [0x100, 0x300, 0xC00])


if __name__ == "__main__":
    unittest.main()
