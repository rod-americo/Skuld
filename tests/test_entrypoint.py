from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from tests.helpers import load_entrypoint_module


class EntrypointTest(unittest.TestCase):
    def test_selects_macos_backend_on_darwin(self) -> None:
        module = load_entrypoint_module()
        with patch.object(module.sys, "platform", "darwin"):
            self.assertEqual(module.select_backend_module(), "skuld_macos")

    def test_selects_linux_backend_for_other_platforms(self) -> None:
        module = load_entrypoint_module()
        with patch.object(module.sys, "platform", "linux"):
            self.assertEqual(module.select_backend_module(), "skuld_linux")

    def test_main_dispatches_to_selected_backend(self) -> None:
        module = load_entrypoint_module()
        fake_backend = types.SimpleNamespace(main=lambda: 23)
        original = sys.modules.get("skuld_linux")
        sys.modules["skuld_linux"] = fake_backend
        try:
            with patch.object(module.sys, "platform", "linux"):
                self.assertEqual(module.main(), 23)
        finally:
            if original is None:
                sys.modules.pop("skuld_linux", None)
            else:
                sys.modules["skuld_linux"] = original


if __name__ == "__main__":
    unittest.main()
