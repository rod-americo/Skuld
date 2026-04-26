from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT


class CliSmokeTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tempdir:
            home = Path(tempdir)
            env = {
                "HOME": str(home),
                "PATH": "",
                "PYTHONPATH": str(ROOT),
                "SKULD_HOME": str(home / "skuld-home"),
                "SKULD_ENV_FILE": str(home / "missing.env"),
                "SKULD_RUNTIME_STATS_FILE": str(home / "journal_stats.json"),
            }
            env.pop("SKULD_SUDO_PASSWORD", None)
            return subprocess.run(
                [sys.executable, str(ROOT / "skuld"), *args],
                env=env,
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

    def test_neutral_subcommand_help_is_available(self) -> None:
        subcommands = (
            "list",
            "catalog",
            "track",
            "rename",
            "untrack",
            "exec",
            "start",
            "stop",
            "restart",
            "status",
            "logs",
            "stats",
            "doctor",
            "describe",
            "sync",
            "version",
            "sudo",
        )
        for subcommand in subcommands:
            with self.subTest(subcommand=subcommand):
                proc = self.run_cli(subcommand, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("usage: skuld", proc.stdout)

    def test_console_script_target_runs_version(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            home = Path(tempdir)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "from skuld_entrypoint import main; "
                        "sys.argv = ['skuld', 'version']; "
                        "raise SystemExit(main())"
                    ),
                ],
                cwd=ROOT,
                env={
                    "HOME": str(home),
                    "PATH": "",
                    "PYTHONPATH": str(ROOT),
                    "SKULD_HOME": str(home / "skuld-home"),
                    "SKULD_ENV_FILE": str(home / "missing.env"),
                    "SKULD_RUNTIME_STATS_FILE": str(home / "journal_stats.json"),
                },
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout.strip(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
