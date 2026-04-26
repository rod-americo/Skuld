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


def doctor_services(
    services: List[object],
    *,
    unit_exists: Callable[..., bool],
    unit_active: Callable[..., str],
    display_unit_state: Callable[[str], str],
    read_timer_schedule: Callable[..., str],
    systemctl_cat: Callable[..., str],
    parse_unit_directives: Callable[[str], dict],
    format_scoped_name: Callable[[str, str], str],
    ok: Callable[[str], None],
    err: Callable[[str], None],
    emit: Callable[[str], None] = print,
) -> int:
    issues = 0
    for service in services:
        service_unit = f"{service.name}.service"
        timer_unit = f"{service.name}.timer"
        line_prefix = (
            f"[{service.display_name}|"
            f"{format_scoped_name(service.name, service.scope)}]"
        )

        if not unit_exists(service_unit, scope=service.scope):
            emit(f"{line_prefix} ERROR missing service unit ({service_unit})")
            issues += 1
        else:
            state = unit_active(service_unit, scope=service.scope)
            emit(f"{line_prefix} service={display_unit_state(state)}")

        has_timer = bool(service.schedule)
        runtime_schedule = read_timer_schedule(service.name, scope=service.scope)
        if not has_timer and runtime_schedule:
            emit(
                f"{line_prefix} WARN registry schedule is empty, "
                f"but timer OnCalendar is '{runtime_schedule}'"
            )
            issues += 1
        if has_timer and not unit_exists(timer_unit, scope=service.scope):
            emit(f"{line_prefix} ERROR expected timer is missing ({timer_unit})")
            issues += 1
        if (not has_timer) and unit_exists(timer_unit, scope=service.scope):
            emit(f"{line_prefix} WARN timer exists, but registry has no schedule")
            issues += 1

        if unit_exists(service_unit, scope=service.scope):
            directives = parse_unit_directives(
                systemctl_cat(service_unit, scope=service.scope)
            )
            current_exec = directives.get("ExecStart", "")
            if service.exec_cmd and service.exec_cmd not in current_exec:
                emit(f"{line_prefix} WARN ExecStart differs from registry")
                issues += 1

    if issues == 0:
        ok("doctor: no issues found.")
    else:
        err(f"doctor: found {issues} issue(s).")
    return issues
