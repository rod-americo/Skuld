import argparse
from typing import Callable, List, Optional


def ensure_display_name_available(
    display_name: str,
    *,
    current_id: Optional[int],
    validate_name: Callable[[str], None],
    load_registry: Callable[[], List[object]],
) -> None:
    validate_name(display_name)
    for service in load_registry():
        if service.display_name != display_name:
            continue
        if current_id is not None and service.id == current_id:
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
    get_managed_by_display_name: Callable[[str], Optional[object]],
    get_managed_by_id: Callable[[int], Optional[object]],
    normalize_target_token: Callable[[str], tuple[Optional[str], str]],
    get_managed: Callable[[str, Optional[str]], Optional[object]],
    find_managed_by_name: Callable[[str], List[object]],
    format_scoped_name: Callable[[str, str], str],
    managed_sort_key: Callable[[object], object],
) -> Optional[object]:
    raw_token = (token or "").strip()
    service = get_managed_by_display_name(raw_token)
    if service:
        return service
    if raw_token.isdigit():
        return get_managed_by_id(int(raw_token))
    scope, name = normalize_target_token(raw_token)
    if scope is not None:
        return get_managed(name, scope)
    matches = find_managed_by_name(name)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        choices = ", ".join(
            format_scoped_name(item.name, item.scope)
            for item in sorted(matches, key=managed_sort_key)
        )
        raise RuntimeError(
            f"Managed service '{name}' is ambiguous across scopes. "
            f"Use an id, display name, or one of: {choices}."
        )
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
    positional_tokens = getattr(args, "targets", None) or []
    name_flag = getattr(args, "name_flag", None)
    id_flag = getattr(args, "id_flag", None)

    tokens: List[str] = list(positional_tokens)
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
