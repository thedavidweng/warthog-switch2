import ctypes
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "port/switch2/host"


class CacheTests(unittest.TestCase):
    def test_key_changes_for_each_identity_component_and_progress_is_visible(self):
        program = r"""
#include "switch2_shader_cache.h"
#include <stdio.h>
#include <string.h>
int main(void) {
 struct switch2_shader_cache_key a, b;
 switch2_shader_cache_key_init(&a, 7, 9, 11);
 b = a; b.generator++; printf("%llu %llu\n",
   (unsigned long long)a.digest, (unsigned long long)switch2_shader_cache_key_digest(&b));
 struct switch2_shader_progress p = { 3, 8 }; char text[80];
 switch2_shader_progress_format(text, sizeof(text), &p); puts(text);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "test.c"
            binary = Path(directory) / "test"
            source.write_text(program)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-I", str(HOST),
                            str(source), str(HOST / "switch2_shader_cache.c"),
                            "-o", str(binary)], check=True)
            output = subprocess.check_output([binary], text=True).splitlines()
        self.assertNotEqual(output[0].split()[0], output[0].split()[1])
        self.assertEqual(output[1], "Compiling shaders: 3 / 8 (37%)")

    def test_atomic_write_survives_restart_and_truncated_dksh_is_rejected(self):
        program = r"""
#include "switch2_shader_cache.h"
#include <stdio.h>
int main(int argc, char **argv) {
 unsigned char bytes[64] = {0}; bytes[0]='D'; bytes[1]='K'; bytes[2]='S'; bytes[3]='H';
 printf("%d %d\n", switch2_shader_cache_atomic_write(argv[1], bytes, sizeof(bytes)),
   switch2_shader_cache_validate_dksh(bytes, 8));
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / "test.c", Path(directory) / "test"
            target = Path(directory) / "cache.dksh"
            source.write_text(program)
            subprocess.run(["cc", "-std=c11", "-I", str(HOST), str(source),
                            str(HOST / "switch2_shader_cache.c"), "-o", str(binary)],
                           check=True)
            self.assertEqual(subprocess.check_output([binary, target], text=True).strip(), "1 0")
            self.assertTrue(target.is_file())
            self.assertFalse((target.with_name("cache.dksh.tmp")).exists())

    def test_switch2_shader_checker_rejects_non_ampere_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.dksh"
            data = bytearray(32)
            data[:4] = b"DKSH"
            data[24:28] = (100).to_bytes(4, "little")
            path.write_bytes(data)
            result = subprocess.run(["python3", str(ROOT / "tools/dk_shader_check.py"),
                                     "--target", "switch2", directory],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid Ampere", result.stdout)


if __name__ == "__main__":
    unittest.main()
