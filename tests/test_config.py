from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import skuld_config


class ConfigTest(unittest.TestCase):
    def test_missing_config_loads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"

            self.assertEqual(skuld_config.load_config(path), {})
            self.assertIsNone(skuld_config.load_columns_text(path))

    def test_saves_and_loads_columns_as_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"

            skuld_config.save_columns(path, ("id", "name", "service"))

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"columns": ["id", "name", "service"]},
            )
            self.assertEqual(skuld_config.load_columns_text(path), "id,name,service")

    def test_default_columns_clear_saved_column_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            skuld_config.save_columns(path, ("id", "name"))

            skuld_config.save_columns(path, None)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {})

    def test_saving_columns_recovers_invalid_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text("{bad json}\n", encoding="utf-8")

            skuld_config.save_columns(path, ("id", "name"))

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"columns": ["id", "name"]},
            )

    def test_rejects_non_object_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "must contain an object"):
                skuld_config.load_config(path)

    def test_rejects_non_string_column_items(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text('{"columns": ["id", 7]}\n', encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "columns must be strings"):
                skuld_config.load_columns_text(path)

    def test_config_lines_render_path_existence_and_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"

            self.assertEqual(
                skuld_config.config_lines(path, ("id", "name")),
                [f"path: {path}", "exists: no", "columns: id,name"],
            )


if __name__ == "__main__":
    unittest.main()
