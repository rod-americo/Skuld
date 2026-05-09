from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def root_modules() -> list[str]:
    return sorted(path.stem for path in (ROOT / "skuld").glob("skuld_*.py"))


def pyproject_packages() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"packages\s*=\s*\[(.*?)\]", text, flags=re.S)
    if not match:
        raise AssertionError("pyproject.toml is missing [tool.setuptools] packages")
    return sorted(re.findall(r'"([^"]+)"', match.group(1)))


class ModuleInventoryTest(unittest.TestCase):
    def test_pyproject_packages_skuld_package(self) -> None:
        self.assertEqual(pyproject_packages(), ["skuld"])

    def test_documented_compile_commands_include_package_glob(self) -> None:
        files = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "docs" / "OPERATIONS.md",
            ROOT / "docs" / "RELEASE.md",
            ROOT / ".github" / "workflows" / "ci.yml",
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIn("skuld/*.py", text, f"{path} misses package compile glob")

    def test_linux_remote_smoke_payload_includes_linux_runtime_modules(self) -> None:
        text = (ROOT / "scripts" / "smoke_linux_systemd_user.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("bin/skuld", text)
        self.assertIn("    skuld \\", text)
        self.assertIn("scripts/smoke_process.sh", text)


if __name__ == "__main__":
    unittest.main()
