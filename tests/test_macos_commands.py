from __future__ import annotations

import types
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
