import re
from dataclasses import dataclass
from typing import Dict, Optional

import skuld_common as common
import skuld_linux_systemd as systemd


VALID_SCOPES = ("system", "user")
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._@-]*$")


@dataclass
class ManagedService:
    name: str
    scope: str
    exec_cmd: str
    description: str
    display_name: str = ""
    schedule: str = ""
    working_dir: str = ""
    user: str = ""
    restart: str = "on-failure"
    timer_persistent: bool = True
    id: int = 0


@dataclass
class DiscoverableService:
    index: int
    scope: str
    name: str
    service_state: str
    timer_state: str


def normalize_scope(value: str) -> str:
    return systemd.normalize_scope(value)


def scope_sort_value(scope: str) -> int:
    return 0 if normalize_scope(scope) == "system" else 1


def managed_service_key(name: str, scope: str) -> tuple:
    return (normalize_scope(scope), name)


def managed_sort_key(service: ManagedService) -> tuple:
    return (service.name.lower(), scope_sort_value(service.scope), service.id)


def format_scoped_name(name: str, scope: str) -> str:
    return f"{normalize_scope(scope)}:{name}"


def split_scope_token(token: str) -> tuple[Optional[str], str]:
    raw = (token or "").strip()
    if ":" not in raw:
        return None, raw
    maybe_scope, remainder = raw.split(":", 1)
    try:
        normalized = normalize_scope(maybe_scope)
    except ValueError:
        return None, raw
    if not remainder.strip():
        return None, raw
    return normalized, remainder.strip()


def normalize_registry_item(item: Dict[str, object]) -> ManagedService:
    display_name = str(item.get("display_name", item.get("name", ""))).strip()
    name = str(item.get("name", "")).strip()
    if not display_name:
        display_name = name
    return ManagedService(
        name=name,
        scope=normalize_scope(str(item.get("scope", "system"))),
        exec_cmd=str(item.get("exec_cmd", "")).strip(),
        description=str(item.get("description", "")).strip(),
        display_name=display_name,
        schedule=str(item.get("schedule", "")).strip(),
        working_dir=str(item.get("working_dir", "")).strip(),
        user=str(item.get("user", "")).strip(),
        restart=str(item.get("restart", "on-failure")).strip() or "on-failure",
        timer_persistent=common.parse_bool(str(item.get("timer_persistent", True))),
        id=common.parse_int(str(item.get("id", 0))),
    )


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError(
            "Invalid name. Use [a-zA-Z0-9._@-] and start with a letter/number."
        )


def validate_registry_service(service: ManagedService, _index: int) -> None:
    validate_name(service.name)
    validate_name(service.display_name)
