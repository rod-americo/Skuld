from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

import skuld_linux_systemd as systemd


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class LinuxSystemdAdapterTest(unittest.TestCase):
    def test_command_builders_honor_scope(self) -> None:
        self.assertEqual(systemd.systemctl_command("system", ["status", "demo.service"]), ["systemctl", "status", "demo.service"])
        self.assertEqual(systemd.systemctl_command("user", ["status", "demo.service"]), ["systemctl", "--user", "status", "demo.service"])
        self.assertEqual(systemd.journalctl_command("user", ["-u", "demo.service"]), ["journalctl", "--user", "-u", "demo.service"])

    def test_run_systemctl_action_uses_sudo_for_system_scope(self) -> None:
        with patch.object(systemd.common, "run_sudo_command", return_value=completed()) as run_sudo:
            systemd.run_systemctl_action("system", ["restart", "demo.service"], sudo_password="pw")

        run_sudo.assert_called_once_with(
            ["systemctl", "restart", "demo.service"],
            sudo_password="pw",
            check=True,
            capture=False,
        )

    def test_run_systemctl_action_uses_user_env_for_user_scope(self) -> None:
        with patch.object(systemd, "scope_env", return_value={"XDG_RUNTIME_DIR": "/run/user/1"}), patch.object(
            systemd.common, "run_command", return_value=completed()
        ) as run_command:
            systemd.run_systemctl_action("user", ["start", "demo.service"], check=False, capture=True)

        run_command.assert_called_once_with(
            ["systemctl", "--user", "start", "demo.service"],
            check=False,
            capture=True,
            env={"XDG_RUNTIME_DIR": "/run/user/1"},
        )

    def test_systemctl_show_parses_key_value_output(self) -> None:
        with patch.object(
            systemd.common,
            "run_command",
            return_value=completed(stdout="LoadState=loaded\nActiveState=active\nignored\n"),
        ):
            data = systemd.systemctl_show("demo.service", ["LoadState", "ActiveState"], scope="user")

        self.assertEqual(data, {"LoadState": "loaded", "ActiveState": "active"})


if __name__ == "__main__":
    unittest.main()
