from __future__ import annotations

import unittest

import skuld_linux_model as model


class LinuxModelTest(unittest.TestCase):
    def test_normalize_registry_item_preserves_linux_contract(self) -> None:
        service = model.normalize_registry_item(
            {
                "name": "worker",
                "scope": "root",
                "exec_cmd": "/bin/worker",
                "description": "Worker",
                "timer_persistent": "false",
            }
        )

        self.assertEqual(service.name, "worker")
        self.assertEqual(service.scope, "system")
        self.assertEqual(service.display_name, "worker")
        self.assertFalse(service.timer_persistent)

    def test_split_scope_token_accepts_scope_aliases(self) -> None:
        self.assertEqual(model.split_scope_token("root:worker"), ("system", "worker"))
        self.assertEqual(model.split_scope_token("worker"), (None, "worker"))

    def test_validate_registry_service_rejects_invalid_display_name(self) -> None:
        service = model.ManagedService(
            "worker",
            "system",
            "/bin/worker",
            "Worker",
            display_name="bad name",
        )

        with self.assertRaisesRegex(ValueError, "Invalid name"):
            model.validate_registry_service(service, 1)


if __name__ == "__main__":
    unittest.main()
