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
