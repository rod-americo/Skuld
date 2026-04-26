from __future__ import annotations

import types
import unittest
from pathlib import Path
from unittest.mock import patch

import skuld_macos_commands as commands


def service():
    return types.SimpleNamespace(
        id=1,
        name="com.example.worker",
        exec_cmd="/bin/worker",
        description="Worker",
        display_name="worker",
        launchd_label="com.example.worker",
        plist_path_hint="/tmp/worker.plist",
        managed_by_skuld=False,
        schedule="daily",
        working_dir="/srv/worker",
        user="",
        restart="on-failure",
        timer_persistent=True,
        backend="launchd",
        scope="agent",
        log_dir="",
    )


class MacosCommandsTest(unittest.TestCase):
    def test_renames_service_with_preserved_fields(self) -> None:
        saved = []
        messages = []

        commands.rename_service(
            service(),
            "api",
            ensure_display_name_available=lambda name, current_name=None: messages.append(
                f"checked:{name}:{current_name}"
            ),
            service_factory=types.SimpleNamespace,
            upsert_registry=saved.append,
            info=messages.append,
            ok=messages.append,
        )

        self.assertEqual(
            messages,
            ["checked:api:com.example.worker", "Renamed 'worker' to 'api'."],
        )
        self.assertEqual(saved[0].name, "com.example.worker")
        self.assertEqual(saved[0].display_name, "api")
        self.assertEqual(saved[0].launchd_label, "com.example.worker")
        self.assertFalse(saved[0].managed_by_skuld)

    def test_rename_same_display_name_does_not_write(self) -> None:
        saved = []
        messages = []

        commands.rename_service(
            service(),
            "worker",
            ensure_display_name_available=lambda name, current_name=None: None,
            service_factory=types.SimpleNamespace,
            upsert_registry=saved.append,
            info=messages.append,
            ok=messages.append,
        )

        self.assertEqual(saved, [])
        self.assertEqual(messages, ["No changes detected."])

    def test_untrack_removes_launchd_label(self) -> None:
        removed = []
        messages = []

        commands.untrack_service(
            service(),
            remove_registry=removed.append,
            ok=messages.append,
        )

        self.assertEqual(removed, ["com.example.worker"])
        self.assertEqual(messages, ["Removed 'worker' from the skuld registry."])

    def test_doctor_reports_missing_plist_and_wrapper(self) -> None:
        output = []
        errors = []

        item = service()
        item.managed_by_skuld = True

        issues = commands.doctor_services(
            [item],
            plist_path_for_service=lambda service: Path("/tmp/missing.plist"),
            wrapper_script_for_service=lambda name, scope: Path("/tmp/missing-wrapper"),
            service_loaded=lambda service: False,
            ok=output.append,
            err=errors.append,
            emit=output.append,
        )

        self.assertEqual(issues, 2)
        self.assertIn(
            "[worker|com.example.worker] ERROR missing plist (/tmp/missing.plist)",
            output,
        )
        self.assertIn("[worker|com.example.worker] loaded=no", output)
        self.assertEqual(errors, ["doctor: found 2 issue(s)."])

    def test_show_logs_rejects_missing_log_paths(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Logs are only available"):
            commands.show_logs(
                service(),
                since="",
                timer=False,
                follow=False,
                lines=100,
                log_paths_for_service=lambda service: (None, None),
                tail_file=lambda path, lines, follow: None,
                info=lambda message: None,
            )

    def test_show_logs_tails_existing_stdout_path(self) -> None:
        output = []
        tailed = []

        commands.show_logs(
            service(),
            since="",
            timer=True,
            follow=False,
            lines=25,
            log_paths_for_service=lambda service: (Path("/tmp"), None),
            tail_file=lambda path, lines, follow: tailed.append((path, lines, follow)),
            info=output.append,
            emit=output.append,
        )

        self.assertEqual(
            output,
            [
                "--timer has no effect on macOS. launchd uses a single plist/job.",
                "==> /tmp",
            ],
        )
        self.assertEqual(tailed, [(Path("/tmp"), 25, False)])

    def test_show_status_formats_launchd_info(self) -> None:
        output = []

        with patch("skuld_macos_presenters.print_lines", side_effect=output.extend):
            commands.show_status(
                service(),
                launchd_label_for_service=lambda service: service.launchd_label,
                domain_target=lambda scope: f"gui/501/{scope}",
                launchctl_service_info=lambda service: {
                    "PID": "123",
                    "LastExitStatus": "0",
                },
                plist_path_for_service=lambda service: Path("/tmp/worker.plist"),
            )

        self.assertIn("target: com.example.worker", output)
        self.assertIn("domain: gui/501/agent", output)
        self.assertIn("loaded: yes", output)
        self.assertIn("pid: 123", output)

    def test_show_stats_formats_runtime_stats(self) -> None:
        output = []

        with patch("skuld_macos_presenters.print_lines", side_effect=output.extend):
            commands.show_stats(
                service(),
                update_runtime_stats=lambda service: {
                    service.name: {
                        "executions": 3,
                        "restarts": 1,
                        "last_run": "2026-04-26T10:00:00Z",
                        "last_exit_status": "0",
                    }
                },
            )

        self.assertIn("window: all retained event entries", output)
        self.assertIn("executions: 3", output)
        self.assertIn("restarts: 1", output)
        self.assertIn("last_exit_status: 0", output)

    def test_describe_service_formats_launchd_info_and_stats(self) -> None:
        output = []

        with patch("skuld_macos_presenters.print_lines", side_effect=output.extend):
            commands.describe_service(
                service(),
                launchctl_service_info=lambda service: {
                    "PID": "123",
                    "LastExitStatus": "0",
                },
                read_event_stats=lambda service: {
                    "last_run": "2026-04-26T10:00:00Z",
                },
                compute_next_run=lambda schedule: "2026-04-27 09:00:00",
                plist_path_for_service=lambda service: Path("/tmp/worker.plist"),
            )

        self.assertIn("target: com.example.worker", output)
        self.assertIn("loaded: yes", output)
        self.assertIn("pid: 123", output)
        self.assertIn("next_run: 2026-04-27 09:00:00", output)
        self.assertIn("last_run: 2026-04-26T10:00:00Z", output)


if __name__ == "__main__":
    unittest.main()
