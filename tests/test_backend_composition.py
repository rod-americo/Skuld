from __future__ import annotations

import ast
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
