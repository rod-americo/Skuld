from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path

import skuld_macos_paths as paths


@dataclass
class Service:
    name: str
    scope: str = "agent"
    launchd_label: str = ""
    plist_path_hint: str = ""


class MacPathsTest(unittest.TestCase):
    def test_launchd_label_uses_existing_label_or_skuld_prefix(self) -> None:
        self.assertEqual(paths.launchd_label_for_service(Service("api")), "io.skuld.api")
        self.assertEqual(
            paths.launchd_label_for_service(Service("api", launchd_label="com.example.api")),
            "com.example.api",
        )

    def test_plist_path_uses_hint_agent_or_daemon_scope(self) -> None:
        home = Path("/Users/example")

        self.assertEqual(
            paths.plist_path_for_service(Service("api", plist_path_hint="/tmp/api.plist"), user_home=home),
            Path("/tmp/api.plist"),
        )
        self.assertEqual(
            paths.plist_path_for_service(Service("api"), user_home=home),
            home / "Library/LaunchAgents/io.skuld.api.plist",
        )
        self.assertEqual(
            paths.plist_path_for_service(Service("api", scope="daemon"), user_home=home),
            Path("/Library/LaunchDaemons/io.skuld.api.plist"),
        )

    def test_agent_runtime_paths_live_under_skuld_home(self) -> None:
        root = Path("/tmp/skuld")

        self.assertEqual(paths.jobs_root_for_scope("agent", skuld_home=root), root / "jobs")
        self.assertEqual(paths.logs_root_for_scope("agent", skuld_home=root), root / "logs")
        self.assertEqual(paths.events_root_for_scope("agent", skuld_home=root), root / "events")
        self.assertEqual(paths.log_dir_for_service("api", "agent", skuld_home=root), root / "logs/api")
        self.assertEqual(paths.event_file_for_service("api", "agent", skuld_home=root), root / "events/api.jsonl")
        self.assertEqual(paths.wrapper_script_for_service("api", "agent", skuld_home=root), root / "jobs/api.sh")

    def test_daemon_runtime_paths_live_under_library_application_support(self) -> None:
        root = Path("/tmp/skuld")

        self.assertEqual(
            paths.jobs_root_for_scope("daemon", skuld_home=root),
            Path("/Library/Application Support/skuld/jobs"),
        )
        self.assertEqual(
            paths.logs_root_for_scope("daemon", skuld_home=root),
            Path("/Library/Application Support/skuld/logs"),
        )
        self.assertEqual(
            paths.events_root_for_scope("daemon", skuld_home=root),
            Path("/Library/Application Support/skuld/events"),
        )


if __name__ == "__main__":
    unittest.main()
