import re
from dataclasses import dataclass
from typing import Callable, Dict

import skuld_common as common


NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._@-]*$")


@dataclass
class ManagedService:
    name: str
    exec_cmd: str
    description: str
    display_name: str = ""
    launchd_label: str = ""
    plist_path_hint: str = ""
    managed_by_skuld: bool = True
    schedule: str = ""
    working_dir: str = ""
    user: str = ""
    restart: str = "on-failure"
    timer_persistent: bool = True
    id: int = 0
    backend: str = "launchd"
    scope: str = "agent"
    log_dir: str = ""


@dataclass
class DiscoverableService:
    index: int
    label: str
    pid: str
    status: str


def resolve_scope(value: str) -> str:
    scope = (value or "agent").strip().lower()
    if scope not in {"daemon", "agent"}:
        raise RuntimeError("Invalid scope. Use 'daemon' or 'agent'.")
    return scope


def normalize_service(
    item: Dict[str, object],
    *,
    log_dir_for_service: Callable[[str, str], object],
    service_label: Callable[[str], str],
) -> ManagedService:
    scope = resolve_scope(str(item.get("scope", "daemon")))
    name = str(item.get("name", "")).strip()
    managed_by_skuld = common.parse_bool(str(item.get("managed_by_skuld", True)))
    log_dir_default = str(log_dir_for_service(name, scope)) if managed_by_skuld else ""
    log_dir = str(item.get("log_dir", "")).strip() or log_dir_default
    return ManagedService(
        name=name,
        exec_cmd=str(item.get("exec_cmd", "")).strip(),
        description=str(item.get("description", "")).strip(),
        display_name=str(item.get("display_name", name)).strip() or name,
        launchd_label=str(item.get("launchd_label", service_label(name))).strip()
        or service_label(name),
        plist_path_hint=str(item.get("plist_path_hint", "")).strip(),
        managed_by_skuld=managed_by_skuld,
        schedule=str(item.get("schedule", "")).strip(),
        working_dir=str(item.get("working_dir", "")).strip(),
        user=str(item.get("user", "")).strip(),
        restart=str(item.get("restart", "on-failure")).strip() or "on-failure",
        timer_persistent=common.parse_bool(str(item.get("timer_persistent", True))),
        id=common.parse_int(str(item.get("id", 0))),
        backend="launchd",
        scope=scope,
        log_dir=log_dir,
    )


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError(
            "Invalid name. Use [a-zA-Z0-9._@-] and start with a letter/number."
        )


def validate_registry_service(service: ManagedService, index: int) -> None:
    validate_name(service.name)
    validate_name(service.display_name)
    if service.scope == "agent" and service.user:
        raise RuntimeError(
            f"Invalid registry entry #{index}: 'user' is only valid for daemon scope."
        )


def managed_sort_key(service: ManagedService) -> tuple:
    return (service.name.lower(), service.id)
