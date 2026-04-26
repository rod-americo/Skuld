from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import skuld_macos_registry as registry
from skuld_macos_model import ManagedService, normalize_service


def normalize_with_temp_paths(item: dict[str, object]) -> ManagedService:
    return normalize_service(
        item,
        log_dir_for_service=lambda name, scope: Path("/tmp/skuld") / scope / name,
        service_label=lambda name: f"io.skuld.{name}",
    )


class MacRegistryModuleTest(unittest.TestCase):
    def test_load_registry_creates_runtime_stats_and_normalizes_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_file = root / "services.json"
            runtime_stats_file = root / "runtime_stats.json"
            registry_file.write_text(
                json.dumps(
                    [
                        {"name": "com.example.worker", "exec_cmd": "/bin/worker", "description": "Worker", "id": 0}
                    ]
                ),
                encoding="utf-8",
            )

            [service] = registry.load_registry(
                root,
                registry_file,
                runtime_stats_file,
                normalize_item=normalize_with_temp_paths,
                write_back=True,
            )

            self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
            self.assertEqual(service.scope, "daemon")
            self.assertEqual(service.id, 1)
            self.assertTrue(runtime_stats_file.exists())

    def test_lookup_helpers_respect_name_display_name_and_id(self) -> None:
        services = [
            ManagedService("com.example.one", "/bin/one", "One", display_name="one", id=1),
            ManagedService("com.example.two", "/bin/two", "Two", display_name="two", id=2),
        ]
        load_registry = lambda: services

        self.assertEqual(registry.get_managed("com.example.one", load_registry=load_registry).id, 1)
        self.assertEqual(registry.get_managed_by_display_name("two", load_registry=load_registry).id, 2)
        self.assertEqual(registry.get_managed_by_id(2, load_registry=load_registry).name, "com.example.two")

    def test_remove_registry_removes_by_launchd_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_file = root / "services.json"
            runtime_stats_file = root / "runtime_stats.json"
            registry.save_registry(
                root,
                registry_file,
                runtime_stats_file,
                [
                    ManagedService("com.example.one", "/bin/one", "One", display_name="one", id=1),
                    ManagedService("com.example.two", "/bin/two", "Two", display_name="two", id=2),
                ],
                normalize_item=normalize_with_temp_paths,
            )

            registry.remove_registry(
                root,
                registry_file,
                runtime_stats_file,
                "com.example.two",
                normalize_item=normalize_with_temp_paths,
            )

            [service] = registry.load_registry(
                root,
                registry_file,
                runtime_stats_file,
                normalize_item=normalize_with_temp_paths,
            )
            self.assertEqual(service.name, "com.example.one")


if __name__ == "__main__":
    unittest.main()
