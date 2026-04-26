from typing import Dict, List


def stats_window(*, boot: bool, since: str) -> str:
    if boot:
        return "current boot"
    if since:
        return f"since {since}"
    return "all retained journal entries"


def stats_lines(
    service: object,
    *,
    target: str,
    service_unit: str,
    window: str,
    executions: int,
    restarts: str,
) -> List[str]:
    return [
        f"name: {service.display_name}",
        f"target: {target}",
        f"scope: {service.scope}",
        f"service_unit: {service_unit}",
        f"window: {window}",
        f"executions: {executions}",
        f"restarts: {restarts}",
    ]


def describe_lines(
    service: object,
    *,
    target: str,
    show_service: Dict[str, str],
    show_timer: Dict[str, str],
) -> List[str]:
    lines = [
        f"name: {service.display_name}",
        f"target: {target}",
        f"scope: {service.scope}",
        f"description: {service.description}",
        f"exec: {service.exec_cmd}",
        f"working_dir: {service.working_dir or '-'}",
        f"user: {service.user or '-'}",
        f"restart: {service.restart}",
        f"schedule: {service.schedule or '-'}",
        f"timer_persistent: {service.timer_persistent}",
        "---",
        f"service_active: {show_service.get('ActiveState', 'unknown')}",
        f"service_substate: {show_service.get('SubState', 'unknown')}",
        f"main_pid: {show_service.get('MainPID', '-')}",
        f"fragment: {show_service.get('FragmentPath', '-')}",
    ]
    if show_timer:
        lines.extend(
            [
                f"timer_active: {show_timer.get('ActiveState', 'unknown')}",
                f"timer_substate: {show_timer.get('SubState', 'unknown')}",
                f"next_run: {show_timer.get('NextElapseUSecRealtime', '-')}",
                f"last_trigger: {show_timer.get('LastTriggerUSec', '-')}",
            ]
        )
    else:
        lines.append("timer: n/a")
    return lines


def print_lines(lines: List[str]) -> None:
    for line in lines:
        print(line)
