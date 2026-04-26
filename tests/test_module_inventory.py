from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def root_modules() -> list[str]:
    return sorted(path.stem for path in ROOT.glob("skuld_*.py"))


def pyproject_modules() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"py-modules\s*=\s*\[(.*?)\]", text, flags=re.S)
    if not match:
        raise AssertionError("pyproject.toml is missing [tool.setuptools] py-modules")
    return sorted(re.findall(r'"(skuld_[^"]+)"', match.group(1)))


class ModuleInventoryTest(unittest.TestCase):
    def test_pyproject_packages_every_root_skuld_module(self) -> None:
        self.assertEqual(pyproject_modules(), root_modules())

    def test_documented_compile_commands_include_every_root_skuld_module(self) -> None:
        files = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "docs" / "OPERATIONS.md",
            ROOT / "docs" / "RELEASE.md",
            ROOT / ".github" / "workflows" / "ci.yml",
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            missing = [
                f"./{module}.py"
                for module in root_modules()
                if f"./{module}.py" not in text
            ]
            self.assertEqual(missing, [], f"{path} misses modules")

    def test_linux_remote_smoke_payload_includes_linux_runtime_modules(self) -> None:
        text = (ROOT / "scripts" / "smoke_linux_systemd_user.sh").read_text(
            encoding="utf-8"
        )
        shared = {
            "skuld_entrypoint",
            "skuld_cli",
            "skuld_common",
            "skuld_observability",
            "skuld_registry",
            "skuld_tables",
        }
        required = [
            f"{module}.py"
            for module in root_modules()
            if module.startswith("skuld_linux") or module in shared
        ]
        missing = [module for module in required if module not in text]
        self.assertEqual(missing, [])
        self.assertIn("scripts/smoke_process.sh", text)


if __name__ == "__main__":
    unittest.main()
