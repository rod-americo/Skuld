from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Callable, Sequence


def user_service_unit_path(name: str, *, home: Path | None = None) -> Path:
    root = home or Path.home()
    return root / ".config/systemd/user" / f"{name}.service"


def command_text(command: Sequence[str]) -> str:
    cleaned = [item for item in command if item]
    if not cleaned:
        raise RuntimeError("Service command is required after '--'.")
    return shlex.join(cleaned)


def service_unit_text(
    *,
    display_name: str,
    command: Sequence[str],
    working_dir: str,
    restart: str = "on-failure",
) -> str:
    shell_command = f"exec {command_text(command)}"
    return "\n".join(
        [
            "[Unit]",
            f"Description=Skuld managed service: {display_name}",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={working_dir}",
            f"ExecStart=/bin/sh -lc {shlex.quote(shell_command)}",
            f"Restart={restart}",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def create_user_service(
    *,
    name: str,
    command: Sequence[str],
    working_dir: str | None,
    service_factory: Callable[..., object],
    validate_name: Callable[[str], None],
    ensure_display_name_available: Callable[..., None],
    get_managed: Callable[..., object],
    unit_exists: Callable[..., bool],
    run_systemctl_action: Callable[..., object],
    upsert_registry: Callable[[object], None],
    ok: Callable[[str], None],
    unit_path_for_name: Callable[[str], Path] = user_service_unit_path,
) -> object:
    display_name = (name or "").strip()
    validate_name(display_name)
    ensure_display_name_available(display_name)
    if get_managed(display_name, scope="user"):
        raise RuntimeError(f"Service '{display_name}' is already tracked.")
    if unit_exists(f"{display_name}.service", scope="user"):
        raise RuntimeError(f"User service '{display_name}.service' already exists.")

    unit_path = unit_path_for_name(display_name)
    if unit_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing unit: {unit_path}")

    cwd = str(Path(working_dir or os.getcwd()).resolve())
    exec_cmd = command_text(command)
    service = service_factory(
        name=display_name,
        scope="user",
        exec_cmd=exec_cmd,
        description=f"Skuld managed user service: {display_name}",
        display_name=display_name,
        schedule="",
        working_dir=cwd,
        user="",
        restart="on-failure",
        timer_persistent=True,
        managed_by_skuld=True,
    )

    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        service_unit_text(
            display_name=display_name,
            command=command,
            working_dir=cwd,
            restart=service.restart,
        ),
        encoding="utf-8",
    )
    run_systemctl_action("user", ["daemon-reload"])
    upsert_registry(service)
    proc = run_systemctl_action(
        "user",
        ["start", f"{display_name}.service"],
        check=False,
        capture=True,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Created '{display_name}', but start failed. {details}".strip())
    ok(f"Created and started Skuld-managed user service '{display_name}'.")
    return service


def delete_user_service(
    service: object,
    *,
    remove_registry: Callable[[str, str], None],
    run_systemctl_action: Callable[..., object],
    ok: Callable[[str], None],
    unit_path_for_name: Callable[[str], Path] = user_service_unit_path,
) -> None:
    if not getattr(service, "managed_by_skuld", False):
        raise RuntimeError(
            f"'{service.display_name}' is externally tracked. Use 'skuld untrack' "
            "to remove only the registry entry."
        )
    if getattr(service, "scope", "") != "user":
        raise RuntimeError("Only Skuld-managed user services can be deleted without sudo.")

    unit_name = f"{service.name}.service"
    run_systemctl_action("user", ["stop", unit_name], check=False, capture=True)
    run_systemctl_action("user", ["disable", unit_name], check=False, capture=True)
    unit_path = unit_path_for_name(service.name)
    if unit_path.exists():
        unit_path.unlink()
    run_systemctl_action("user", ["daemon-reload"], check=False, capture=True)
    run_systemctl_action("user", ["reset-failed", unit_name], check=False, capture=True)
    remove_registry(service.name, service.scope)
    ok(f"Deleted Skuld-managed user service '{service.display_name}'.")
