from typing import Callable, Dict, List, Optional


def service_state_for_display(
    raw_state: str,
    display_state: str,
    colorize: Callable[[str, str], str],
) -> str:
    if raw_state == "active":
        return colorize("active", "green")
    if raw_state == "activating":
        return colorize(display_state, "green")
    if raw_state == "inactive":
        return colorize("inactive", "yellow")
    return colorize(display_state, "red")


def timer_state_for_display(
    raw_state: str,
    display_state: str,
    colorize: Callable[[str, str], str],
) -> str:
    if raw_state == "active":
        return colorize("active", "green")
    if raw_state == "activating":
        return colorize(display_state, "green")
    if raw_state == "inactive":
        return colorize("inactive", "yellow")
    if raw_state == "n/a":
        return colorize("n/a", "gray")
    return colorize(display_state, "red")


def build_service_rows(
    services: List[object],
    *,
    unit_exists: Callable[..., bool],
    unit_active: Callable[..., str],
    display_unit_state: Callable[[str], str],
    colorize: Callable[[str, str], str],
    read_unit_usage: Callable[..., Dict[str, str]],
    timer_triggers_for_display: Callable[[object], str],
    read_unit_ports: Callable[..., str],
    gpu_memory_by_pid: Optional[Dict[int, int]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for service in services:
        service_unit = f"{service.name}.service"
        timer_unit = f"{service.name}.timer"
        service_state_raw = (
            unit_active(service_unit, scope=service.scope)
            if unit_exists(service_unit, scope=service.scope)
            else "missing"
        )
        timer_state_raw = (
            unit_active(timer_unit, scope=service.scope)
            if unit_exists(timer_unit, scope=service.scope)
            else "n/a"
        )
        service_state_display = display_unit_state(service_state_raw)
        timer_state_display = display_unit_state(timer_state_raw)
        usage = read_unit_usage(
            service_unit,
            scope=service.scope,
            gpu_memory_by_pid=gpu_memory_by_pid,
        )
        rows.append(
            {
                "id": service.id,
                "name": service.display_name,
                "service": service_state_for_display(
                    service_state_raw,
                    service_state_display,
                    colorize,
                ),
                "timer": timer_state_for_display(
                    timer_state_raw,
                    timer_state_display,
                    colorize,
                ),
                "triggers": timer_triggers_for_display(service),
                "cpu": usage["cpu"],
                "memory": usage["memory"],
                "ports": read_unit_ports(service_unit, scope=service.scope),
            }
        )
    return rows


def render_services_table(
    *,
    compact: bool,
    sort_by: str,
    require_systemctl: Callable[[], None],
    load_registry: Callable[[], List[object]],
    render_discoverable_services_hint: Callable[[], None],
    read_gpu_memory_by_pid: Callable[[], Optional[Dict[int, int]]],
    render_host_panel: Callable[[], None],
    unit_exists: Callable[..., bool],
    unit_active: Callable[..., str],
    display_unit_state: Callable[[str], str],
    colorize: Callable[[str, str], str],
    read_unit_usage: Callable[..., Dict[str, str]],
    timer_triggers_for_display: Callable[[object], str],
    read_unit_ports: Callable[..., str],
    sort_service_rows: Callable[[List[Dict[str, object]], str], List[Dict[str, object]]],
    fit_service_table: Callable[[List[Dict[str, object]]], tuple[List[str], List[List[str]]]],
    render_table: Callable[[List[str], List[List[str]]], None],
    emit_blank: Callable[[], None] = print,
) -> None:
    del compact
    require_systemctl()
    services = list(load_registry())
    if not services:
        render_discoverable_services_hint()
        return

    gpu_memory_by_pid = read_gpu_memory_by_pid()
    emit_blank()
    render_host_panel()
    rows = build_service_rows(
        services,
        unit_exists=unit_exists,
        unit_active=unit_active,
        display_unit_state=display_unit_state,
        colorize=colorize,
        read_unit_usage=read_unit_usage,
        timer_triggers_for_display=timer_triggers_for_display,
        read_unit_ports=read_unit_ports,
        gpu_memory_by_pid=gpu_memory_by_pid,
    )
    ordered_rows = sort_service_rows(rows, sort_by)
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    emit_blank()
