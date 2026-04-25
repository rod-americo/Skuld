from __future__ import annotations

import subprocess
import unittest

from tests.helpers import ROOT


class LiveSmokeRunnerTest(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "run_live_smokes.sh"), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_help_lists_explicit_targets(self) -> None:
        proc = self.run_script("--help")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--macos", proc.stdout)
        self.assertIn("--linux-host", proc.stdout)

    def test_requires_at_least_one_target(self) -> None:
        proc = self.run_script()

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Choose at least one smoke target.", proc.stderr)


if __name__ == "__main__":
    unittest.main()
