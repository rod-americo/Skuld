from __future__ import annotations

import subprocess
import sys
import unittest

from tests.helpers import ROOT


class CliSmokeTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "skuld"), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_top_level_help_is_available(self) -> None:
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage: skuld", proc.stdout)
        self.assertIn("track", proc.stdout)

    def test_version_does_not_require_backend_registry(self) -> None:
        proc = self.run_cli("version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout.strip(), r"^\d+\.\d+\.\d+$")

    def test_important_subcommand_help_is_available(self) -> None:
        for subcommand in ("list", "track", "logs", "doctor", "sudo"):
            with self.subTest(subcommand=subcommand):
                proc = self.run_cli(subcommand, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("usage: skuld", proc.stdout)


if __name__ == "__main__":
    unittest.main()
