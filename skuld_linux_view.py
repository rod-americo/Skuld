from typing import Callable, Dict, List, Optional, Sequence

import skuld_tables as tables


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


def pid_summary(pids: List[int]) -> str:
    if not pids:
        return "-"
    if len(pids) == 1:
        return str(pids[0])
    return f"{pids[0]}+{len(pids) - 1}"


def build_service_rows(
    services: List[object],
    *,
    service_table_columns: Optional[Sequence[str]] = None,
    sort_by: str = "name",
    unit_exists: Callable[..., bool],
    unit_active: Callable[..., str],
    display_unit_state: Callable[[str], str],
    colorize: Callable[[str, str], str],
    read_unit_usage: Callable[..., Dict[str, str]],
    timer_triggers_for_display: Callable[[object], str],
    read_unit_pids: Callable[..., List[int]],
    read_unit_ports: Callable[..., str],
    load_runtime_stats: Callable[[], Dict[str, Dict[str, int]]],
    format_restarts_exec: Callable[[str, Dict[str, Dict[str, int]]], str],
    read_timer_next_run: Callable[..., str],
    read_timer_last_run: Callable[..., str],
    gpu_memory_by_pid: Optional[Dict[int, int]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    row_keys = tables.service_table_row_keys(service_table_columns, sort_by)
    needs_usage = bool({"cpu", "memory"} & row_keys)
    needs_timer_presence = bool({"timer", "last", "next"} & row_keys)
    runtime_stats = load_runtime_stats() if "runs" in row_keys else {}
    for service in services:
        service_unit = f"{service.name}.service"
        timer_unit = f"{service.name}.timer"
        row: Dict[str, object] = {"id": service.id, "name": service.display_name}
        if "target" in row_keys:
            row["target"] = f"{service.scope}:{service.name}"
        if "scope" in row_keys:
            row["scope"] = service.scope
        if "backend" in row_keys:
            row["backend"] = "systemd"
        if "service" in row_keys:
            service_state_raw = (
                unit_active(service_unit, scope=service.scope)
                if unit_exists(service_unit, scope=service.scope)
                else "missing"
            )
            service_state_display = display_unit_state(service_state_raw)
            row["service"] = service_state_for_display(
                service_state_raw,
                service_state_display,
                colorize,
            )
        timer_exists = False
        if needs_timer_presence:
            timer_exists = unit_exists(timer_unit, scope=service.scope)
        if "timer" in row_keys:
            timer_state_raw = (
                unit_active(timer_unit, scope=service.scope) if timer_exists else "n/a"
            )
            timer_state_display = display_unit_state(timer_state_raw)
            row["timer"] = timer_state_for_display(
                timer_state_raw,
                timer_state_display,
                colorize,
            )
        if "triggers" in row_keys:
            row["triggers"] = timer_triggers_for_display(service)
        if "pid" in row_keys:
            row["pid"] = pid_summary(read_unit_pids(service_unit, scope=service.scope))
        if "user" in row_keys:
            row["user"] = service.user or "-"
        if "restart" in row_keys:
            row["restart"] = service.restart or "-"
        if "runs" in row_keys:
            row["runs"] = format_restarts_exec(service.name, runtime_stats)
        if "last" in row_keys:
            row["last"] = (
                read_timer_last_run(service.name, scope=service.scope)
                if timer_exists
                else "-"
            )
        if "next" in row_keys:
            row["next"] = (
                read_timer_next_run(service.name, scope=service.scope)
                if timer_exists
                else "-"
            )
        if needs_usage:
            usage = read_unit_usage(
                service_unit,
                scope=service.scope,
                gpu_memory_by_pid=gpu_memory_by_pid,
            )
            if "cpu" in row_keys:
                row["cpu"] = usage["cpu"]
            if "memory" in row_keys:
                row["memory"] = usage["memory"]
        if "ports" in row_keys:
            row["ports"] = read_unit_ports(service_unit, scope=service.scope)
        rows.append(row)
    return rows


def render_services_table(
    *,
    compact: bool,
    sort_by: str,
    service_table_columns: Optional[Sequence[str]],
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
    read_unit_pids: Callable[..., List[int]],
    read_unit_ports: Callable[..., str],
    load_runtime_stats: Callable[[], Dict[str, Dict[str, int]]],
    format_restarts_exec: Callable[[str, Dict[str, Dict[str, int]]], str],
    read_timer_next_run: Callable[..., str],
    read_timer_last_run: Callable[..., str],
    render_extra_sections: Callable[[List[object]], None],
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

    row_keys = tables.service_table_row_keys(service_table_columns, sort_by)
    gpu_memory_by_pid = read_gpu_memory_by_pid() if {"cpu", "memory"} & row_keys else None
    emit_blank()
    render_host_panel()
    rows = build_service_rows(
        services,
        service_table_columns=service_table_columns,
        sort_by=sort_by,
        unit_exists=unit_exists,
        unit_active=unit_active,
        display_unit_state=display_unit_state,
        colorize=colorize,
        read_unit_usage=read_unit_usage,
        timer_triggers_for_display=timer_triggers_for_display,
        read_unit_pids=read_unit_pids,
        read_unit_ports=read_unit_ports,
        load_runtime_stats=load_runtime_stats,
        format_restarts_exec=format_restarts_exec,
        read_timer_next_run=read_timer_next_run,
        read_timer_last_run=read_timer_last_run,
        gpu_memory_by_pid=gpu_memory_by_pid,
    )
    ordered_rows = sort_service_rows(rows, sort_by)
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    render_extra_sections(services)
    emit_blank()
