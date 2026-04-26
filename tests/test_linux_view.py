from __future__ import annotations

import types
import unittest

import skuld_linux_view as view


def colorize(text: str, color: str) -> str:
    return f"{color}:{text}"


class LinuxViewTest(unittest.TestCase):
    def test_formats_service_and_timer_states(self) -> None:
        self.assertEqual(
            view.service_state_for_display("active", "active", colorize),
            "green:active",
        )
        self.assertEqual(
            view.service_state_for_display("inactive", "inactive", colorize),
            "yellow:inactive",
        )
        self.assertEqual(
            view.service_state_for_display("missing", "missing", colorize),
            "red:missing",
        )
        self.assertEqual(view.timer_state_for_display("n/a", "n/a", colorize), "gray:n/a")

    def test_builds_service_rows_from_backend_callbacks(self) -> None:
        service = types.SimpleNamespace(id=1, name="api", display_name="api", scope="user")

        def unit_exists(unit: str, scope: str = "system") -> bool:
            return unit in {"api.service", "api.timer"}

        def unit_active(unit: str, scope: str = "system") -> str:
            return "active" if unit == "api.service" else "inactive"

        rows = view.build_service_rows(
            [service],
            unit_exists=unit_exists,
            unit_active=unit_active,
            display_unit_state=lambda value: value,
            colorize=colorize,
            read_unit_usage=lambda unit, scope="system", gpu_memory_by_pid=None: {
                "cpu": "1ms",
                "memory": "0.01GB",
            },
            timer_triggers_for_display=lambda item: "daily",
            read_unit_ports=lambda unit, scope="system": "8000/tcp",
            gpu_memory_by_pid={123: 10},
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": 1,
                    "name": "api",
                    "service": "green:active",
                    "timer": "yellow:inactive",
                    "triggers": "daily",
                    "cpu": "1ms",
                    "memory": "0.01GB",
                    "ports": "8000/tcp",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
