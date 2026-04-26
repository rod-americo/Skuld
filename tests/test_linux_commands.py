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


if __name__ == "__main__":
    unittest.main()
