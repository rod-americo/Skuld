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

    def test_render_services_table_shows_catalog_hint_when_registry_is_empty(self) -> None:
        calls: list[str] = []

        view.render_services_table(
            compact=True,
            sort_by="name",
            load_registry=lambda: [],
            render_discoverable_services_hint=lambda: calls.append("hint"),
            render_host_panel=lambda: calls.append("host"),
            read_event_stats=lambda _service: {},
            read_pid=lambda _service: 0,
            read_cpu_memory=lambda _pid: {"cpu": "-", "memory": "-"},
            service_loaded=lambda _service: False,
            colorize=colorize,
            humanize_schedule_for_display=lambda _schedule, _persistent: "-",
            read_ports=lambda _pid: "-",
            sort_service_rows=lambda rows, _sort_by: rows,
            fit_service_table=lambda rows: (["id"], [[str(row["id"])] for row in rows]),
            render_table=lambda _headers, _rows: calls.append("table"),
            emit_blank=lambda: calls.append("blank"),
        )

        self.assertEqual(calls, ["hint"])

    def test_render_services_table_renders_rows_through_table_pipeline(self) -> None:
        service = types.SimpleNamespace(
            id=2,
            name="com.example.worker",
            display_name="worker",
            schedule="",
            timer_persistent=True,
        )
        calls: list[str] = []

        view.render_services_table(
            compact=False,
            sort_by="id",
            load_registry=lambda: [service],
            render_discoverable_services_hint=lambda: calls.append("hint"),
            render_host_panel=lambda: calls.append("host"),
            read_event_stats=lambda _service: {},
            read_pid=lambda _service: 42,
            read_cpu_memory=lambda _pid: {"cpu": "1ms", "memory": "1MB"},
            service_loaded=lambda _service: True,
            colorize=colorize,
            humanize_schedule_for_display=lambda _schedule, _persistent: "-",
            read_ports=lambda _pid: "-",
            sort_service_rows=lambda rows, sort_by: calls.append(f"sort:{sort_by}") or rows,
            fit_service_table=lambda rows: (["id", "name"], [[str(row["id"]), str(row["name"])] for row in rows]),
            render_table=lambda headers, rows: calls.append(f"table:{headers}:{rows}"),
            emit_blank=lambda: calls.append("blank"),
        )

        self.assertEqual(calls, [
            "blank",
            "host",
            "sort:id",
            "table:['id', 'name']:[['2', 'worker']]",
            "blank",
        ])


if __name__ == "__main__":
    unittest.main()
