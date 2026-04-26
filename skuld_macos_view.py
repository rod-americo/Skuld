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
