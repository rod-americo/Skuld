from typing import Callable, Dict, List, Optional, Sequence

import skuld_tables as tables


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


def pid_for_display(pid: int) -> str:
    return str(pid) if pid > 0 else "-"


def build_service_rows(
    services: List[object],
    *,
    service_table_columns: Optional[Sequence[str]] = None,
    sort_by: str = "name",
    read_event_stats: Callable[[object], Dict[str, object]],
    read_pid: Callable[[object], int],
    read_cpu_memory: Callable[[int], Dict[str, str]],
    service_loaded: Callable[[object], bool],
    colorize: Callable[[str, str], str],
    humanize_schedule_for_display: Callable[[str, bool], str],
    compute_next_run: Callable[[str], str],
    read_ports: Callable[[int], str],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    row_keys = tables.service_table_row_keys(service_table_columns, sort_by)
    needs_pid = bool({"service", "pid", "cpu", "memory", "ports"} & row_keys)
    needs_usage = bool({"cpu", "memory"} & row_keys)
    needs_loaded = bool({"service", "timer"} & row_keys)
    needs_stats = bool({"runs", "last"} & row_keys)
    for service in services:
        stats = read_event_stats(service) if needs_stats else {}
        pid = read_pid(service) if needs_pid else 0
        loaded = service_loaded(service) if needs_loaded else False
        row: Dict[str, object] = {"id": service.id, "name": service.display_name}
        if "target" in row_keys:
            row["target"] = getattr(service, "launchd_label", service.name) or service.name
        if "scope" in row_keys:
            row["scope"] = service.scope
        if "backend" in row_keys:
            row["backend"] = getattr(service, "backend", "launchd") or "launchd"
        if "service" in row_keys:
            row["service"] = service_state_for_display(loaded, pid, colorize)
        if "timer" in row_keys:
            row["timer"] = timer_state_for_display(
                bool(service.schedule),
                loaded,
                colorize,
            )
        if "triggers" in row_keys:
            row["triggers"] = humanize_schedule_for_display(
                service.schedule,
                service.timer_persistent,
            )
        if "pid" in row_keys:
            row["pid"] = pid_for_display(pid)
        if "user" in row_keys:
            row["user"] = service.user or "-"
        if "restart" in row_keys:
            row["restart"] = service.restart or "-"
        if "runs" in row_keys:
            row["runs"] = f"{stats.get('restarts', 0)}/{stats.get('executions', 0)}"
        if "last" in row_keys:
            row["last"] = str(stats.get("last_run", "-") or "-")
        if "next" in row_keys:
            row["next"] = compute_next_run(service.schedule)
        if needs_usage:
            usage = read_cpu_memory(pid)
            if "cpu" in row_keys:
                row["cpu"] = usage["cpu"]
            if "memory" in row_keys:
                row["memory"] = usage["memory"]
        if "ports" in row_keys:
            row["ports"] = read_ports(pid)
        rows.append(row)
    return rows


def render_services_table(
    *,
    compact: bool,
    sort_by: str,
    service_table_columns: Optional[Sequence[str]],
    load_registry: Callable[[], List[object]],
    render_discoverable_services_hint: Callable[[], None],
    render_host_panel: Callable[[], None],
    read_event_stats: Callable[[object], Dict[str, object]],
    read_pid: Callable[[object], int],
    read_cpu_memory: Callable[[int], Dict[str, str]],
    service_loaded: Callable[[object], bool],
    colorize: Callable[[str, str], str],
    humanize_schedule_for_display: Callable[[str, bool], str],
    compute_next_run: Callable[[str], str],
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
        service_table_columns=service_table_columns,
        sort_by=sort_by,
        read_event_stats=read_event_stats,
        read_pid=read_pid,
        read_cpu_memory=read_cpu_memory,
        service_loaded=service_loaded,
        colorize=colorize,
        humanize_schedule_for_display=humanize_schedule_for_display,
        compute_next_run=compute_next_run,
        read_ports=read_ports,
    )
    ordered_rows = sort_service_rows(rows, sort_by)
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    emit_blank()
