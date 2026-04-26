import sys
from typing import Callable, List

import skuld_linux_presenters as presenters


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


def show_logs(
    service: object,
    *,
    timer: bool,
    since: str,
    follow: bool,
    plain: bool,
    output: str,
    lines: int,
    journalctl_command: Callable[[str, List[str]], List[str]],
    systemd_scope_env: Callable[[str], object],
    run: Callable[..., object],
    run_sudo: Callable[..., object],
    journal_permission_hint: Callable[[str], bool],
    emit: Callable[[str], None] = print,
    emit_err: Callable[[str], None] = lambda message: print(message, file=sys.stderr),
) -> None:
    unit = f"{service.name}.timer" if timer else f"{service.name}.service"
    scope_env = systemd_scope_env(service.scope)
    command = journalctl_command(service.scope, ["-u", unit, "-n", str(lines)])
    output_mode = "cat" if plain else output
    command.extend(["-o", output_mode])
    if since:
        command.extend(["--since", since])
    if follow:
        command.append("-f")
        probe_command = [item for item in command if item != "-f"] + [
            "-n",
            "1",
            "--no-pager",
        ]
        probe = run(probe_command, check=False, capture=True, env=scope_env)
        probe_error = (probe.stderr or "").lower()
        needs_sudo = service.scope == "system" and (
            "not seeing messages from other users and the system" in probe_error
            or "permission denied" in probe_error
        )
        if needs_sudo:
            run_sudo(command, check=False)
        else:
            run(command, check=False, env=scope_env)
        return

    command.append("--no-pager")
    proc = run(command, check=False, capture=True, env=scope_env)
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()

    if service.scope == "system" and journal_permission_hint(stderr):
        proc = run_sudo(command, check=False, capture=True)
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()

    if stdout:
        emit(stdout)
    if stderr:
        emit_err(stderr)


def show_status(
    service: object,
    *,
    format_scoped_name: Callable[[str, str], str],
    systemd_scope_env: Callable[[str], object],
    systemctl_command: Callable[[str, List[str]], List[str]],
    run: Callable[..., object],
    emit: Callable[[str], None] = print,
) -> None:
    emit(f"[skuld] {service.display_name} -> {format_scoped_name(service.name, service.scope)}")
    scope_env = systemd_scope_env(service.scope)
    run(
        systemctl_command(
            service.scope,
            ["status", f"{service.name}.service", "--no-pager"],
        ),
        check=False,
        env=scope_env,
    )
    run(
        systemctl_command(
            service.scope,
            ["status", f"{service.name}.timer", "--no-pager"],
        ),
        check=False,
        env=scope_env,
    )


def show_stats(
    service: object,
    *,
    since: str,
    boot: bool,
    sync_registry_from_systemd: Callable[[object], int],
    count_unit_starts: Callable[..., int],
    read_restart_count: Callable[..., str],
    format_scoped_name: Callable[[str, str], str],
) -> None:
    sync_registry_from_systemd(service)
    service_unit = f"{service.name}.service"
    executions = count_unit_starts(
        service_unit,
        scope=service.scope,
        since=since,
        boot=boot,
    )
    restarts = read_restart_count(service.name, scope=service.scope)
    presenters.print_lines(
        presenters.stats_lines(
            service,
            target=format_scoped_name(service.name, service.scope),
            service_unit=service_unit,
            window=presenters.stats_window(boot=boot, since=since),
            executions=executions,
            restarts=restarts,
        )
    )


def describe_service(
    target: object,
    *,
    require_managed: Callable[..., object],
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., dict],
    format_scoped_name: Callable[[str, str], str],
) -> None:
    service = require_managed(target.name, scope=target.scope)
    service_unit = f"{service.name}.service"
    timer_unit = f"{service.name}.timer"
    show_service = systemctl_show(
        service_unit,
        ["Id", "Description", "ActiveState", "SubState", "FragmentPath", "MainPID"],
        scope=service.scope,
    )
    show_timer = (
        systemctl_show(
            timer_unit,
            ["Id", "ActiveState", "SubState", "NextElapseUSecRealtime", "LastTriggerUSec"],
            scope=service.scope,
        )
        if unit_exists(timer_unit, scope=service.scope)
        else {}
    )
    presenters.print_lines(
        presenters.describe_lines(
            service,
            target=format_scoped_name(service.name, service.scope),
            show_service=show_service,
            show_timer=show_timer,
        )
    )
