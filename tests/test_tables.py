from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

import skuld_common as common
import skuld_tables as tables


class ServiceTableTest(unittest.TestCase):
    def test_fits_service_table_with_shared_columns(self) -> None:
        rows = [
            {
                "id": 1,
                "name": "very-long-service-name",
                "service": "active",
                "timer": "n/a",
                "triggers": "every weekday morning",
                "cpu": "1.0%",
                "memory": "0.10GB",
                "ports": "8000/tcp,9000/tcp",
            }
        ]

        headers, fitted = tables.fit_service_table(rows, max_width=60)

        self.assertIn("id", headers)
        self.assertIn("name", headers)
        self.assertLessEqual(common.table_render_width(common.table_widths(headers, fitted)), 60)

    def test_sorts_rows_by_shared_sort_key(self) -> None:
        rows = [
            {"id": 2, "name": "worker", "cpu": "1.0%", "memory": "0.50GB"},
            {"id": 1, "name": "api", "cpu": "9.0%", "memory": "0.10GB"},
        ]

        self.assertEqual([row["id"] for row in tables.sort_service_rows(rows, "name")], [1, 2])
        self.assertEqual([row["id"] for row in tables.sort_service_rows(rows, "cpu")], [1, 2])

    def test_selects_explicit_service_table_columns_in_requested_order(self) -> None:
        rows = [
            {
                "id": 1,
                "name": "api",
                "service": "active",
                "timer": "n/a",
                "triggers": "-",
                "cpu": "1.0%",
                "memory": "0.10GB",
                "ports": "8000/tcp",
            }
        ]

        headers, fitted = tables.fit_service_table(
            rows,
            max_width=12,
            columns=("name", "id"),
        )

        self.assertEqual(headers, ["name", "id"])
        self.assertEqual(fitted, [["api", "1"]])

    def test_parses_service_table_columns_from_cli_or_env(self) -> None:
        self.assertEqual(
            tables.resolve_service_table_columns("name,cpu,name", env_value="id"),
            ("name", "cpu"),
        )
        self.assertEqual(
            tables.resolve_service_table_columns(None, env_value="id,service"),
            ("id", "service"),
        )
        self.assertIsNone(tables.resolve_service_table_columns("default", env_value="id"))

    def test_rejects_unknown_service_table_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown service table column"):
            tables.parse_service_table_columns("id,owner")

    def test_render_host_panel_delegates_to_backend_renderer(self) -> None:
        calls = []

        def render_table(headers, rows):
            calls.append((headers, rows))
            print("rendered")

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            tables.render_host_panel({"uptime": "1m", "memory": "1GB"}, render_table)

        self.assertEqual(calls, [(["uptime", "memory"], [["1m", "1GB"]])])
        self.assertEqual(stdout.getvalue(), "rendered\n\n")


if __name__ == "__main__":
    unittest.main()
