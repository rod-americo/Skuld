from __future__ import annotations

import re
import unittest

import skuld_linux
import skuld_macos
from tests.helpers import ROOT


class PackagingMetadataTest(unittest.TestCase):
    def test_pyproject_exposes_console_script(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('[project.scripts]', text)
        self.assertIn('skuld = "skuld_entrypoint:main"', text)
        self.assertIn('"skuld_entrypoint"', text)
        self.assertIn('"skuld_linux"', text)
        self.assertIn('"skuld_linux_runtime"', text)
        self.assertIn('"skuld_linux_targets"', text)
        self.assertIn('"skuld_linux_view"', text)
        self.assertIn('"skuld_macos"', text)
        self.assertIn('"skuld_macos_runtime"', text)
        self.assertIn('"skuld_macos_view"', text)
        self.assertIn('"skuld_tables"', text)

    def test_package_version_matches_backend_versions(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
        self.assertIsNotNone(match)
        package_version = match.group(1)

        self.assertEqual(package_version, skuld_linux.VERSION)
        self.assertEqual(package_version, skuld_macos.VERSION)


if __name__ == "__main__":
    unittest.main()
