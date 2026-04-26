from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import skuld_linux_runtime as runtime


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class LinuxRuntimeStatsTest(unittest.TestCase):
    def test_loads_runtime_stats_with_normalized_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal_stats.json"
            path.write_text(
                json.dumps(
                    {
                        "services": {
                            "api": {"executions": "3", "restarts": "-1"},
                            "bad": "ignored",
                        }
                    }
                ),
                encoding="utf-8",
            )

            stats = runtime.load_runtime_stats(path)

        self.assertEqual(stats, {"api": {"executions": 3, "restarts": 0}})

    def test_format_restarts_exec(self) -> None:
        self.assertEqual(runtime.format_restarts_exec("api", {"api": {"restarts": 2, "executions": 7}}), "2/7")
        self.assertEqual(runtime.format_restarts_exec("worker", {}), "-")


class LinuxJournalRuntimeTest(unittest.TestCase):
    def test_detects_journal_permission_hint(self) -> None:
        self.assertTrue(runtime.journal_permission_hint("You are not seeing messages from other users and the system."))
        self.assertTrue(runtime.journal_permission_hint("Permission denied"))
        self.assertFalse(runtime.journal_permission_hint("No entries"))

    def test_count_unit_starts_uses_journal_filters(self) -> None:
        calls = []

        def scope_env(scope: str):
            return {"XDG_RUNTIME_DIR": "/run/user/1000"}

        def journal_cmd(scope: str, args: list[str]) -> list[str]:
            return ["journalctl", "--user", *args]

        def run_cmd(cmd, check=True, capture=False, env=None):
            calls.append((cmd, env))
            return completed(stdout='{"MESSAGE":"Started"}\n\n{"MESSAGE":"Started again"}\n')

        count = runtime.count_unit_starts(
            unit="api.service",
            scope="user",
            systemd_scope_env=scope_env,
            journalctl_command=journal_cmd,
            run_cmd=run_cmd,
            run_sudo_cmd=lambda *args, **kwargs: completed(),
            since="1 hour ago",
            boot=True,
        )

        self.assertEqual(count, 2)
        self.assertIn("MESSAGE_ID=39f53479d3a045ac8e11786248231fbf", calls[0][0])
        self.assertIn("--since", calls[0][0])
        self.assertIn("-b", calls[0][0])
        self.assertEqual(calls[0][1], {"XDG_RUNTIME_DIR": "/run/user/1000"})

    def test_count_unit_starts_falls_back_to_sudo_for_system_permission_hint(self) -> None:
        sudo_calls = []

        def run_sudo_cmd(cmd, check=True, capture=False):
            sudo_calls.append(cmd)
            return completed(stdout="one\ntwo\n")

        count = runtime.count_unit_starts(
            unit="api.service",
            scope="system",
            systemd_scope_env=lambda scope: None,
            journalctl_command=lambda scope, args: ["journalctl", *args],
            run_cmd=lambda *args, **kwargs: completed(stderr="Permission denied"),
            run_sudo_cmd=run_sudo_cmd,
        )

        self.assertEqual(count, 2)
        self.assertTrue(sudo_calls)

    def test_read_restart_count(self) -> None:
        self.assertEqual(
            runtime.read_restart_count(
                name="api",
                scope="system",
                unit_exists=lambda unit, scope="system": True,
                systemctl_show=lambda unit, props, scope="system": {"NRestarts": "4"},
            ),
            "4",
        )
        self.assertEqual(
            runtime.read_restart_count(
                name="api",
                scope="system",
                unit_exists=lambda unit, scope="system": False,
                systemctl_show=lambda unit, props, scope="system": {},
            ),
            "-",
        )


if __name__ == "__main__":
    unittest.main()
