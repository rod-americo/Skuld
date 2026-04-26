from __future__ import annotations

import unittest
from pathlib import Path

import skuld_macos_model as model


class MacosModelTest(unittest.TestCase):
    def test_normalize_service_uses_runtime_log_dir_for_managed_entries(self) -> None:
        service = model.normalize_service(
            {
                "name": "com.example.worker",
                "exec_cmd": "/bin/worker",
                "description": "Worker",
                "managed_by_skuld": "true",
                "scope": "agent",
            },
            log_dir_for_service=lambda name, scope: Path("/tmp/skuld") / scope / name,
            service_label=lambda name: f"io.skuld.{name}",
        )

        self.assertEqual(service.name, "com.example.worker")
        self.assertEqual(service.scope, "agent")
        self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
        self.assertEqual(service.log_dir, "/tmp/skuld/agent/com.example.worker")

    def test_normalize_service_keeps_external_entries_without_log_dir_default(self) -> None:
        service = model.normalize_service(
            {
                "name": "com.example.worker",
                "exec_cmd": "/bin/worker",
                "description": "Worker",
                "managed_by_skuld": "false",
            },
            log_dir_for_service=lambda name, scope: Path("/tmp/skuld") / scope / name,
            service_label=lambda name: f"io.skuld.{name}",
        )

        self.assertFalse(service.managed_by_skuld)
        self.assertEqual(service.scope, "daemon")
        self.assertEqual(service.log_dir, "")

    def test_validate_registry_service_rejects_agent_user(self) -> None:
        service = model.ManagedService(
            "com.example.worker",
            "/bin/worker",
            "Worker",
            display_name="worker",
            scope="agent",
            user="root",
        )

        with self.assertRaisesRegex(RuntimeError, "'user' is only valid"):
            model.validate_registry_service(service, 1)

    def test_suggest_display_name_uses_label_tokens(self) -> None:
        self.assertEqual(model.suggest_display_name("application.com.example.worker.123"), "worker")
        self.assertEqual(model.suggest_display_name("com.example.desktop"), "example-desktop")
        self.assertEqual(model.suggest_display_name("single"), "single")


if __name__ == "__main__":
    unittest.main()
