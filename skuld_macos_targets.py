import argparse
from typing import Callable, List, Optional


def ensure_display_name_available(
    display_name: str,
    *,
    current_name: Optional[str],
    validate_name: Callable[[str], None],
    load_registry: Callable[[], List[object]],
) -> None:
    validate_name(display_name)
    for service in load_registry():
        if service.display_name != display_name:
            continue
        if current_name is not None and service.name == current_name:
            return
        raise RuntimeError(f"Display name '{display_name}' is already in use.")


def resolve_name_arg(args: argparse.Namespace, required: bool = True) -> Optional[str]:
    positional = getattr(args, "name", None)
    flag_value = getattr(args, "name_flag", None)
    if positional and flag_value and positional != flag_value:
        raise RuntimeError(
            f"Conflicting names provided: positional='{positional}' "
            f"and --name='{flag_value}'."
        )
    name = flag_value or positional
    if required and not name:
        raise RuntimeError("Service name is required. Use NAME or --name NAME.")
    return name


def resolve_managed_from_token(
    token: str,
    *,
    get_managed: Callable[[str], Optional[object]],
    get_managed_by_display_name: Callable[[str], Optional[object]],
    get_managed_by_id: Callable[[int], Optional[object]],
) -> Optional[object]:
    service = get_managed(token)
    if service:
        return service
    service = get_managed_by_display_name(token)
    if service:
        return service
    if token.isdigit():
        return get_managed_by_id(int(token))
    return None


def resolve_managed_arg(
    args: argparse.Namespace,
    *,
    required: bool = True,
    resolve_managed_from_token: Callable[[str], Optional[object]],
    get_managed_by_id: Callable[[int], Optional[object]],
) -> Optional[object]:
    positional = getattr(args, "name", None)
    name_flag = getattr(args, "name_flag", None)
    id_flag = getattr(args, "id_flag", None)
    if positional and name_flag and positional != name_flag:
        raise RuntimeError(
            f"Conflicting targets provided: positional='{positional}' "
            f"and --name='{name_flag}'."
        )
    token = name_flag or positional
    by_token = None
    if token:
        by_token = resolve_managed_from_token(token)
        if not by_token:
            raise RuntimeError(f"Managed service '{token}' not found (name or id).")
    by_id = None
    if id_flag is not None:
        by_id = get_managed_by_id(id_flag)
        if not by_id:
            raise RuntimeError(f"Managed service id '{id_flag}' not found.")
    if by_token and by_id and by_token.id != by_id.id:
        raise RuntimeError(
            f"Conflicting targets provided: '{token}' resolves to id={by_token.id}, "
            f"but --id={id_flag}."
        )
    service = by_id or by_token
    if required and not service:
        raise RuntimeError(
            "Service target is required. Use NAME/ID, --name NAME, or --id ID."
        )
    return service


def resolve_managed_many_arg(
    args: argparse.Namespace,
    *,
    resolve_managed_from_token: Callable[[str], Optional[object]],
) -> List[object]:
    tokens = list(getattr(args, "targets", None) or [])
    name_flag = getattr(args, "name_flag", None)
    id_flag = getattr(args, "id_flag", None)
    if name_flag:
        tokens.append(name_flag)
    if id_flag is not None:
        tokens.append(str(id_flag))
    if not tokens:
        raise RuntimeError(
            "At least one service target is required. "
            "Use NAME/ID, --name NAME, or --id ID."
        )
    resolved: List[object] = []
    seen_ids = set()
    for token in tokens:
        service = resolve_managed_from_token(token)
        if not service:
            raise RuntimeError(f"Managed service '{token}' not found (name or id).")
        if service.id in seen_ids:
            continue
        seen_ids.add(service.id)
        resolved.append(service)
    return resolved


def resolve_discoverable_targets(
    tokens: List[str],
    *,
    discover_launchd_services: Callable[[], List[object]],
) -> List[object]:
    catalog = discover_launchd_services()
    by_index = {entry.index: entry for entry in catalog}
    by_label = {entry.label: entry for entry in catalog}
    resolved: List[object] = []
    seen_labels = set()
    for token in tokens:
        entry = by_index.get(int(token)) if token.isdigit() else by_label.get(token)
        if not entry:
            raise RuntimeError(
                f"Launchd service '{token}' not found in the current catalog."
            )
        if entry.label in seen_labels:
            continue
        seen_labels.add(entry.label)
        resolved.append(entry)
    return resolved
