from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from skuld_linux_context import LinuxBackendContext
from skuld_macos_context import MacOSBackendContext


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


class IsolatedLinuxContext:
    def __init__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "services.json"
        self.stats = self.root / "journal_stats.json"
        self.context = LinuxBackendContext(
            skuld_home=self.root,
            registry_file=self.registry,
            runtime_stats_file=self.stats,
            force_table_ascii=True,
        )

    def __enter__(self) -> "IsolatedLinuxContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.tempdir.cleanup()


class IsolatedMacContext:
    def __init__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "services.json"
        self.stats = self.root / "runtime_stats.json"
        self.context = MacOSBackendContext(
            skuld_home=self.root,
            registry_file=self.registry,
            runtime_stats_file=self.stats,
            force_table_ascii=True,
        )

    def __enter__(self) -> "IsolatedMacContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.tempdir.cleanup()
