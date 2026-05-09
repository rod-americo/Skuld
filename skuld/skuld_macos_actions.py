from typing import Callable, List


def _service_uses_schedule(service: object) -> bool:
    return bool(service.schedule)


def _known_root_pids(
    service: object,
    *,
    read_pid: Callable[[object], int],
    read_recent_run_root_pids: Callable[[object], List[int]],
) -> tuple[int, List[int]]:
    pid = read_pid(service)
    extra_pids = read_recent_run_root_pids(service)
    return pid, extra_pids


def _terminate_known_roots(
    pid: int,
    extra_pids: List[int],
    *,
    terminate_process_tree: Callable[[int], None],
) -> None:
    terminate_process_tree(pid)
    for extra_pid in extra_pids:
        if extra_pid != pid:
            terminate_process_tree(extra_pid)


def apply_lifecycle_action(
    service: object,
    action: str,
    *,
    bootstrap_service: Callable[[object], None],
    bootout_service: Callable[[object], None],
    kickstart_service: Callable[..., object],
    read_pid: Callable[[object], int],
    read_recent_run_root_pids: Callable[[object], List[int]],
    terminate_process_tree: Callable[[int], None],
    ok: Callable[[str], None],
) -> None:
    if action == "start":
        bootstrap_service(service)
        if not _service_uses_schedule(service):
            proc = kickstart_service(service, kill_existing=False)
            if proc.returncode != 0:
                details = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(
                    f"Failed to start {service.name}. {details}".strip()
                )
        ok(f"start -> {service.display_name}")
        return

    if action == "stop":
        pid, extra_pids = _known_root_pids(
            service,
            read_pid=read_pid,
            read_recent_run_root_pids=read_recent_run_root_pids,
        )
        bootout_service(service)
        _terminate_known_roots(
            pid,
            extra_pids,
            terminate_process_tree=terminate_process_tree,
        )
        ok(f"stop -> {service.display_name}")
        return

    if action == "restart":
        pid, extra_pids = _known_root_pids(
            service,
            read_pid=read_pid,
            read_recent_run_root_pids=read_recent_run_root_pids,
        )
        bootout_service(service)
        _terminate_known_roots(
            pid,
            extra_pids,
            terminate_process_tree=terminate_process_tree,
        )
        bootstrap_service(service)
        if not _service_uses_schedule(service):
            proc = kickstart_service(service, kill_existing=True)
            if proc.returncode != 0:
                details = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(
                    f"Failed to restart {service.name}. {details}".strip()
                )
        ok(f"restart -> {service.display_name}")
        return

    raise RuntimeError(f"Unsupported action: {action}")


def apply_lifecycle_action_to_services(
    services: List[object],
    action: str,
    *,
    bootstrap_service: Callable[[object], None],
    bootout_service: Callable[[object], None],
    kickstart_service: Callable[..., object],
    read_pid: Callable[[object], int],
    read_recent_run_root_pids: Callable[[object], List[int]],
    terminate_process_tree: Callable[[int], None],
    ok: Callable[[str], None],
) -> None:
    for service in services:
        apply_lifecycle_action(
            service,
            action,
            bootstrap_service=bootstrap_service,
            bootout_service=bootout_service,
            kickstart_service=kickstart_service,
            read_pid=read_pid,
            read_recent_run_root_pids=read_recent_run_root_pids,
            terminate_process_tree=terminate_process_tree,
            ok=ok,
        )


def execute_now(
    service: object,
    *,
    bootstrap_service: Callable[[object], None],
    kickstart_service: Callable[..., object],
    ok: Callable[[str], None],
) -> None:
    bootstrap_service(service)
    proc = kickstart_service(service, kill_existing=False)
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Failed to execute {service.name}. {details}".strip())
    ok(f"Execution started: {service.display_name}")
