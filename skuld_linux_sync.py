from dataclasses import asdict
from typing import Callable, List, Optional

from skuld_linux_model import ManagedService


def sync_registry_from_systemd(
    target: Optional[ManagedService],
    *,
    load_registry: Callable[..., List[ManagedService]],
    save_registry: Callable[[List[ManagedService]], None],
    managed_service_key: Callable[[str, str], tuple],
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., dict],
    read_timer_schedule: Callable[..., str],
    read_timer_persistent: Callable[..., bool],
) -> int:
    services = load_registry(write_back=True)
    changed = 0
    target_key = managed_service_key(target.name, target.scope) if target else None
    updated: List[ManagedService] = []

    for service in services:
        if target_key and managed_service_key(service.name, service.scope) != target_key:
            updated.append(service)
            continue

        new_service = ManagedService(**asdict(service))
        service_unit = f"{service.name}.service"
        timer_unit = f"{service.name}.timer"

        if unit_exists(service_unit, scope=service.scope):
            show_service = systemctl_show(
                service_unit,
                ["Description", "WorkingDirectory", "User", "Restart"],
                scope=service.scope,
            )
            if not new_service.description and show_service.get("Description"):
                new_service.description = show_service["Description"]
            if not new_service.working_dir and show_service.get("WorkingDirectory"):
                new_service.working_dir = show_service["WorkingDirectory"]
            if not new_service.user and show_service.get("User"):
                new_service.user = show_service["User"]
            if (
                not new_service.restart or new_service.restart == "on-failure"
            ) and show_service.get("Restart"):
                new_service.restart = show_service["Restart"]

        if unit_exists(timer_unit, scope=service.scope):
            if not new_service.schedule:
                new_service.schedule = read_timer_schedule(
                    service.name,
                    scope=service.scope,
                )
            new_service.timer_persistent = read_timer_persistent(
                service.name,
                scope=service.scope,
                default=new_service.timer_persistent,
            )

        if asdict(new_service) != asdict(service):
            changed += 1
            updated.append(new_service)
        else:
            updated.append(service)

    if changed:
        save_registry(updated)
    return changed
