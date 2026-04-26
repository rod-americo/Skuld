from __future__ import annotations

import types
import unittest
from unittest.mock import patch

import skuld_linux_commands as commands


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def service():
    return types.SimpleNamespace(
        id=1,
        name="api",
        scope="user",
        exec_cmd="/bin/api",
        description="API",
        display_name="api",
        schedule="daily",
        working_dir="/srv/api",
        user="",
        restart="on-failure",
        timer_persistent=True,
    )


class LinuxCommandsTest(unittest.TestCase):
    def test_renames_service_with_preserved_fields(self) -> None:
        saved = []
        messages = []

        commands.rename_service(
            service(),
            "worker",
            ensure_display_name_available=lambda name, current_id=None: messages.append(
                f"checked:{name}:{current_id}"
            ),
            service_factory=types.SimpleNamespace,
            upsert_registry=saved.append,
            info=messages.append,
            ok=messages.append,
        )

        self.assertEqual(messages, ["checked:worker:1", "Renamed 'api' to 'worker'."])
        self.assertEqual(saved[0].name, "api")
        self.assertEqual(saved[0].scope, "user")
        self.assertEqual(saved[0].display_name, "worker")
        self.assertEqual(saved[0].working_dir, "/srv/api")

    def test_rename_same_display_name_does_not_write(self) -> None:
        saved = []
        messages = []

        commands.rename_service(
            service(),
            "api",
            ensure_display_name_available=lambda name, current_id=None: None,
            service_factory=types.SimpleNamespace,
            upsert_registry=saved.append,
            info=messages.append,
            ok=messages.append,
        )

        self.assertEqual(saved, [])
        self.assertEqual(messages, ["No changes detected."])

    def test_untrack_removes_scoped_service(self) -> None:
        removed = []
        messages = []

        commands.untrack_service(
            service(),
            remove_registry=lambda name, scope: removed.append((name, scope)),
            ok=messages.append,
        )

        self.assertEqual(removed, [("api", "user")])
        self.assertEqual(messages, ["Removed 'api' from the skuld registry."])

    def test_doctor_reports_missing_expected_timer(self) -> None:
        output = []
        errors = []

        def unit_exists(unit: str, scope: str = "system") -> bool:
            return unit == "api.service"

        issues = commands.doctor_services(
            [service()],
            unit_exists=unit_exists,
            unit_active=lambda unit, scope="system": "active",
            display_unit_state=lambda state: state,
            read_timer_schedule=lambda name, scope="system": "",
            systemctl_cat=lambda unit, scope="system": "ExecStart=/bin/api\n",
            parse_unit_directives=lambda text: {"ExecStart": "/bin/api"},
            format_scoped_name=lambda name, scope: f"{scope}:{name}",
            ok=output.append,
            err=errors.append,
            emit=output.append,
        )

        self.assertEqual(issues, 1)
        self.assertIn("[api|user:api] service=active", output)
        self.assertIn(
            "[api|user:api] ERROR expected timer is missing (api.timer)",
            output,
        )
        self.assertEqual(errors, ["doctor: found 1 issue(s)."])

    def test_show_logs_emits_journal_output(self) -> None:
        calls = []
        output = []
        errors = []

        commands.show_logs(
            service(),
            timer=False,
            since="1 hour ago",
            follow=False,
            plain=True,
            output="short",
            lines=20,
            journalctl_command=lambda scope, args: ["journalctl", *args],
            systemd_scope_env=lambda scope: {"XDG_RUNTIME_DIR": "/run/user/1"},
            run=lambda cmd, **kwargs: calls.append((cmd, kwargs)) or completed(stdout="log line\n"),
            run_sudo=lambda cmd, **kwargs: completed(),
            journal_permission_hint=lambda stderr: False,
            emit=output.append,
            emit_err=errors.append,
        )

        self.assertEqual(output, ["log line"])
        self.assertEqual(errors, [])
        self.assertEqual(calls[0][0][:3], ["journalctl", "-u", "api.service"])
        self.assertIn("--since", calls[0][0])

    def test_show_status_runs_service_and_timer_status(self) -> None:
        calls = []
        output = []

        commands.show_status(
            service(),
            format_scoped_name=lambda name, scope: f"{scope}:{name}",
            systemd_scope_env=lambda scope: {"XDG_RUNTIME_DIR": "/run/user/1"},
            systemctl_command=lambda scope, args: ["systemctl", "--user", *args],
            run=lambda cmd, **kwargs: calls.append((cmd, kwargs)),
            emit=output.append,
        )

        self.assertEqual(output, ["[skuld] api -> user:api"])
        self.assertEqual(
            calls[0][0],
            ["systemctl", "--user", "status", "api.service", "--no-pager"],
        )
        self.assertEqual(
            calls[1][0],
            ["systemctl", "--user", "status", "api.timer", "--no-pager"],
        )

    def test_show_stats_formats_runtime_counts(self) -> None:
        output = []

        with patch("skuld_linux_presenters.print_lines", side_effect=output.extend):
            commands.show_stats(
                service(),
                since="1 hour ago",
                boot=False,
                sync_registry_from_systemd=lambda service: 0,
                count_unit_starts=lambda unit, **kwargs: 4,
                read_restart_count=lambda name, **kwargs: "2",
                format_scoped_name=lambda name, scope: f"{scope}:{name}",
            )

        self.assertIn("window: since 1 hour ago", output)
        self.assertIn("executions: 4", output)
        self.assertIn("restarts: 2", output)

    def test_describe_service_formats_systemd_show_maps(self) -> None:
        output = []

        def systemctl_show(unit: str, props, **kwargs):
            if unit == "api.service":
                return {
                    "ActiveState": "active",
                    "SubState": "running",
                    "MainPID": "123",
                    "FragmentPath": "/etc/systemd/user/api.service",
                }
            return {
                "ActiveState": "active",
                "SubState": "waiting",
                "NextElapseUSecRealtime": "Mon 2026-04-27 09:00:00",
                "LastTriggerUSec": "Sun 2026-04-26 09:00:00",
            }

        with patch("skuld_linux_presenters.print_lines", side_effect=output.extend):
            commands.describe_service(
                service(),
                require_managed=lambda name, **kwargs: service(),
                unit_exists=lambda unit, **kwargs: unit == "api.timer",
                systemctl_show=systemctl_show,
                format_scoped_name=lambda name, scope: f"{scope}:{name}",
            )

        self.assertIn("target: user:api", output)
        self.assertIn("service_active: active", output)
        self.assertIn("main_pid: 123", output)
        self.assertIn("timer_active: active", output)
        self.assertIn("next_run: Mon 2026-04-27 09:00:00", output)


if __name__ == "__main__":
    unittest.main()
