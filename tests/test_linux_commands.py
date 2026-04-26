from __future__ import annotations

import types
import unittest

import skuld_linux_commands as commands


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


if __name__ == "__main__":
    unittest.main()
