from __future__ import annotations

import os
import plistlib
import shlex
from pathlib import Path
from typing import Callable, Sequence


def command_text(command: Sequence[str]) -> str:
    cleaned = [item for item in command if item]
    if not cleaned:
        raise RuntimeError("Service command is required after '--'.")
    return shlex.join(cleaned)


def wrapper_script_text(*, command: Sequence[str], event_file: Path) -> str:
    payload = command_text(command)
    event_path = shlex.quote(str(event_file))
    event_dir = shlex.quote(str(event_file.parent))
    shell_payload = shlex.quote(payload)
    return "\n".join(
        [
            "#!/bin/sh",
            "set -u",
            f"mkdir -p {event_dir}",
            'ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
            f"printf '{{\"event\":\"start\",\"ts\":\"%s\",\"pid\":%s}}\\n' \"$ts\" \"$$\" >> {event_path}",
            f"/bin/sh -lc {shell_payload}",
            "status=$?",
            'ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
            f"printf '{{\"event\":\"end\",\"ts\":\"%s\",\"exit_status\":%s}}\\n' \"$ts\" \"$status\" >> {event_path}",
            "exit $status",
            "",
        ]
    )


def launch_agent_plist(
    *,
    label: str,
    wrapper_path: Path,
    working_dir: str,
    stdout_path: Path,
    stderr_path: Path,
    restart: str = "on-failure",
) -> bytes:
    payload: dict[str, object] = {
        "Label": label,
        "ProgramArguments": [str(wrapper_path)],
        "WorkingDirectory": working_dir,
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
        "RunAtLoad": False,
    }
    if restart not in {"no", "never"}:
        payload["KeepAlive"] = {"SuccessfulExit": False}
    return plistlib.dumps(payload, sort_keys=True)


def create_agent_service(
    *,
    name: str,
    command: Sequence[str],
    working_dir: str | None,
    service_factory: Callable[..., object],
    validate_name: Callable[[str], None],
    ensure_display_name_available: Callable[..., None],
    get_managed: Callable[[str], object],
    service_label: Callable[[str], str],
    plist_path_for_service: Callable[[object], Path],
    wrapper_script_for_service: Callable[[str, str], Path],
    log_dir_for_service: Callable[[str, str], Path],
    event_file_for_service: Callable[[str, str], Path],
    bootstrap_service: Callable[[object], None],
    kickstart_service: Callable[..., object],
    upsert_registry: Callable[[object], None],
    ok: Callable[[str], None],
) -> object:
    display_name = (name or "").strip()
    validate_name(display_name)
    ensure_display_name_available(display_name)
    if get_managed(display_name):
        raise RuntimeError(f"Service '{display_name}' is already tracked.")

    cwd = str(Path(working_dir or os.getcwd()).resolve())
    label = service_label(display_name)
    log_dir = log_dir_for_service(display_name, "agent")
    event_file = event_file_for_service(display_name, "agent")
    wrapper_path = wrapper_script_for_service(display_name, "agent")
    service = service_factory(
        name=display_name,
        exec_cmd=command_text(command),
        description=f"Skuld managed LaunchAgent: {display_name}",
        display_name=display_name,
        launchd_label=label,
        plist_path_hint="",
        managed_by_skuld=True,
        schedule="",
        working_dir=cwd,
        user="",
        restart="on-failure",
        timer_persistent=True,
        scope="agent",
        log_dir=str(log_dir),
    )
    plist_path = plist_path_for_service(service)
    for path in (plist_path, wrapper_path):
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite existing file: {path}")

    log_dir.mkdir(parents=True, exist_ok=True)
    event_file.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(
        wrapper_script_text(command=command, event_file=event_file),
        encoding="utf-8",
    )
    wrapper_path.chmod(0o755)
    plist_path.write_bytes(
        launch_agent_plist(
            label=label,
            wrapper_path=wrapper_path,
            working_dir=cwd,
            stdout_path=log_dir / "stdout.log",
            stderr_path=log_dir / "stderr.log",
            restart=service.restart,
        )
    )
    upsert_registry(service)
    bootstrap_service(service)
    proc = kickstart_service(service, kill_existing=False)
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Created '{display_name}', but start failed. {details}".strip())
    ok(f"Created and started Skuld-managed LaunchAgent '{display_name}'.")
    return service


def delete_agent_service(
    service: object,
    *,
    bootout_service: Callable[[object], object],
    remove_registry: Callable[[str], None],
    plist_path_for_service: Callable[[object], Path],
    wrapper_script_for_service: Callable[[str, str], Path],
    ok: Callable[[str], None],
) -> None:
    if not getattr(service, "managed_by_skuld", False):
        raise RuntimeError(
            f"'{service.display_name}' is externally tracked. Use 'skuld untrack' "
            "to remove only the registry entry."
        )
    if getattr(service, "scope", "") != "agent":
        raise RuntimeError("Only Skuld-managed LaunchAgents can be deleted without sudo.")

    bootout_service(service)
    for path in (
        plist_path_for_service(service),
        wrapper_script_for_service(service.name, service.scope),
    ):
        if path.exists():
            path.unlink()
    remove_registry(service.name)
    ok(f"Deleted Skuld-managed LaunchAgent '{service.display_name}'.")
