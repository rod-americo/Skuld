from pathlib import Path
from typing import Callable, List, Optional

from skuld_macos_model import ManagedService, managed_sort_key, validate_registry_service
from skuld_registry import RegistryStore


def ensure_storage(home: Path, registry_file: Path, runtime_stats_file: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    if not registry_file.exists():
        registry_file.write_text("[]", encoding="utf-8")
    if not runtime_stats_file.exists():
        runtime_stats_file.write_text('{"services": {}}\n', encoding="utf-8")


def registry_store(
    home: Path,
    registry_file: Path,
    *,
    normalize_item: Callable[[dict[str, object]], ManagedService],
) -> RegistryStore[ManagedService]:
    return RegistryStore(
        home=home,
        registry_file=registry_file,
        normalize_item=normalize_item,
        validate_service=validate_registry_service,
        sort_key=managed_sort_key,
        service_key=lambda service: service.name,
        required_fields=("name", "exec_cmd", "description"),
    )


def load_registry(
    home: Path,
    registry_file: Path,
    runtime_stats_file: Path,
    *,
    normalize_item: Callable[[dict[str, object]], ManagedService],
    write_back: bool = False,
) -> List[ManagedService]:
    ensure_storage(home, registry_file, runtime_stats_file)
    return registry_store(
        home,
        registry_file,
        normalize_item=normalize_item,
    ).load(write_back=write_back)


def save_registry(
    home: Path,
    registry_file: Path,
    runtime_stats_file: Path,
    services: List[ManagedService],
    *,
    normalize_item: Callable[[dict[str, object]], ManagedService],
) -> None:
    ensure_storage(home, registry_file, runtime_stats_file)
    registry_store(home, registry_file, normalize_item=normalize_item).save(services)


def upsert_registry(
    home: Path,
    registry_file: Path,
    runtime_stats_file: Path,
    service: ManagedService,
    *,
    normalize_item: Callable[[dict[str, object]], ManagedService],
) -> None:
    ensure_storage(home, registry_file, runtime_stats_file)
    registry_store(home, registry_file, normalize_item=normalize_item).upsert(service)


def remove_registry(
    home: Path,
    registry_file: Path,
    runtime_stats_file: Path,
    name: str,
    *,
    normalize_item: Callable[[dict[str, object]], ManagedService],
) -> None:
    ensure_storage(home, registry_file, runtime_stats_file)
    registry_store(home, registry_file, normalize_item=normalize_item).remove(name)


def get_managed(
    name: str,
    *,
    load_registry: Callable[[], List[ManagedService]],
) -> Optional[ManagedService]:
    for service in load_registry():
        if service.name == name:
            return service
    return None


def get_managed_by_display_name(
    display_name: str,
    *,
    load_registry: Callable[[], List[ManagedService]],
) -> Optional[ManagedService]:
    for service in load_registry():
        if service.display_name == display_name:
            return service
    return None


def get_managed_by_id(
    service_id: int,
    *,
    load_registry: Callable[[], List[ManagedService]],
) -> Optional[ManagedService]:
    for service in load_registry():
        if service.id == service_id:
            return service
    return None
