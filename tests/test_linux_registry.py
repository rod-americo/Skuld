from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import skuld_linux_registry as registry
from skuld_linux_model import ManagedService


class LinuxRegistryModuleTest(unittest.TestCase):
    def test_load_registry_normalizes_scope_ids_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_file = root / "services.json"
            registry_file.write_text(
                json.dumps(
                    [
                        {"name": "beta", "scope": "root", "exec_cmd": "/bin/b", "description": "B"},
                        {"name": "alpha", "scope": "user", "exec_cmd": "/bin/a", "description": "A", "id": 0},
                    ]
                ),
                encoding="utf-8",
            )

            services = registry.load_registry(root, registry_file, write_back=True)

            self.assertEqual([(item.name, item.scope, item.id) for item in services], [
                ("alpha", "user", 2),
                ("beta", "system", 1),
            ])
            self.assertTrue(registry_file.read_text(encoding="utf-8").endswith("\n"))

    def test_lookup_helpers_respect_scope_display_name_and_id(self) -> None:
        services = [
            ManagedService("api", "system", "/bin/api", "API", display_name="api-system", id=1),
            ManagedService("api", "user", "/bin/api", "API", display_name="api-user", id=2),
        ]
        load_registry = lambda: services

        self.assertIsNone(registry.get_managed("api", load_registry=load_registry))
        self.assertEqual(registry.get_managed("api", scope="user", load_registry=load_registry).id, 2)
        self.assertEqual(
            registry.get_managed_by_display_name("api-system", load_registry=load_registry).scope,
            "system",
        )
        self.assertEqual(registry.get_managed_by_id(2, load_registry=load_registry).scope, "user")

    def test_require_managed_keeps_registry_boundary_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Only services tracked by skuld"):
            registry.require_managed("missing", get_managed=lambda *_args, **_kwargs: None)

    def test_remove_registry_uses_scoped_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_file = root / "services.json"
            registry.save_registry(
                root,
                registry_file,
                [
                    ManagedService("api", "system", "/bin/api", "API", display_name="api-system", id=1),
                    ManagedService("api", "user", "/bin/api", "API", display_name="api-user", id=2),
                ],
            )

            registry.remove_registry(root, registry_file, "api", "user")

            [service] = registry.load_registry(root, registry_file)
            self.assertEqual((service.name, service.scope), ("api", "system"))


if __name__ == "__main__":
    unittest.main()
