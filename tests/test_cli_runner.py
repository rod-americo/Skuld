from __future__ import annotations

import argparse
import unittest

import skuld_cli
import skuld_tables as tables


def parser_with_commands() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skuld")
    parser.add_argument(
        "--columns",
        nargs="?",
        const=tables.SERVICE_TABLE_COLUMN_CATALOG_REQUEST,
    )
    subparsers = parser.add_subparsers(dest="command")

    version = subparsers.add_parser("version")
    version.set_defaults(func=lambda _args: None)

    sudo = subparsers.add_parser("sudo")
    sudo_subparsers = sudo.add_subparsers(dest="sudo_command", required=True)
    sudo_check = sudo_subparsers.add_parser("check")
    sudo_check.set_defaults(func=lambda _args: None)

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_show = config_subparsers.add_parser("show")
    config_show.set_defaults(func=lambda _args: None)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--columns",
        nargs="?",
        const=tables.SERVICE_TABLE_COLUMN_CATALOG_REQUEST,
        default=argparse.SUPPRESS,
    )
    list_parser.set_defaults(func=lambda _args: None)
    return parser


class CliRunnerTest(unittest.TestCase):
    def test_sudo_helpers_do_not_require_registry_load(self) -> None:
        loaded = False

        def load_registry():
            nonlocal loaded
            loaded = True
            raise AssertionError("sudo helpers should not load the registry")

        result = skuld_cli.run_backend_main(
            argv=["skuld", "sudo", "check"],
            parser=parser_with_commands(),
            configure_globals=lambda _args, _parser: None,
            load_registry=load_registry,
            list_services_compact=lambda _sort: None,
            resolve_sort_arg=lambda _args: "name",
            err=lambda _message: None,
        )

        self.assertEqual(result, 0)
        self.assertFalse(loaded)

    def test_config_helpers_do_not_require_registry_load(self) -> None:
        loaded = False

        def load_registry():
            nonlocal loaded
            loaded = True
            raise AssertionError("config helpers should not load the registry")

        result = skuld_cli.run_backend_main(
            argv=["skuld", "config", "show"],
            parser=parser_with_commands(),
            configure_globals=lambda _args, _parser: None,
            load_registry=load_registry,
            list_services_compact=lambda _sort: None,
            resolve_sort_arg=lambda _args: "name",
            err=lambda _message: None,
        )

        self.assertEqual(result, 0)
        self.assertFalse(loaded)

    def test_columns_catalog_request_does_not_require_registry_load(self) -> None:
        loaded = False
        rendered = False

        def load_registry():
            nonlocal loaded
            loaded = True
            raise AssertionError("column catalog should not load the registry")

        def show_columns_catalog():
            nonlocal rendered
            rendered = True

        result = skuld_cli.run_backend_main(
            argv=["skuld", "--columns"],
            parser=parser_with_commands(),
            configure_globals=lambda _args, _parser: None,
            load_registry=load_registry,
            list_services_compact=lambda _sort: None,
            resolve_sort_arg=lambda _args: "name",
            err=lambda _message: None,
            show_columns_catalog=show_columns_catalog,
        )

        self.assertEqual(result, 0)
        self.assertFalse(loaded)
        self.assertTrue(rendered)

    def test_regular_commands_still_load_registry(self) -> None:
        loaded = False

        def load_registry():
            nonlocal loaded
            loaded = True

        result = skuld_cli.run_backend_main(
            argv=["skuld", "list"],
            parser=parser_with_commands(),
            configure_globals=lambda _args, _parser: None,
            load_registry=load_registry,
            list_services_compact=lambda _sort: None,
            resolve_sort_arg=lambda _args: "name",
            err=lambda _message: None,
        )

        self.assertEqual(result, 0)
        self.assertTrue(loaded)


if __name__ == "__main__":
    unittest.main()
