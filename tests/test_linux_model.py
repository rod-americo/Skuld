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

    def test_normalize_service_name_strips_unit_suffixes(self) -> None:
        self.assertEqual(model.normalize_service_name("api.service"), "api")
        self.assertEqual(model.normalize_service_name("backup.timer"), "backup")

    def test_normalize_target_token_preserves_scoped_name_contract(self) -> None:
        self.assertEqual(model.normalize_target_token("user:api.service"), ("user", "api"))
        self.assertEqual(model.normalize_target_token("api.service"), (None, "api"))

    def test_suggest_display_name_uses_last_meaningful_tokens(self) -> None:
        self.assertEqual(model.suggest_display_name("com.example.worker.123.service"), "example-worker")
        self.assertEqual(model.suggest_display_name("postgres.service"), "postgres")

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
