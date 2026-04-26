from __future__ import annotations

import types
import unittest

import skuld_linux_catalog as catalog
from skuld_linux_model import DiscoverableService, ManagedService, managed_service_key


def completed(stdout: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


class LinuxCatalogTest(unittest.TestCase):
    def test_list_discoverable_services_for_scope_pairs_services_and_timers(self) -> None:
        output = "\n".join(
            [
                "api.service enabled",
                "api.timer enabled",
                "bad name.service enabled",
                "worker.service disabled",
            ]
        )

        entries = catalog.list_discoverable_services_for_scope(
            "user",
            run=lambda cmd, **kwargs: completed(stdout=output),
            systemctl_command=lambda scope, args: ["systemctl", "--user", *args],
            systemd_scope_env=lambda scope: {"XDG_RUNTIME_DIR": "/run/user/1"},
        )

        self.assertEqual(
            [(item.scope, item.name, item.service_state, item.timer_state) for item in entries],
            [
                ("user", "api", "enabled", "enabled"),
                ("user", "worker", "disabled", "n/a"),
            ],
        )

    def test_list_discoverable_services_preserves_global_catalog_ids(self) -> None:
        system_entry = DiscoverableService(0, "system", "alpha", "enabled", "n/a")
        user_entry = DiscoverableService(0, "user", "alpha", "enabled", "enabled")
        beta_entry = DiscoverableService(0, "system", "beta", "enabled", "n/a")

        def list_scope(scope: str):
            if scope == "system":
                return [system_entry, beta_entry]
            if scope == "user":
                return [user_entry]
            return []

        entries = catalog.list_discoverable_services(
            "user",
            require_systemctl=lambda: None,
            list_scope=list_scope,
        )

        self.assertEqual([(item.index, item.scope, item.name) for item in entries], [
            (2, "user", "alpha"),
        ])

    def test_track_services_captures_systemd_metadata(self) -> None:
        saved = []
        messages = []
        entry = DiscoverableService(1, "user", "api", "enabled", "enabled")

        def systemctl_show(unit: str, props, **kwargs):
            if unit == "api.service":
                return {
                    "Description": "API",
                    "WorkingDirectory": "/srv/api",
                    "User": "rodrigo",
                    "Restart": "always",
                }
            return {"OnCalendar": "daily", "Persistent": "false"}

        catalog.track_services(
            ["1"],
            alias="api-alias",
            resolve_discoverable_targets=lambda targets: [entry],
            suggest_display_name=lambda name: name,
            prompt_display_name=lambda target, suggested: suggested,
            ensure_display_name_available=lambda name: None,
            get_managed=lambda name, **kwargs: None,
            systemctl_cat=lambda unit, **kwargs: "ExecStart=/bin/bash -lc '/usr/bin/api --flag'\n",
            systemctl_show=systemctl_show,
            unit_exists=lambda unit, **kwargs: unit == "api.timer",
            parse_bool=lambda value, default=True: value == "true",
            service_factory=ManagedService,
            upsert_registry=saved.append,
            ok=messages.append,
        )

        self.assertEqual(messages, ["Tracked 'user:api' as 'api-alias'."])
        self.assertEqual(saved[0].exec_cmd, "/usr/bin/api --flag")
        self.assertEqual(saved[0].schedule, "daily")
        self.assertFalse(saved[0].timer_persistent)
        self.assertEqual(managed_service_key(saved[0].name, saved[0].scope), ("user", "api"))


if __name__ == "__main__":
    unittest.main()
