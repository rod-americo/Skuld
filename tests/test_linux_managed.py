from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path

from skuld import skuld_linux_managed as managed


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class LinuxManagedServicesTest(unittest.TestCase):
    def test_create_user_service_writes_unit_registers_and_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            saved = []
            messages = []

            service = managed.create_user_service(
                name="api",
                command=["python", "app.py"],
                working_dir=str(root),
                service_factory=types.SimpleNamespace,
                validate_name=lambda name: calls.append(("validate", name)),
                ensure_display_name_available=lambda name: calls.append(("display", name)),
                get_managed=lambda name, scope=None: None,
                unit_exists=lambda unit, scope="system": False,
                run_systemctl_action=lambda scope, args, **kwargs: (
                    calls.append((scope, args, kwargs)) or completed()
                ),
                upsert_registry=saved.append,
                ok=messages.append,
                unit_path_for_name=lambda name: root / f"{name}.service",
            )

            unit_text = (root / "api.service").read_text(encoding="utf-8")

        self.assertEqual(service.name, "api")
        self.assertTrue(service.managed_by_skuld)
        self.assertEqual(saved[0].display_name, "api")
        self.assertIn("ExecStart=/bin/sh -lc", unit_text)
        self.assertIn("python app.py", unit_text)
        self.assertIn(("user", ["daemon-reload"], {}), calls)
        self.assertIn(("user", ["start", "api.service"], {"check": False, "capture": True}), calls)
        self.assertEqual(messages, ["Created and started Skuld-managed user service 'api'."])

    def test_create_user_service_refuses_existing_unit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            managed.create_user_service(
                name="api",
                command=["python", "app.py"],
                working_dir=None,
                service_factory=types.SimpleNamespace,
                validate_name=lambda name: None,
                ensure_display_name_available=lambda name: None,
                get_managed=lambda name, scope=None: None,
                unit_exists=lambda unit, scope="system": True,
                run_systemctl_action=lambda scope, args, **kwargs: completed(),
                upsert_registry=lambda service: None,
                ok=lambda message: None,
            )

    def test_delete_user_service_requires_skuld_managed_user_scope(self) -> None:
        external = types.SimpleNamespace(
            name="api",
            scope="user",
            display_name="api",
            managed_by_skuld=False,
        )

        with self.assertRaisesRegex(RuntimeError, "externally tracked"):
            managed.delete_user_service(
                external,
                remove_registry=lambda name, scope: None,
                run_systemctl_action=lambda scope, args, **kwargs: completed(),
                ok=lambda message: None,
            )

    def test_delete_user_service_removes_unit_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = root / "api.service"
            unit.write_text("[Service]\n", encoding="utf-8")
            calls = []
            removed = []
            messages = []
            service = types.SimpleNamespace(
                name="api",
                scope="user",
                display_name="api",
                managed_by_skuld=True,
            )

            managed.delete_user_service(
                service,
                remove_registry=lambda name, scope: removed.append((name, scope)),
                run_systemctl_action=lambda scope, args, **kwargs: (
                    calls.append((scope, args, kwargs)) or completed()
                ),
                ok=messages.append,
                unit_path_for_name=lambda name: unit,
            )

            self.assertFalse(unit.exists())

        self.assertEqual(removed, [("api", "user")])
        self.assertIn(("user", ["stop", "api.service"], {"check": False, "capture": True}), calls)
        self.assertIn(("user", ["daemon-reload"], {"check": False, "capture": True}), calls)
        self.assertEqual(messages, ["Deleted Skuld-managed user service 'api'."])


if __name__ == "__main__":
    unittest.main()
