from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import skuld_macos_launchd as launchd


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class MacLaunchdAdapterTest(unittest.TestCase):
    def test_domain_and_service_targets(self) -> None:
        self.assertEqual(launchd.domain_target("agent", uid=501), "gui/501")
        self.assertEqual(launchd.domain_target("daemon"), "system")
        self.assertEqual(launchd.service_target("daemon", "com.example.worker"), "system/com.example.worker")

    def test_run_launchctl_uses_sudo_for_daemon_scope(self) -> None:
        with patch.object(launchd.common, "run_sudo_command", return_value=completed()) as run_sudo:
            launchd.run_launchctl("daemon", ["bootout", "system/com.example.worker"], sudo_password="pw")

        run_sudo.assert_called_once_with(
            ["launchctl", "bootout", "system/com.example.worker"],
            sudo_password="pw",
            check=True,
            capture=False,
        )

    def test_parse_kv_and_extract_value(self) -> None:
        raw = """
        path = /Users/me/Library/LaunchAgents/com.example.worker.plist
        "PID" = 123;
        LastExitStatus = 0;
        """
        self.assertEqual(
            launchd.extract_value(raw, "path"),
            "/Users/me/Library/LaunchAgents/com.example.worker.plist",
        )
        self.assertEqual(launchd.parse_kv('"PID" = 123;\nLastExitStatus = 0;\n'), {"PID": "123", "LastExitStatus": "0"})

    def test_bootstrap_returns_success_for_existing_loaded_service(self) -> None:
        calls: list[list[str]] = []

        def fake_run(scope: str, args: list[str], **_kwargs):
            calls.append(args)
            return completed(returncode=0)

        with patch.object(launchd, "service_loaded", return_value=True), patch.object(
            launchd, "run_launchctl", side_effect=fake_run
        ):
            proc = launchd.bootstrap_service("agent", "com.example.worker", Path("/tmp/worker.plist"))

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(calls, [])

    def test_bootstrap_does_not_enable_after_success(self) -> None:
        calls: list[list[str]] = []

        def fake_run(scope: str, args: list[str], **_kwargs):
            calls.append(args)
            return completed(returncode=0)

        with patch.object(launchd, "service_loaded", return_value=False), patch.object(
            launchd, "run_launchctl", side_effect=fake_run
        ):
            proc = launchd.bootstrap_service("agent", "com.example.worker", Path("/tmp/worker.plist"))

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            calls,
            [["bootstrap", "gui/%s" % launchd.os.getuid(), "/tmp/worker.plist"]],
        )

    def test_bootstrap_enables_and_retries_disabled_service(self) -> None:
        calls: list[list[str]] = []

        def fake_run(scope: str, args: list[str], **_kwargs):
            calls.append(args)
            if len(calls) == 1:
                return completed(stderr="service is disabled", returncode=5)
            return completed(returncode=0)

        with patch.object(launchd, "service_loaded", return_value=False), patch.object(
            launchd, "run_launchctl", side_effect=fake_run
        ):
            proc = launchd.bootstrap_service("agent", "com.example.worker", Path("/tmp/worker.plist"))

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            calls,
            [
                ["bootstrap", "gui/%s" % launchd.os.getuid(), "/tmp/worker.plist"],
                ["enable", "gui/%s/com.example.worker" % launchd.os.getuid()],
                ["bootstrap", "gui/%s" % launchd.os.getuid(), "/tmp/worker.plist"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
