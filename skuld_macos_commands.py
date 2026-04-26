from pathlib import Path
from typing import Callable, List


def rename_service(
    service: object,
    new_name: str,
    *,
    ensure_display_name_available: Callable[..., None],
    service_factory: Callable[..., object],
    upsert_registry: Callable[[object], None],
    info: Callable[[str], None],
    ok: Callable[[str], None],
) -> None:
    display_name = (new_name or "").strip()
    ensure_display_name_available(display_name, current_name=service.name)
    if service.display_name == display_name:
        info("No changes detected.")
        return
    upsert_registry(
        service_factory(
            name=service.name,
            exec_cmd=service.exec_cmd,
            description=service.description,
            display_name=display_name,
            launchd_label=service.launchd_label,
            plist_path_hint=service.plist_path_hint,
            managed_by_skuld=service.managed_by_skuld,
            schedule=service.schedule,
            working_dir=service.working_dir,
            user=service.user,
            restart=service.restart,
            timer_persistent=service.timer_persistent,
            id=service.id,
            backend=service.backend,
            scope=service.scope,
            log_dir=service.log_dir,
        )
    )
    ok(f"Renamed '{service.display_name}' to '{display_name}'.")


def untrack_service(
    service: object,
    *,
    remove_registry: Callable[[str], None],
    ok: Callable[[str], None],
) -> None:
    remove_registry(service.name)
    ok(f"Removed '{service.display_name}' from the skuld registry.")


def doctor_services(
    services: List[object],
    *,
    plist_path_for_service: Callable[[object], Path],
    wrapper_script_for_service: Callable[[str, str], Path],
    service_loaded: Callable[[object], bool],
    ok: Callable[[str], None],
    err: Callable[[str], None],
    emit: Callable[[str], None] = print,
) -> int:
    issues = 0
    for service in services:
        prefix = f"[{service.display_name}|{service.name}]"
        plist_path = plist_path_for_service(service)
        if not plist_path.exists():
            emit(f"{prefix} ERROR missing plist ({plist_path})")
            issues += 1
        else:
            emit(f"{prefix} plist=ok")
        if service.managed_by_skuld and not wrapper_script_for_service(
            service.name,
            service.scope,
        ).exists():
            emit(f"{prefix} ERROR missing wrapper script")
            issues += 1
        loaded = service_loaded(service)
        emit(f"{prefix} loaded={'yes' if loaded else 'no'}")
        if service.scope == "agent" and service.user:
            emit(f"{prefix} ERROR agent scope cannot store user")
            issues += 1
    if issues == 0:
        ok("doctor: no issues found.")
    else:
        err(f"doctor: found {issues} issue(s).")
    return issues
