from __future__ import annotations

import unittest

import skuld_linux_sync as sync
from skuld_linux_model import ManagedService, managed_service_key


class LinuxSyncTest(unittest.TestCase):
    def test_sync_backfills_systemd_service_and_timer_metadata(self) -> None:
        saved = []
        service = ManagedService("api", "user", "", "", "api")

        def unit_exists(unit: str, **kwargs) -> bool:
            return unit in {"api.service", "api.timer"}

        def systemctl_show(unit: str, props, **kwargs):
            if unit == "api.service":
                return {
                    "Description": "API",
                    "WorkingDirectory": "/srv/api",
                    "User": "rodrigo",
                    "Restart": "always",
                }
            return {}

        changed = sync.sync_registry_from_systemd(
            None,
            load_registry=lambda **kwargs: [service],
            save_registry=saved.append,
            managed_service_key=managed_service_key,
            unit_exists=unit_exists,
            systemctl_show=systemctl_show,
            read_timer_schedule=lambda name, **kwargs: "daily",
            read_timer_persistent=lambda name, **kwargs: False,
        )

        self.assertEqual(changed, 1)
        [updated] = saved[0]
        self.assertEqual(updated.description, "API")
        self.assertEqual(updated.working_dir, "/srv/api")
        self.assertEqual(updated.user, "rodrigo")
        self.assertEqual(updated.restart, "always")
        self.assertEqual(updated.schedule, "daily")
        self.assertFalse(updated.timer_persistent)

    def test_sync_does_not_write_when_target_is_unchanged(self) -> None:
        saved = []
        service = ManagedService("api", "user", "/bin/api", "API", "api")

        changed = sync.sync_registry_from_systemd(
            service,
            load_registry=lambda **kwargs: [service],
            save_registry=saved.append,
            managed_service_key=managed_service_key,
            unit_exists=lambda unit, **kwargs: False,
            systemctl_show=lambda unit, props, **kwargs: {},
            read_timer_schedule=lambda name, **kwargs: "",
            read_timer_persistent=lambda name, **kwargs: True,
        )

        self.assertEqual(changed, 0)
        self.assertEqual(saved, [])


if __name__ == "__main__":
    unittest.main()
