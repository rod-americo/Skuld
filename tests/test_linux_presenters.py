from __future__ import annotations

import types
import unittest

import skuld_linux_presenters as presenters


def service():
    return types.SimpleNamespace(
        display_name="api",
        scope="user",
        description="API",
        exec_cmd="/bin/api",
        working_dir="",
        user="",
        restart="on-failure",
        schedule="daily",
        timer_persistent=True,
    )


class LinuxPresentersTest(unittest.TestCase):
    def test_formats_stats_window(self) -> None:
        self.assertEqual(presenters.stats_window(boot=True, since=""), "current boot")
        self.assertEqual(
            presenters.stats_window(boot=False, since="1 hour ago"),
            "since 1 hour ago",
        )
        self.assertEqual(
            presenters.stats_window(boot=False, since=""),
            "all retained journal entries",
        )

    def test_formats_stats_lines(self) -> None:
        self.assertEqual(
            presenters.stats_lines(
                service(),
                target="user:api",
                service_unit="api.service",
                window="current boot",
                executions=3,
                restarts="1",
            ),
            [
                "name: api",
                "target: user:api",
                "scope: user",
                "service_unit: api.service",
                "window: current boot",
                "executions: 3",
                "restarts: 1",
            ],
        )

    def test_formats_describe_timer_absent(self) -> None:
        lines = presenters.describe_lines(
            service(),
            target="user:api",
            show_service={"ActiveState": "active", "MainPID": "123"},
            show_timer={},
        )

        self.assertIn("service_active: active", lines)
        self.assertIn("main_pid: 123", lines)
        self.assertEqual(lines[-1], "timer: n/a")


if __name__ == "__main__":
    unittest.main()
