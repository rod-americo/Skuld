from typing import Callable, List, Optional

from skuld_macos_model import DiscoverableService, ManagedService


def discover_launchd_services(*, run: Callable[..., object]) -> List[DiscoverableService]:
    proc = run(["launchctl", "list"], check=False, capture=True)
    entries: List[DiscoverableService] = []
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("PID\tStatus\tLabel"):
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, status, label = parts
        entries.append(
            DiscoverableService(
                index=0,
                label=label.strip(),
                pid=pid.strip(),
                status=status.strip(),
            )
        )
    entries.sort(key=lambda item: item.label.lower())
    for index, entry in enumerate(entries, start=1):
        entry.index = index
    return entries


def render_discoverable_services_hint(
    *,
    discover_launchd_services: Callable[[], List[DiscoverableService]],
    grep: str = "",
    emit: Callable[[str], None] = print,
) -> None:
    catalog = discover_launchd_services()
    grep_text = grep.strip()
    if grep_text:
        grep_lower = grep_text.lower()
        catalog = [entry for entry in catalog if grep_lower in entry.label.lower()]
    if not catalog:
        emit("No services tracked by skuld.")
        if grep_text:
            emit(f"No launchd services matched grep '{grep_text}' in the current session.")
        else:
            emit("No visible launchd services were discovered in the current session.")
        return
    emit("No services tracked by skuld.")
    emit("")
    for entry in catalog:
        pid = "-" if entry.pid == "-" else entry.pid
        emit(f"{entry.index:>3}. {entry.label}  pid={pid} status={entry.status}")
    emit("")
    emit(
        "Use `skuld track <id ...>` or `skuld track <label ...>` to start "
        "tracking services from this catalog."
    )


def track_services(
    targets: List[str],
    *,
    alias: str,
    resolve_discoverable_targets: Callable[[List[str]], List[DiscoverableService]],
    suggest_display_name: Callable[[str], str],
    prompt_display_name: Callable[[str, str], str],
    ensure_display_name_available: Callable[[str], None],
    get_managed: Callable[[str], Optional[ManagedService]],
    launchctl_print_service_raw: Callable[[str], str],
    extract_launchctl_value: Callable[[str, str], str],
    service_factory: Callable[..., ManagedService],
    upsert_registry: Callable[[ManagedService], None],
    ok: Callable[[str], None],
) -> None:
    if not targets:
        raise RuntimeError("Use: skuld track <id ...> or skuld track <label ...>")
    if alias and len(targets) != 1:
        raise RuntimeError("--alias can only be used when tracking exactly one service.")

    resolved = resolve_discoverable_targets(targets)
    for entry in resolved:
        label = entry.label
        suggested = suggest_display_name(label)
        display_name = (alias or prompt_display_name(label, suggested)).strip()
        ensure_display_name_available(display_name)
        if get_managed(label):
            raise RuntimeError(f"'{label}' is already tracked in skuld.")
        raw = launchctl_print_service_raw(label)
        if not raw:
            raise RuntimeError(f"Could not inspect launchd service '{label}'.")
        plist_path = extract_launchctl_value(raw, "path")
        program = extract_launchctl_value(raw, "program") or label
        state = extract_launchctl_value(raw, "state")
        description = label if not state else f"{label} ({state})"
        service = service_factory(
            name=label,
            exec_cmd=program,
            description=description,
            display_name=display_name,
            launchd_label=label,
            plist_path_hint=plist_path,
            managed_by_skuld=False,
            scope="agent",
            log_dir="",
        )
        upsert_registry(service)
        ok(f"Tracked '{label}' as '{display_name}'.")
