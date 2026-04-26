from __future__ import annotations

import types
import unittest

import skuld_linux_view as view
import skuld_tables as tables


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
        service = types.SimpleNamespace(
            id=1,
            name="api",
            display_name="api",
            scope="user",
            user="runner",
            restart="on-failure",
        )

        def unit_exists(unit: str, scope: str = "system") -> bool:
            return unit in {"api.service", "api.timer"}

        def unit_active(unit: str, scope: str = "system") -> str:
            return "active" if unit == "api.service" else "inactive"

        rows = view.build_service_rows(
            [service],
            service_table_columns=tables.SERVICE_TABLE_COLUMN_KEYS,
            sort_by="name",
            unit_exists=unit_exists,
            unit_active=unit_active,
            display_unit_state=lambda value: value,
            colorize=colorize,
            read_unit_usage=lambda unit, scope="system", gpu_memory_by_pid=None: {
                "cpu": "1ms",
                "memory": "0.01GB",
            },
            timer_triggers_for_display=lambda item: "daily",
            read_unit_pids=lambda unit, scope="system": [123, 124],
            read_unit_ports=lambda unit, scope="system": "8000/tcp",
            load_runtime_stats=lambda: {"api": {"restarts": 1, "executions": 7}},
            format_restarts_exec=lambda name, stats: f"{stats[name]['restarts']}/{stats[name]['executions']}",
            read_timer_next_run=lambda name, scope="system": "tomorrow",
            read_timer_last_run=lambda name, scope="system": "yesterday",
            gpu_memory_by_pid={123: 10},
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": 1,
                    "name": "api",
                    "target": "user:api",
                    "scope": "user",
                    "backend": "systemd",
                    "service": "green:active",
                    "timer": "yellow:inactive",
                    "triggers": "daily",
                    "pid": "123+1",
                    "user": "runner",
                    "restart": "on-failure",
                    "runs": "1/7",
                    "last": "yesterday",
                    "next": "tomorrow",
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
            service_table_columns=None,
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
            read_unit_pids=lambda *_args, **_kwargs: [],
            read_unit_ports=lambda *_args, **_kwargs: "-",
            load_runtime_stats=lambda: {},
            format_restarts_exec=lambda _name, _stats: "-",
            read_timer_next_run=lambda *_args, **_kwargs: "-",
            read_timer_last_run=lambda *_args, **_kwargs: "-",
            sort_service_rows=lambda rows, _sort_by: rows,
            fit_service_table=lambda rows: (["id"], [[str(row["id"])] for row in rows]),
            render_table=lambda _headers, _rows: calls.append("table"),
            emit_blank=lambda: calls.append("blank"),
        )

        self.assertEqual(calls, ["require", "hint"])

    def test_render_services_table_renders_rows_through_table_pipeline(self) -> None:
        service = types.SimpleNamespace(
            id=2,
            name="api",
            display_name="api",
            scope="user",
            user="",
            restart="on-failure",
        )
        calls: list[str] = []

        view.render_services_table(
            compact=False,
            sort_by="id",
            service_table_columns=("id", "name"),
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
            read_unit_pids=lambda *_args, **_kwargs: [42],
            read_unit_ports=lambda *_args, **_kwargs: "-",
            load_runtime_stats=lambda: {},
            format_restarts_exec=lambda _name, _stats: "-",
            read_timer_next_run=lambda *_args, **_kwargs: "-",
            read_timer_last_run=lambda *_args, **_kwargs: "-",
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

    def test_default_columns_skip_optional_runtime_reads(self) -> None:
        service = types.SimpleNamespace(
            id=1,
            name="api",
            display_name="api",
            scope="user",
            user="runner",
            restart="on-failure",
        )
        calls: list[str] = []

        rows = view.build_service_rows(
            [service],
            service_table_columns=None,
            sort_by="name",
            unit_exists=lambda unit, scope="system": unit in {"api.service", "api.timer"},
            unit_active=lambda unit, scope="system": "active",
            display_unit_state=lambda value: value,
            colorize=colorize,
            read_unit_usage=lambda *_args, **_kwargs: {"cpu": "1ms", "memory": "1MB"},
            timer_triggers_for_display=lambda _service: "-",
            read_unit_pids=lambda *_args, **_kwargs: calls.append("pid") or [],
            read_unit_ports=lambda *_args, **_kwargs: "-",
            load_runtime_stats=lambda: calls.append("stats") or {},
            format_restarts_exec=lambda _name, _stats: "-",
            read_timer_next_run=lambda *_args, **_kwargs: calls.append("next") or "-",
            read_timer_last_run=lambda *_args, **_kwargs: calls.append("last") or "-",
            gpu_memory_by_pid=None,
        )

        self.assertEqual(calls, [])
        self.assertNotIn("pid", rows[0])
        self.assertNotIn("runs", rows[0])
        self.assertNotIn("last", rows[0])
        self.assertNotIn("next", rows[0])


if __name__ == "__main__":
    unittest.main()
