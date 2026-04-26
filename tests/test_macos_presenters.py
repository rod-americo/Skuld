from __future__ import annotations

import types
import unittest
from pathlib import Path

import skuld_macos_presenters as presenters


def service():
    return types.SimpleNamespace(
        display_name="worker",
        name="com.example.worker",
        scope="agent",
        description="Worker",
        exec_cmd="/bin/worker",
        user="",
        working_dir="",
        restart="on-failure",
        schedule="daily",
        timer_persistent=True,
        log_dir="",
    )


class MacosPresentersTest(unittest.TestCase):
    def test_formats_status_lines_for_unloaded_job(self) -> None:
        self.assertEqual(
            presenters.status_lines(
                service(),
                label="com.example.worker",
                domain="gui/501",
                info_map={},
                plist_path=Path("/tmp/worker.plist"),
            ),
            [
                "name: worker",
                "target: com.example.worker",
                "label: com.example.worker",
                "scope: agent",
                "domain: gui/501",
                "loaded: no",
                "pid: -",
                "last_exit_status: -",
                "plist: /tmp/worker.plist",
            ],
        )

    def test_formats_stats_lines(self) -> None:
        lines = presenters.stats_lines(
            service(),
            {
                "executions": 3,
                "restarts": 1,
                "last_run": "2026-04-26T12:00:00",
                "last_exit_status": 0,
            },
        )

        self.assertIn("executions: 3", lines)
        self.assertIn("last_exit_status: 0", lines)

    def test_formats_describe_lines(self) -> None:
        lines = presenters.describe_lines(
            service(),
            info_map={"PID": "123", "LastExitStatus": "0"},
            stats_map={"last_run": "2026-04-26T12:00:00"},
            next_run="2026-04-27 00:00:00",
            plist_path=Path("/tmp/worker.plist"),
        )

        self.assertIn("loaded: yes", lines)
        self.assertIn("pid: 123", lines)
        self.assertIn("next_run: 2026-04-27 00:00:00", lines)
        self.assertEqual(lines[-1], "plist: /tmp/worker.plist")


if __name__ == "__main__":
    unittest.main()
