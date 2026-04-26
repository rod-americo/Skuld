import sys


def select_backend_module() -> str:
    if sys.platform == "darwin":
        return "skuld_macos"
    return "skuld_linux"


def main() -> int:
    module_name = select_backend_module()
    module = __import__(module_name, fromlist=["main"])
    return module.main()
