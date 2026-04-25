from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

import skuld_common as common


class CommonHelperTest(unittest.TestCase):
    def test_parse_helpers_are_conservative(self) -> None:
        self.assertTrue(common.parse_bool("yes"))
        self.assertFalse(common.parse_bool("off"))
        self.assertTrue(common.parse_bool("unknown", default=True))
        self.assertEqual(common.parse_int("42"), 42)
        self.assertEqual(common.parse_int("-1"), 0)
        self.assertEqual(common.parse_int("bad"), 0)

    def test_format_helpers_match_cli_expectations(self) -> None:
        self.assertEqual(common.format_bytes(str(1024**3)), "1.00GB")
        self.assertEqual(common.format_bytes("[not set]"), "-")
        self.assertEqual(common.format_duration_human(65), "1m")
        self.assertEqual(common.format_duration_human(3660), "1h 01m")
        self.assertEqual(common.clip_text("abcdef", 5), "ab...")

    def test_fit_table_shrinks_and_drops_columns_to_width(self) -> None:
        columns = (
            {"key": "id", "header": "id", "min_width": 2, "shrink": False},
            {"key": "name", "header": "name", "min_width": 4, "shrink": True},
            {"key": "ports", "header": "ports", "min_width": 5, "shrink": True},
        )
        rows = [{"id": 1, "name": "very-long-service-name", "ports": "8080/tcp,9000/tcp"}]
        headers, fitted = common.fit_table(
            rows,
            service_columns=columns,
            shrink_order=("name", "ports"),
            hide_order=("ports",),
            max_width=32,
        )

        self.assertEqual(headers, ["id", "name", "ports"])
        self.assertLessEqual(common.table_render_width(common.table_widths(headers, fitted)), 32)

    def test_render_table_uses_ascii_when_requested(self) -> None:
        with redirect_stdout(io.StringIO()) as stdout:
            common.render_table(["id", "name"], [["1", "api"]], unicode_box=False)

        output = stdout.getvalue()
        self.assertIn("+----+------+", output)
        self.assertIn("| id | name |", output)


if __name__ == "__main__":
    unittest.main()
