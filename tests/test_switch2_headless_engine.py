"""Checks shared infrastructure for Switch 2 engine overrides."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import switch_overrides


class OverrideChecks(unittest.TestCase):
    def test_both_ports_are_checked_against_their_own_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "chupathingyce"
            directories = [root / "port" / port / "overrides" for port in ("switch", "switch2")]
            for directory in [game, *directories]:
                directory.mkdir(parents=True)
            (game / "example.c").write_text("upstream\n")
            for directory in directories:
                (directory / "example.c").write_text("fixed\n")
                (directory / "README.md").write_text("## example.c\n")

            with patch.object(switch_overrides, "ROOT", root), \
                 patch.object(switch_overrides, "GAME", game), \
                 patch.object(switch_overrides, "OVERRIDE_DIRS", directories), \
                 patch("sys.argv", ["switch_overrides.py"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(switch_overrides.main(), 0)
                (directories[1] / "README.md").write_text("")
                self.assertEqual(switch_overrides.main(), 1)
                (directories[1] / "README.md").write_text("## example.c\n")
                (directories[1] / "example.c").write_text("upstream\n")
                self.assertEqual(switch_overrides.main(), 1)


if __name__ == "__main__":
    unittest.main()
