from typing import Callable, Dict, List


def service_state_for_display(
    loaded: bool,
    pid: int,
    colorize: Callable[[str, str], str],
) -> str:
    if loaded and pid > 0:
        return colorize("active", "green")
    if loaded:
        return colorize("loaded", "yellow")
    return colorize("inactive", "yellow")


def timer_state_for_display(
    has_schedule: bool,
    loaded: bool,
    colorize: Callable[[str, str], str],
) -> str:
    if not has_schedule:
        return colorize("n/a", "gray")
    if loaded:
        return colorize("scheduled", "green")
    return colorize("inactive", "yellow")


def build_service_rows(
    services: List[object],
    *,
    read_event_stats: Callable[[object], Dict[str, object]],
    read_pid: Callable[[object], int],
    read_cpu_memory: Callable[[int], Dict[str, str]],
    service_loaded: Callable[[object], bool],
    colorize: Callable[[str, str], str],
    humanize_schedule_for_display: Callable[[str, bool], str],
    read_ports: Callable[[int], str],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for service in services:
        read_event_stats(service)
        pid = read_pid(service)
        usage = read_cpu_memory(pid)
        loaded = service_loaded(service)
        rows.append(
            {
                "id": service.id,
                "name": service.display_name,
                "service": service_state_for_display(loaded, pid, colorize),
                "timer": timer_state_for_display(
                    bool(service.schedule),
                    loaded,
                    colorize,
                ),
                "triggers": humanize_schedule_for_display(
                    service.schedule,
                    service.timer_persistent,
                ),
                "cpu": usage["cpu"],
                "memory": usage["memory"],
                "ports": read_ports(pid),
            }
        )
    return rows


def render_services_table(
    *,
    compact: bool,
    sort_by: str,
    load_registry: Callable[[], List[object]],
    render_discoverable_services_hint: Callable[[], None],
    render_host_panel: Callable[[], None],
    read_event_stats: Callable[[object], Dict[str, object]],
    read_pid: Callable[[object], int],
    read_cpu_memory: Callable[[int], Dict[str, str]],
    service_loaded: Callable[[object], bool],
    colorize: Callable[[str, str], str],
    humanize_schedule_for_display: Callable[[str, bool], str],
    read_ports: Callable[[int], str],
    sort_service_rows: Callable[[List[Dict[str, object]], str], List[Dict[str, object]]],
    fit_service_table: Callable[[List[Dict[str, object]]], tuple[List[str], List[List[str]]]],
    render_table: Callable[[List[str], List[List[str]]], None],
    emit_blank: Callable[[], None] = print,
) -> None:
    del compact
    services = list(load_registry())
    if not services:
        render_discoverable_services_hint()
        return

    emit_blank()
    render_host_panel()
    rows = build_service_rows(
        services,
        read_event_stats=read_event_stats,
        read_pid=read_pid,
        read_cpu_memory=read_cpu_memory,
        service_loaded=service_loaded,
        colorize=colorize,
        humanize_schedule_for_display=humanize_schedule_for_display,
        read_ports=read_ports,
    )
    ordered_rows = sort_service_rows(rows, sort_by)
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    emit_blank()
