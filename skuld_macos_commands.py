from typing import Callable


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
