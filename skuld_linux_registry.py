from pathlib import Path
from typing import Callable, List, Optional

from skuld_linux_model import (
    ManagedService,
    managed_service_key,
    managed_sort_key,
    normalize_registry_item,
    normalize_scope,
    validate_registry_service,
)
from skuld_registry import RegistryStore


def ensure_storage(home: Path, registry_file: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    if not registry_file.exists():
        registry_file.write_text("[]", encoding="utf-8")


def registry_store(home: Path, registry_file: Path) -> RegistryStore[ManagedService]:
    return RegistryStore(
        home=home,
        registry_file=registry_file,
        normalize_item=normalize_registry_item,
        validate_service=validate_registry_service,
        sort_key=managed_sort_key,
        service_key=lambda service: managed_service_key(service.name, service.scope),
        required_fields=("name", "exec_cmd", "description"),
    )


def load_registry(
    home: Path,
    registry_file: Path,
    *,
    write_back: bool = False,
) -> List[ManagedService]:
    return registry_store(home, registry_file).load(write_back=write_back)


def save_registry(
    home: Path,
    registry_file: Path,
    services: List[ManagedService],
) -> None:
    registry_store(home, registry_file).save(services)


def upsert_registry(
    home: Path,
    registry_file: Path,
    service: ManagedService,
) -> None:
    registry_store(home, registry_file).upsert(service)


def remove_registry(
    home: Path,
    registry_file: Path,
    name: str,
    scope: str,
) -> None:
    registry_store(home, registry_file).remove(managed_service_key(name, scope))


def find_managed_by_name(
    name: str,
    *,
    load_registry: Callable[[], List[ManagedService]],
) -> List[ManagedService]:
    return [service for service in load_registry() if service.name == name]


def get_managed(
    name: str,
    *,
    scope: Optional[str] = None,
    load_registry: Callable[[], List[ManagedService]],
) -> Optional[ManagedService]:
    matches = find_managed_by_name(name, load_registry=load_registry)
    if scope is not None:
        normalized_scope = normalize_scope(scope)
        for service in matches:
            if service.scope == normalized_scope:
                return service
        return None
    if len(matches) == 1:
        return matches[0]
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


def require_managed(
    name: str,
    *,
    scope: Optional[str] = None,
    get_managed: Callable[..., Optional[ManagedService]],
) -> ManagedService:
    service = get_managed(name, scope=scope)
    if not service:
        raise RuntimeError(
            f"'{name}' is not in the skuld registry. "
            "Only services tracked by skuld can be monitored."
        )
    return service
