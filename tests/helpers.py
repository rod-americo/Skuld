from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_entrypoint_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("skuld_entrypoint_test", str(ROOT / "skuld"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Could not create module spec for ./skuld")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class IsolatedLinuxState:
    def __init__(self, module: ModuleType):
        self.module = module
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "services.json"
        self.stats = self.root / "journal_stats.json"
        self.patches = [
            patch.object(module, "SKULD_HOME", self.root),
            patch.object(module, "REGISTRY_FILE", self.registry),
            patch.object(module, "RUNTIME_STATS_FILE", self.stats),
            patch.object(module, "USE_ENV_SUDO", True),
            patch.object(module, "FORCE_TABLE_ASCII", True),
            patch.object(module, "FORCE_TABLE_UNICODE", False),
        ]

    def __enter__(self) -> "IsolatedLinuxState":
        for item in self.patches:
            item.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.tempdir.cleanup()


class IsolatedMacState:
    def __init__(self, module: ModuleType):
        self.module = module
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "services.json"
        self.stats = self.root / "runtime_stats.json"
        self.patches = [
            patch.object(module, "SKULD_HOME", self.root),
            patch.object(module, "REGISTRY_FILE", self.registry),
            patch.object(module, "RUNTIME_STATS_FILE", self.stats),
            patch.object(module, "USE_ENV_SUDO", True),
            patch.object(module, "FORCE_TABLE_ASCII", True),
            patch.object(module, "FORCE_TABLE_UNICODE", False),
        ]

    def __enter__(self) -> "IsolatedMacState":
        for item in self.patches:
            item.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.tempdir.cleanup()
