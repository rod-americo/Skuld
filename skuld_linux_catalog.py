from typing import Callable, Dict, List, Optional, Set

from skuld_linux_model import (
    DiscoverableService,
    ManagedService,
    NAME_RE,
    VALID_SCOPES,
    format_scoped_name,
    normalize_scope,
    scope_sort_value,
)


DISCOVERABLE_SCOPE_CHOICES = ("all", "system", "user")


def list_discoverable_services_for_scope(
    scope: str,
    *,
    run: Callable[..., object],
    systemctl_command: Callable[[str, List[str]], List[str]],
    systemd_scope_env: Callable[[str], object],
) -> List[DiscoverableService]:
    proc = run(
        systemctl_command(
            scope,
            [
                "list-unit-files",
                "--type=service",
                "--type=timer",
                "--no-legend",
                "--no-pager",
            ],
        ),
        check=False,
        capture=True,
        env=systemd_scope_env(scope),
    )
    if proc.returncode != 0:
        return []
    discovered: Dict[str, Dict[str, str]] = {}
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        unit_name = parts[0].strip()
        state = parts[1].strip()
        if unit_name.endswith(".service"):
            base_name = unit_name[:-8]
            kind = "service"
        elif unit_name.endswith(".timer"):
            base_name = unit_name[:-6]
            kind = "timer"
        else:
            continue
        if not NAME_RE.match(base_name):
            continue
        entry = discovered.setdefault(base_name, {"service": "", "timer": ""})
        entry[kind] = state

    result: List[DiscoverableService] = []
    names = sorted(name for name, states in discovered.items() if states.get("service"))
    for name in names:
        states = discovered[name]
        result.append(
            DiscoverableService(
                index=0,
                scope=normalize_scope(scope),
                name=name,
                service_state=states.get("service", "") or "-",
                timer_state=states.get("timer", "") or "n/a",
            )
        )
    return result


def normalize_discoverable_scope(value: Optional[str]) -> str:
    raw = (value or "all").strip().lower()
    if raw not in DISCOVERABLE_SCOPE_CHOICES:
        raise ValueError(
            f"Invalid catalog scope '{value}'. Use 'all', 'system', or 'user'."
        )
    return raw


def list_discoverable_services(
    scope_filter: str,
    *,
    require_systemctl: Callable[[], None],
    list_scope: Callable[[str], List[DiscoverableService]],
) -> List[DiscoverableService]:
    require_systemctl()
    normalized_scope = normalize_discoverable_scope(scope_filter)
    entries = list_scope("system") + list_scope("user")
    entries.sort(key=lambda item: (item.name.lower(), scope_sort_value(item.scope)))
    for index, entry in enumerate(entries, start=1):
        entry.index = index
    if normalized_scope == "all":
        return entries
    return [entry for entry in entries if entry.scope == normalized_scope]


def render_discoverable_services_hint(
    *,
    empty_registry_note: bool,
    scope_filter: str,
    list_discoverable_services: Callable[..., List[DiscoverableService]],
    emit: Callable[[str], None] = print,
) -> None:
    if empty_registry_note:
        emit("No services tracked by skuld.")
    normalized_scope = normalize_discoverable_scope(scope_filter)
    entries = list_discoverable_services(scope_filter=normalized_scope)
    if not entries:
        if normalized_scope == "all":
            emit("No systemd services were found.")
        else:
            emit(f"No {normalized_scope} systemd services were found.")
        return
    if normalized_scope == "all":
        emit("Available systemd services (system + user):")
    else:
        emit(f"Available systemd services ({normalized_scope} only):")
    for entry in entries:
        emit(
            f"  {entry.index}. [{entry.scope}] {entry.name}  "
            f"service={entry.service_state}  timer={entry.timer_state}"
        )
    emit("")
    emit(
        "Use: skuld track <id ...>, skuld track <service ...>, "
        "or skuld track <system:name|user:name ...>"
    )


def resolve_discoverable_target_by_name(
    name: str,
    scope: Optional[str],
    entries: List[DiscoverableService],
    *,
    unit_exists: Callable[..., bool],
) -> DiscoverableService:
    matches = [
        entry
        for entry in entries
        if entry.name == name and (scope is None or entry.scope == scope)
    ]
    known_scopes = {entry.scope for entry in matches}
    if scope is None:
        for candidate_scope in VALID_SCOPES:
            if candidate_scope in known_scopes:
                continue
            if unit_exists(f"{name}.service", scope=candidate_scope):
                matches.append(
                    DiscoverableService(
                        index=0,
                        scope=candidate_scope,
                        name=name,
                        service_state="-",
                        timer_state="n/a",
                    )
                )
    elif not matches and unit_exists(f"{name}.service", scope=scope):
        matches.append(
            DiscoverableService(
                index=0,
                scope=scope,
                name=name,
                service_state="-",
                timer_state="n/a",
            )
        )

    if not matches:
        if scope is not None:
            raise RuntimeError(
                f"Service '{name}.service' does not exist in the {scope} "
                "systemd catalog."
            )
        raise RuntimeError(f"Service '{name}.service' does not exist in systemd.")
    if len(matches) > 1:
        scopes = ", ".join(
            format_scoped_name(name, item.scope)
            for item in sorted(matches, key=lambda item: scope_sort_value(item.scope))
        )
        raise RuntimeError(
            f"Service '{name}' exists in multiple scopes. Use one of: {scopes}."
        )
    return matches[0]


def resolve_discoverable_targets(
    targets: List[str],
    *,
    list_discoverable_services: Callable[[], List[DiscoverableService]],
    normalize_target_token: Callable[[str], tuple[Optional[str], str]],
    unit_exists: Callable[..., bool],
) -> List[DiscoverableService]:
    entries = list_discoverable_services()
    by_index = {entry.index: entry for entry in entries}
    resolved: List[DiscoverableService] = []
    seen: Set[tuple] = set()
    for raw_target in targets:
        token = (raw_target or "").strip()
        if not token:
            continue
        if token.isdigit():
            entry = by_index.get(int(token))
            if not entry:
                raise RuntimeError(f"Catalog id '{token}' not found.")
        else:
            scope, name = normalize_target_token(token)
            entry = resolve_discoverable_target_by_name(
                name,
                scope,
                entries,
                unit_exists=unit_exists,
            )
        key = (entry.scope, entry.name)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(entry)
    if not resolved:
        raise RuntimeError(
            "Use: skuld track <id ...>, skuld track <service ...>, "
            "or skuld track <system:name|user:name ...>"
        )
    return resolved


def parse_unit_directives(unit_text: str) -> Dict[str, str]:
    directives: Dict[str, str] = {}
    for raw in unit_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        directives[key] = value
    return directives


def _normalize_exec_start(exec_line: str, fallback: str) -> str:
    if exec_line.startswith("/bin/bash -lc "):
        exec_line = exec_line[len("/bin/bash -lc ") :].strip()
        if (
            len(exec_line) >= 2
            and exec_line[0] == exec_line[-1]
            and exec_line[0] in ("'", '"')
        ):
            exec_line = exec_line[1:-1]
    return exec_line or fallback


def track_services(
    targets: List[str],
    *,
    alias: str,
    resolve_discoverable_targets: Callable[[List[str]], List[DiscoverableService]],
    suggest_display_name: Callable[[str], str],
    prompt_display_name: Callable[[str, str], str],
    ensure_display_name_available: Callable[[str], None],
    get_managed: Callable[..., Optional[ManagedService]],
    systemctl_cat: Callable[..., str],
    systemctl_show: Callable[..., Dict[str, str]],
    unit_exists: Callable[..., bool],
    parse_bool: Callable[..., bool],
    service_factory: Callable[..., ManagedService],
    upsert_registry: Callable[[ManagedService], None],
    ok: Callable[[str], None],
) -> None:
    if not targets:
        raise RuntimeError(
            "Use: skuld track <id ...>, skuld track <service ...>, "
            "or skuld track <system:name|user:name ...>"
        )
    if alias and len(targets) != 1:
        raise RuntimeError("--alias can only be used when tracking exactly one service.")

    resolved = resolve_discoverable_targets(targets)
    for entry in resolved:
        name = entry.name
        suggested = suggest_display_name(name)
        target_label = format_scoped_name(name, entry.scope)
        display_name = (alias or prompt_display_name(target_label, suggested)).strip()
        ensure_display_name_available(display_name)
        if get_managed(name, scope=entry.scope):
            raise RuntimeError(f"'{target_label}' is already tracked in skuld.")

        service_unit = f"{name}.service"
        timer_unit = f"{name}.timer"
        directives = parse_unit_directives(systemctl_cat(service_unit, scope=entry.scope))
        exec_line = _normalize_exec_start(directives.get("ExecStart", ""), service_unit)
        show_service = systemctl_show(
            service_unit,
            ["Description", "WorkingDirectory", "User", "Restart"],
            scope=entry.scope,
        )
        schedule = ""
        timer_persistent = True
        if unit_exists(timer_unit, scope=entry.scope):
            show_timer = systemctl_show(
                timer_unit,
                ["OnCalendar", "Persistent"],
                scope=entry.scope,
            )
            schedule = show_timer.get("OnCalendar", "") or ""
            timer_persistent = parse_bool(
                show_timer.get("Persistent", "true"),
                default=True,
            )

        upsert_registry(
            service_factory(
                name=name,
                scope=entry.scope,
                exec_cmd=exec_line,
                description=show_service.get("Description", "") or name,
                display_name=display_name,
                schedule=schedule,
                working_dir=show_service.get("WorkingDirectory", ""),
                user=show_service.get("User", ""),
                restart=show_service.get("Restart", "on-failure") or "on-failure",
                timer_persistent=timer_persistent,
            )
        )
        ok(f"Tracked '{target_label}' as '{display_name}'.")
