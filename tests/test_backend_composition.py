from __future__ import annotations

import ast
import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import skuld_config
import skuld_linux
import skuld_macos
from skuld_linux_context import LinuxBackendContext
from skuld_linux_handlers import LinuxCommandHandlers
from skuld_macos_context import MacOSBackendContext
from skuld_macos_handlers import MacOSCommandHandlers


ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_FUNCTIONS = {"build_parser", "configure_cli_globals", "main"}
LEGACY_BACKEND_WRAPPERS = {
    "load_registry",
    "save_registry",
    "track",
    "start_stop",
    "logs",
    "stats",
    "doctor",
    "render_table",
}


def top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


class BackendCompositionTest(unittest.TestCase):
    def test_linux_entrypoint_is_only_composition_root(self) -> None:
        functions = top_level_functions(ROOT / "skuld_linux.py")

        self.assertEqual(functions, COMPOSITION_FUNCTIONS)
        self.assertTrue(LEGACY_BACKEND_WRAPPERS.isdisjoint(functions))
        self.assertIsInstance(skuld_linux.CONTEXT, LinuxBackendContext)
        self.assertIsInstance(skuld_linux.HANDLERS, LinuxCommandHandlers)

    def test_macos_entrypoint_is_only_composition_root(self) -> None:
        functions = top_level_functions(ROOT / "skuld_macos.py")

        self.assertEqual(functions, COMPOSITION_FUNCTIONS)
        self.assertTrue(LEGACY_BACKEND_WRAPPERS.isdisjoint(functions))
        self.assertIsInstance(skuld_macos.CONTEXT, MacOSBackendContext)
        self.assertIsInstance(skuld_macos.HANDLERS, MacOSCommandHandlers)

    def test_contexts_resolve_table_columns_from_cli_or_env(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            parser = argparse.ArgumentParser()
            args = argparse.Namespace(
                no_env_sudo=False,
                ascii=False,
                unicode=False,
                columns="name,cpu",
                command="list",
            )
            linux_context = LinuxBackendContext(skuld_home=root / "linux")
            macos_context = MacOSBackendContext(skuld_home=root / "macos")

            skuld_config.save_columns(linux_context.config_file, ("id", "service"))
            skuld_config.save_columns(macos_context.config_file, ("id", "service"))

            linux_context.configure_cli_globals(args, parser)
            macos_context.configure_cli_globals(args, parser)

            self.assertEqual(linux_context.service_table_columns, ("name", "cpu"))
            self.assertEqual(macos_context.service_table_columns, ("name", "cpu"))

            config_args = argparse.Namespace(
                no_env_sudo=False,
                ascii=False,
                unicode=False,
                columns=None,
                command="list",
            )
            with patch.dict(os.environ, {"SKULD_COLUMNS": "name,memory"}):
                linux_context.configure_cli_globals(config_args, parser)
                macos_context.configure_cli_globals(config_args, parser)

            self.assertEqual(linux_context.service_table_columns, ("id", "service"))
            self.assertEqual(macos_context.service_table_columns, ("id", "service"))

            env_args = argparse.Namespace(
                no_env_sudo=False,
                ascii=False,
                unicode=False,
                columns=None,
                command="list",
            )
            linux_context.config_file.unlink()
            macos_context.config_file.unlink()
            with patch.dict(os.environ, {"SKULD_COLUMNS": "id,service"}):
                linux_context.configure_cli_globals(env_args, parser)
                macos_context.configure_cli_globals(env_args, parser)

            self.assertEqual(linux_context.service_table_columns, ("id", "service"))
            self.assertEqual(macos_context.service_table_columns, ("id", "service"))


if __name__ == "__main__":
    unittest.main()
