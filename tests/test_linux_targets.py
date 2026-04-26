from __future__ import annotations

import argparse
import types
import unittest

import skuld_linux_targets as targets


def service(
    service_id: int,
    name: str,
    *,
    scope: str = "system",
    display_name: str = "",
):
    return types.SimpleNamespace(
        id=service_id,
        name=name,
        scope=scope,
        display_name=display_name or name,
    )


class LinuxTargetResolutionTest(unittest.TestCase):
    def test_resolves_name_argument_conflicts(self) -> None:
        args = argparse.Namespace(name="api", name_flag="worker")

        with self.assertRaisesRegex(RuntimeError, "Conflicting names"):
            targets.resolve_name_arg(args)

    def test_rejects_duplicate_display_name(self) -> None:
        existing = service(1, "api", display_name="api")

        with self.assertRaisesRegex(RuntimeError, "already in use"):
            targets.ensure_display_name_available(
                "api",
                current_id=None,
                validate_name=lambda name: None,
                load_registry=lambda: [existing],
            )

    def test_allows_current_service_display_name(self) -> None:
        existing = service(1, "api", display_name="api")

        targets.ensure_display_name_available(
            "api",
            current_id=1,
            validate_name=lambda name: None,
            load_registry=lambda: [existing],
        )

    def test_resolves_ambiguous_name_error_with_scoped_choices(self) -> None:
        entries = [
            service(1, "api", scope="system"),
            service(2, "api", scope="user"),
        ]

        with self.assertRaisesRegex(RuntimeError, "system:api, user:api"):
            targets.resolve_managed_from_token(
                "api",
                get_managed_by_display_name=lambda name: None,
                get_managed_by_id=lambda service_id: None,
                normalize_target_token=lambda token: (None, token),
                get_managed=lambda name, scope: None,
                find_managed_by_name=lambda name: entries,
                format_scoped_name=lambda name, scope: f"{scope}:{name}",
                managed_sort_key=lambda item: (item.scope, item.name),
            )

    def test_resolves_many_targets_without_duplicates(self) -> None:
        api = service(1, "api")
        worker = service(2, "worker")
        by_token = {"api": api, "1": api, "worker": worker}

        resolved = targets.resolve_managed_many_arg(
            argparse.Namespace(targets=["api", "1"], name_flag="worker", id_flag=None),
            resolve_managed_from_token=lambda token: by_token[token],
        )

        self.assertEqual(resolved, [api, worker])


if __name__ == "__main__":
    unittest.main()
