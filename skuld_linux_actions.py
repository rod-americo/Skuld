from typing import Callable, List


def execute_now(
    service: object,
    *,
    run_systemctl_action: Callable[..., object],
    ok: Callable[[str], None],
) -> None:
    service_unit = f"{service.name}.service"
    run_systemctl_action(service.scope, ["start", service_unit])
    ok(
        f"Execution started: {service_unit} "
        f"({service.display_name}, scope={service.scope})"
    )


def _service_has_schedule(service: object) -> bool:
    return bool((service.schedule or "").strip())


def _service_uses_timer(
    service: object,
    *,
    unit_exists: Callable[..., bool],
) -> bool:
    return _service_has_schedule(service) and unit_exists(
        f"{service.name}.timer",
        scope=service.scope,
    )


def apply_lifecycle_action(
    service: object,
    action: str,
    *,
    unit_exists: Callable[..., bool],
    run_systemctl_action: Callable[..., object],
    ok: Callable[[str], None],
) -> None:
    service_unit = f"{service.name}.service"
    timer_unit = f"{service.name}.timer"
    target_unit = (
        timer_unit
        if _service_uses_timer(service, unit_exists=unit_exists)
        else service_unit
    )
    proc = run_systemctl_action(
        service.scope,
        [action, target_unit],
        check=False,
        capture=True,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        message = f"Failed to {action} {target_unit}."
        if details:
            message = f"{message} {details}"
        raise RuntimeError(message)
    ok(f"{action} -> {target_unit} ({service.scope})")


def apply_lifecycle_action_to_services(
    services: List[object],
    action: str,
    *,
    unit_exists: Callable[..., bool],
    run_systemctl_action: Callable[..., object],
    ok: Callable[[str], None],
) -> None:
    for service in services:
        apply_lifecycle_action(
            service,
            action,
            unit_exists=unit_exists,
            run_systemctl_action=run_systemctl_action,
            ok=ok,
        )
