from __future__ import annotations

import subprocess
import unittest

from tests.helpers import ROOT


class RuntimeStatsInstallerTest(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "install_runtime_stats_timer.sh"), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_install_prints_units_without_sudo_execution(self) -> None:
        proc = self.run_script("--dry-run", "--registry", "/tmp/skuld-services.json", "--output", "/tmp/stats.json")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Installing Skuld journal stats timer.", proc.stdout)
        self.assertIn("ExecStart=/usr/bin/env python3", proc.stdout)
        self.assertIn("--registry /tmp/skuld-services.json --output /tmp/stats.json", proc.stdout)
        self.assertIn("+ sudo systemctl enable --now skuld-journal-stats.timer", proc.stdout)

    def test_dry_run_uninstall_prints_removal_commands(self) -> None:
        proc = self.run_script("--dry-run", "--uninstall")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Removing Skuld journal stats timer.", proc.stdout)
        self.assertIn("+ sudo systemctl disable --now skuld-journal-stats.timer", proc.stdout)
        self.assertIn("+ sudo rm -f", proc.stdout)


if __name__ == "__main__":
    unittest.main()
