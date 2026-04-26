from __future__ import annotations

import unittest
from typing import Optional

import skuld_macos_parser as macos_parser
import skuld_tables as tables


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


class MacParserTest(unittest.TestCase):
    def build_parser(self, calls: Optional[list[tuple[str, object]]] = None):
        def start_stop(args, action):
            if calls is not None:
                calls.append((action, list(args.targets)))

        return macos_parser.build_parser(
            sort_choices=("id", "name", "cpu", "memory"),
            column_choices=tables.SERVICE_TABLE_COLUMN_KEYS,
            version="9.9.9",
            list_services=_noop,
            catalog=_noop,
            track=_noop,
            rename=_noop,
            untrack=_noop,
            exec_now=_noop,
            start_stop=start_stop,
            restart=_noop,
            status=_noop,
            logs=_noop,
            stats=_noop,
            doctor=_noop,
            describe=_noop,
            sync=_noop,
            sudo_check=_noop,
            sudo_auth=_noop,
            sudo_forget=_noop,
            sudo_run_command=_noop,
            config_show=_noop,
            config_columns=_noop,
        )

    def test_top_level_columns_configures_default_table(self) -> None:
        args = self.build_parser().parse_args(["--columns", "id,name,service"])

        self.assertEqual(args.columns, "id,name,service")

    def test_top_level_columns_without_value_requests_catalog(self) -> None:
        args = self.build_parser().parse_args(["--columns"])

        self.assertEqual(args.columns, tables.SERVICE_TABLE_COLUMN_CATALOG_REQUEST)

    def test_list_columns_configures_table_after_subcommand(self) -> None:
        args = self.build_parser().parse_args(["list", "--columns", "name,cpu"])

        self.assertEqual(args.columns, "name,cpu")

    def test_list_columns_without_value_requests_catalog(self) -> None:
        args = self.build_parser().parse_args(["list", "--columns"])

        self.assertEqual(args.columns, tables.SERVICE_TABLE_COLUMN_CATALOG_REQUEST)

    def test_top_level_columns_survive_list_subcommand_defaults(self) -> None:
        args = self.build_parser().parse_args(["--columns", "id,name", "list"])

        self.assertEqual(args.columns, "id,name")

    def test_track_keeps_launchd_target_and_alias_contract(self) -> None:
        args = self.build_parser().parse_args(["track", "1", "com.example.Worker", "--alias", "worker"])

        self.assertEqual(args.targets, ["1", "com.example.Worker"])
        self.assertEqual(args.alias, "worker")
        self.assertIs(args.func, _noop)

    def test_catalog_accepts_grep_filter(self) -> None:
        args = self.build_parser().parse_args(["catalog", "--grep", "draupnir"])

        self.assertEqual(args.grep, "draupnir")
        self.assertIs(args.func, _noop)

    def test_logs_keep_compatibility_options(self) -> None:
        args = self.build_parser().parse_args(["logs", "api", "--folow", "--timer", "--plain"])

        self.assertEqual(args.name, "api")
        self.assertTrue(args.follow)
        self.assertTrue(args.timer)
        self.assertTrue(args.plain)

    def test_stop_dispatches_to_shared_action_handler(self) -> None:
        calls: list[tuple[str, object]] = []
        args = self.build_parser(calls).parse_args(["stop", "api", "worker"])

        args.func(args)

        self.assertEqual(calls, [("stop", ["api", "worker"])])

    def test_untrack_accepts_multiple_targets(self) -> None:
        args = self.build_parser().parse_args(["untrack", "1", "2", "worker"])

        self.assertEqual(args.targets, ["1", "2", "worker"])
        self.assertIsNone(args.name_flag)
        self.assertIsNone(args.id_flag)

    def test_sync_keeps_target_forms(self) -> None:
        args = self.build_parser().parse_args(["sync", "--name", "api"])

        self.assertIsNone(args.name)
        self.assertEqual(args.name_flag, "api")

    def test_sudo_auth_and_forget_are_registered(self) -> None:
        for command in ("auth", "forget"):
            with self.subTest(command=command):
                args = self.build_parser().parse_args(["sudo", command])
                self.assertIs(args.func, _noop)

    def test_config_commands_are_registered(self) -> None:
        show_args = self.build_parser().parse_args(["config", "show"])
        columns_args = self.build_parser().parse_args(["config", "columns", "id,name"])
        catalog_args = self.build_parser().parse_args(["config", "columns"])
        numeric_args = self.build_parser().parse_args(["config", "columns", "1", "2", "3"])

        self.assertIs(show_args.func, _noop)
        self.assertEqual(columns_args.columns, ["id,name"])
        self.assertIs(columns_args.func, _noop)
        self.assertEqual(catalog_args.columns, [])
        self.assertIs(catalog_args.func, _noop)
        self.assertEqual(numeric_args.columns, ["1", "2", "3"])
        self.assertIs(numeric_args.func, _noop)


if __name__ == "__main__":
    unittest.main()
