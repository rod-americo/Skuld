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
    ensure_display_name_available(display_name, current_id=service.id)
    if service.display_name == display_name:
        info("No changes detected.")
        return
    upsert_registry(
        service_factory(
            name=service.name,
            scope=service.scope,
            exec_cmd=service.exec_cmd,
            description=service.description,
            display_name=display_name,
            schedule=service.schedule,
            working_dir=service.working_dir,
            user=service.user,
            restart=service.restart,
            timer_persistent=service.timer_persistent,
            id=service.id,
        )
    )
    ok(f"Renamed '{service.display_name}' to '{display_name}'.")


def untrack_service(
    service: object,
    *,
    remove_registry: Callable[[str, str], None],
    ok: Callable[[str], None],
) -> None:
    remove_registry(service.name, service.scope)
    ok(f"Removed '{service.display_name}' from the skuld registry.")
