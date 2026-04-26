from __future__ import annotations

import subprocess
import unittest
from argparse import Namespace

import skuld_sudo


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class SudoCommandTest(unittest.TestCase):
    def test_sudo_check_uses_password_when_available(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []
        messages: list[str] = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed()

        skuld_sudo.sudo_check(
            get_sudo_password=lambda: "secret",
            run=run,
            info=messages.append,
            ok=messages.append,
        )

        self.assertEqual(calls[0][0], ["sudo", "-S", "-k", "-p", "", "true"])
        self.assertEqual(calls[0][1]["input_text"], "secret\n")
        self.assertIn("SKULD_SUDO_PASSWORD", messages[0])
        self.assertEqual(messages[-1], "sudo is available.")

    def test_sudo_check_uses_non_interactive_sudo_without_password(self) -> None:
        calls: list[list[str]] = []

        def run(cmd, **_kwargs):
            calls.append(cmd)
            return completed()

        skuld_sudo.sudo_check(
            get_sudo_password=lambda: "",
            run=run,
            info=lambda _message: None,
            ok=lambda _message: None,
        )

        self.assertEqual(calls, [["sudo", "-n", "true"]])

    def test_sudo_check_raises_with_command_details(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "skuld sudo auth.*password required"):
            skuld_sudo.sudo_check(
                get_sudo_password=lambda: "",
                run=lambda *_args, **_kwargs: completed(stderr="password required", returncode=1),
                info=lambda _message: None,
                ok=lambda _message: None,
            )

    def test_sudo_auth_refreshes_native_timestamp(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []
        messages: list[str] = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed()

        skuld_sudo.sudo_auth(run=run, ok=messages.append)

        self.assertEqual(calls, [(["sudo", "-v"], {"check": False})])
        self.assertEqual(messages, ["sudo credentials cached by the native sudo timestamp."])

    def test_sudo_auth_raises_on_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "authentication failed"):
            skuld_sudo.sudo_auth(
                run=lambda *_args, **_kwargs: completed(returncode=1),
                ok=lambda _message: None,
            )

    def test_sudo_forget_invalidates_native_timestamp(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []
        messages: list[str] = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed()

        skuld_sudo.sudo_forget(run=run, ok=messages.append)

        self.assertEqual(calls, [(["sudo", "-k"], {"check": False, "capture": True})])
        self.assertEqual(messages, ["sudo timestamp invalidated."])

    def test_sudo_run_command_strips_separator_and_runs_command(self) -> None:
        calls: list[list[str]] = []

        def run_sudo(cmd, **_kwargs):
            calls.append(cmd)
            return completed()

        skuld_sudo.sudo_run_command(
            Namespace(command=["--", "id", "-u"]),
            get_sudo_password=lambda: "",
            run_sudo=run_sudo,
            info=lambda _message: None,
        )

        self.assertEqual(calls, [["id", "-u"]])

    def test_sudo_run_command_rejects_empty_command(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "skuld sudo run"):
            skuld_sudo.sudo_run_command(
                Namespace(command=[]),
                get_sudo_password=lambda: "",
                run_sudo=lambda *_args, **_kwargs: completed(),
                info=lambda _message: None,
            )

    def test_sudo_run_command_raises_on_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exit code 7.*skuld sudo auth"):
            skuld_sudo.sudo_run_command(
                Namespace(command=["id"]),
                get_sudo_password=lambda: "",
                run_sudo=lambda *_args, **_kwargs: completed(returncode=7),
                info=lambda _message: None,
            )


if __name__ == "__main__":
    unittest.main()
