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

    def test_render_services_table_shows_catalog_hint_when_registry_is_empty(self) -> None:
        calls: list[str] = []

        view.render_services_table(
            compact=True,
            sort_by="name",
            require_systemctl=lambda: calls.append("require"),
            load_registry=lambda: [],
            render_discoverable_services_hint=lambda: calls.append("hint"),
            read_gpu_memory_by_pid=lambda: {},
            render_host_panel=lambda: calls.append("host"),
            unit_exists=lambda *_args, **_kwargs: False,
            unit_active=lambda *_args, **_kwargs: "inactive",
            display_unit_state=lambda value: value,
            colorize=colorize,
            read_unit_usage=lambda *_args, **_kwargs: {"cpu": "-", "memory": "-"},
            timer_triggers_for_display=lambda _service: "-",
            read_unit_ports=lambda *_args, **_kwargs: "-",
            sort_service_rows=lambda rows, _sort_by: rows,
            fit_service_table=lambda rows: (["id"], [[str(row["id"])] for row in rows]),
            render_table=lambda _headers, _rows: calls.append("table"),
            emit_blank=lambda: calls.append("blank"),
        )

        self.assertEqual(calls, ["require", "hint"])

    def test_render_services_table_renders_rows_through_table_pipeline(self) -> None:
        service = types.SimpleNamespace(id=2, name="api", display_name="api", scope="user")
        calls: list[str] = []

        view.render_services_table(
            compact=False,
            sort_by="id",
            require_systemctl=lambda: calls.append("require"),
            load_registry=lambda: [service],
            render_discoverable_services_hint=lambda: calls.append("hint"),
            read_gpu_memory_by_pid=lambda: {123: 1},
            render_host_panel=lambda: calls.append("host"),
            unit_exists=lambda unit, scope="system": unit == "api.service",
            unit_active=lambda _unit, scope="system": "active",
            display_unit_state=lambda value: value,
            colorize=colorize,
            read_unit_usage=lambda *_args, **_kwargs: {"cpu": "1ms", "memory": "1MB"},
            timer_triggers_for_display=lambda _service: "-",
            read_unit_ports=lambda *_args, **_kwargs: "-",
            sort_service_rows=lambda rows, sort_by: calls.append(f"sort:{sort_by}") or rows,
            fit_service_table=lambda rows: (["id", "name"], [[str(row["id"]), str(row["name"])] for row in rows]),
            render_table=lambda headers, rows: calls.append(f"table:{headers}:{rows}"),
            emit_blank=lambda: calls.append("blank"),
        )

        self.assertEqual(calls, [
            "require",
            "blank",
            "host",
            "sort:id",
            "table:['id', 'name']:[['2', 'api']]",
            "blank",
        ])


if __name__ == "__main__":
    unittest.main()
