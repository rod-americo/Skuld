from pathlib import Path
from typing import Dict, List


def status_lines(
    service: object,
    *,
    label: str,
    domain: str,
    info_map: Dict[str, str],
    plist_path: Path,
) -> List[str]:
    return [
        f"name: {service.display_name}",
        f"target: {service.name}",
        f"label: {label}",
        f"scope: {service.scope}",
        f"domain: {domain}",
        f"loaded: {'yes' if info_map else 'no'}",
        f"pid: {info_map.get('PID', '-') if info_map else '-'}",
        (
            "last_exit_status: "
            f"{info_map.get('LastExitStatus', '-') if info_map else '-'}"
        ),
        f"plist: {plist_path}",
    ]


def stats_lines(service: object, item: Dict[str, object]) -> List[str]:
    return [
        f"name: {service.display_name}",
        f"target: {service.name}",
        f"scope: {service.scope}",
        "window: all retained event entries",
        f"executions: {item.get('executions', 0)}",
        f"restarts: {item.get('restarts', 0)}",
        f"last_run: {item.get('last_run', '-')}",
        f"last_exit_status: {item.get('last_exit_status', '-')}",
    ]


def describe_lines(
    service: object,
    *,
    info_map: Dict[str, str],
    stats_map: Dict[str, object],
    next_run: str,
    plist_path: Path,
) -> List[str]:
    return [
        f"name: {service.display_name}",
        f"target: {service.name}",
        f"description: {service.description}",
        f"exec: {service.exec_cmd}",
        f"scope: {service.scope}",
        f"user: {service.user or '-'}",
        f"working_dir: {service.working_dir or '-'}",
        f"restart: {service.restart}",
        f"schedule: {service.schedule or '-'}",
        f"timer_persistent: {service.timer_persistent}",
        f"log_dir: {service.log_dir}",
        "---",
        f"loaded: {'yes' if info_map else 'no'}",
        f"pid: {info_map.get('PID', '-') if info_map else '-'}",
        f"last_exit_status: {info_map.get('LastExitStatus', '-') if info_map else '-'}",
        f"next_run: {next_run}",
        f"last_run: {stats_map.get('last_run', '-')}",
        f"plist: {plist_path}",
    ]


def print_lines(lines: List[str]) -> None:
    for line in lines:
        print(line)
