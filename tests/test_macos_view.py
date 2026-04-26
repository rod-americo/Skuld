from __future__ import annotations

import types
import unittest

import skuld_macos_view as view


def colorize(text: str, color: str) -> str:
    return f"{color}:{text}"


class MacosViewTest(unittest.TestCase):
    def test_formats_service_and_timer_states(self) -> None:
        self.assertEqual(
            view.service_state_for_display(True, 42, colorize),
            "green:active",
        )
        self.assertEqual(
            view.service_state_for_display(True, 0, colorize),
            "yellow:loaded",
        )
        self.assertEqual(
            view.service_state_for_display(False, 0, colorize),
            "yellow:inactive",
        )
        self.assertEqual(
            view.timer_state_for_display(True, True, colorize),
            "green:scheduled",
        )
        self.assertEqual(
            view.timer_state_for_display(True, False, colorize),
            "yellow:inactive",
        )
        self.assertEqual(
            view.timer_state_for_display(False, True, colorize),
            "gray:n/a",
        )

    def test_builds_service_rows_from_backend_callbacks(self) -> None:
        service = types.SimpleNamespace(
            id=1,
            name="com.example.worker",
            display_name="worker",
            schedule="daily",
            timer_persistent=True,
        )
        stats_calls = []

        rows = view.build_service_rows(
            [service],
            read_event_stats=lambda item: stats_calls.append(item.name) or {},
            read_pid=lambda item: 123,
            read_cpu_memory=lambda pid: {"cpu": "2ms", "memory": "0.02GB"},
            service_loaded=lambda item: True,
            colorize=colorize,
            humanize_schedule_for_display=lambda schedule, persistent: schedule,
            read_ports=lambda pid: "8000/tcp",
        )

        self.assertEqual(stats_calls, ["com.example.worker"])
        self.assertEqual(
            rows,
            [
                {
                    "id": 1,
                    "name": "worker",
                    "service": "green:active",
                    "timer": "green:scheduled",
                    "triggers": "daily",
                    "cpu": "2ms",
                    "memory": "0.02GB",
                    "ports": "8000/tcp",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
