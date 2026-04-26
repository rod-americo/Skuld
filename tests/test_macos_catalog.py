from __future__ import annotations

import types
import unittest

import skuld_macos_catalog as catalog
from skuld_macos_model import DiscoverableService, ManagedService


def completed(stdout: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


class MacosCatalogTest(unittest.TestCase):
    def test_discover_launchd_services_parses_list_output(self) -> None:
        output = "\n".join(
            [
                "PID\tStatus\tLabel",
                "123\t0\tcom.example.worker",
                "-\t1\tcom.example.stopped",
            ]
        )

        entries = catalog.discover_launchd_services(
            run=lambda cmd, **kwargs: completed(stdout=output),
        )

        self.assertEqual(
            [(item.index, item.label, item.pid, item.status) for item in entries],
            [
                (1, "com.example.stopped", "-", "1"),
                (2, "com.example.worker", "123", "0"),
            ],
        )

    def test_render_discoverable_services_hint_renders_all_catalog_entries(self) -> None:
        output = []
        entries = [
            DiscoverableService(1, "com.example.worker", "123", "0"),
            DiscoverableService(2, "com.example.helper", "-", "1"),
        ]

        catalog.render_discoverable_services_hint(
            discover_launchd_services=lambda: entries,
            emit=output.append,
        )

        self.assertIn("No services tracked by skuld.", output)
        self.assertIn("  1. com.example.worker  pid=123 status=0", output)
        self.assertIn("  2. com.example.helper  pid=- status=1", output)

    def test_render_discoverable_services_hint_filters_by_grep(self) -> None:
        output = []
        entries = [
            DiscoverableService(7, "com.example.worker", "123", "0"),
            DiscoverableService(8, "org.example.helper", "-", "1"),
        ]

        catalog.render_discoverable_services_hint(
            discover_launchd_services=lambda: entries,
            grep="worker",
            emit=output.append,
        )

        self.assertIn("  7. com.example.worker  pid=123 status=0", output)
        self.assertNotIn("  8. org.example.helper  pid=- status=1", output)

    def test_render_discoverable_services_hint_reports_empty_grep_match(self) -> None:
        output = []

        catalog.render_discoverable_services_hint(
            discover_launchd_services=lambda: [DiscoverableService(7, "com.example.worker", "123", "0")],
            grep="missing",
            emit=output.append,
        )

        self.assertEqual(
            output,
            [
                "No services tracked by skuld.",
                "No launchd services matched grep 'missing' in the current session.",
            ],
        )

    def test_track_services_captures_launchd_metadata_as_external_job(self) -> None:
        saved = []
        messages = []
        entry = DiscoverableService(1, "com.example.worker", "123", "0")
        raw = """
        path = /Users/me/Library/LaunchAgents/com.example.worker.plist
        program = /usr/bin/worker
        state = running
        """

        def extract_value(text: str, key: str) -> str:
            for line in text.splitlines():
                clean = line.strip()
                if clean.startswith(f"{key} = "):
                    return clean.split(" = ", 1)[1]
            return ""

        catalog.track_services(
            ["1"],
            alias="worker",
            resolve_discoverable_targets=lambda targets: [entry],
            suggest_display_name=lambda label: "worker",
            prompt_display_name=lambda target, suggested: suggested,
            ensure_display_name_available=lambda name: None,
            get_managed=lambda label: None,
            launchctl_print_service_raw=lambda label: raw,
            extract_launchctl_value=extract_value,
            service_factory=ManagedService,
            upsert_registry=saved.append,
            ok=messages.append,
        )

        self.assertEqual(messages, ["Tracked 'com.example.worker' as 'worker'."])
        self.assertEqual(saved[0].name, "com.example.worker")
        self.assertEqual(saved[0].exec_cmd, "/usr/bin/worker")
        self.assertEqual(
            saved[0].plist_path_hint,
            "/Users/me/Library/LaunchAgents/com.example.worker.plist",
        )
        self.assertFalse(saved[0].managed_by_skuld)
        self.assertEqual(saved[0].scope, "agent")


if __name__ == "__main__":
    unittest.main()
