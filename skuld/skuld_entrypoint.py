import sys
from importlib import import_module


def select_backend_module() -> str:
    if sys.platform == "darwin":
        return "skuld.skuld_macos"
    return "skuld.skuld_linux"


def main() -> int:
    module_name = select_backend_module()
    module = import_module(module_name)
    return module.main()
