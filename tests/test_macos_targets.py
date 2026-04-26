from __future__ import annotations

import argparse
import types
import unittest

import skuld_macos_targets as targets


def service(service_id: int, name: str, *, display_name: str = ""):
    return types.SimpleNamespace(
        id=service_id,
        name=name,
        display_name=display_name or name,
    )


def discoverable(index: int, label: str):
    return types.SimpleNamespace(index=index, label=label)


class MacosTargetResolutionTest(unittest.TestCase):
    def test_resolves_name_argument_conflicts(self) -> None:
        args = argparse.Namespace(name="api", name_flag="worker")

        with self.assertRaisesRegex(RuntimeError, "Conflicting names"):
            targets.resolve_name_arg(args)

    def test_rejects_duplicate_display_name(self) -> None:
        existing = service(1, "com.example.worker", display_name="worker")

        with self.assertRaisesRegex(RuntimeError, "already in use"):
            targets.ensure_display_name_available(
                "worker",
                current_name=None,
                validate_name=lambda name: None,
                load_registry=lambda: [existing],
            )

    def test_resolves_managed_targets_without_duplicates(self) -> None:
        worker = service(1, "com.example.worker", display_name="worker")
        helper = service(2, "com.example.helper", display_name="helper")
        by_token = {
            "com.example.worker": worker,
            "worker": worker,
            "1": worker,
            "helper": helper,
        }

        resolved = targets.resolve_managed_many_arg(
            argparse.Namespace(targets=["worker", "1"], name_flag="helper", id_flag=None),
            resolve_managed_from_token=lambda token: by_token[token],
        )

        self.assertEqual(resolved, [worker, helper])

    def test_resolves_discoverable_targets_without_duplicates(self) -> None:
        worker = discoverable(1, "com.example.worker")
        helper = discoverable(2, "com.example.helper")

        resolved = targets.resolve_discoverable_targets(
            ["1", "com.example.worker", "com.example.helper"],
            discover_launchd_services=lambda: [worker, helper],
        )

        self.assertEqual(resolved, [worker, helper])


if __name__ == "__main__":
    unittest.main()
