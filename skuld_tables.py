from typing import Callable, Dict, List, Optional, Sequence, Tuple

import skuld_common as common


SERVICE_TABLE_COLUMNS = (
    {"key": "id", "header": "id", "min_width": 2, "shrink": False},
    {"key": "name", "header": "name", "min_width": 12, "shrink": True},
    {"key": "service", "header": "service", "min_width": 7, "shrink": False},
    {"key": "timer", "header": "timer", "min_width": 5, "shrink": False},
    {"key": "triggers", "header": "triggers", "min_width": 12, "shrink": True},
    {"key": "cpu", "header": "cpu", "min_width": 3, "shrink": False},
    {"key": "memory", "header": "memory", "min_width": 6, "shrink": False},
    {"key": "ports", "header": "ports", "min_width": 5, "shrink": True},
)
SERVICE_TABLE_COLUMN_KEYS = tuple(str(column["key"]) for column in SERVICE_TABLE_COLUMNS)
SERVICE_TABLE_SHRINK_ORDER = ("triggers", "name", "ports")
SERVICE_TABLE_HIDE_ORDER = ("ports", "memory", "cpu", "triggers", "timer")


def shrink_service_table_widths(
    columns: List[Dict[str, object]],
    widths: Dict[str, int],
    max_width: int,
) -> Dict[str, int]:
    return common.shrink_table_widths(columns, widths, max_width, SERVICE_TABLE_SHRINK_ORDER)


def parse_service_table_columns(value: Optional[str]) -> Optional[Tuple[str, ...]]:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.lower() in {"all", "auto", "default"}:
        return None

    selected: List[str] = []
    invalid: List[str] = []
    for item in raw.split(","):
        key = item.strip().lower()
        if not key:
            continue
        if key not in SERVICE_TABLE_COLUMN_KEYS:
            invalid.append(key)
            continue
        if key not in selected:
            selected.append(key)

    if invalid:
        allowed = ", ".join(SERVICE_TABLE_COLUMN_KEYS)
        raise ValueError(
            f"Unknown service table column(s): {', '.join(invalid)}. "
            f"Allowed columns: {allowed}."
        )
    if not selected:
        raise ValueError("At least one service table column must be selected.")
    return tuple(selected)


def resolve_service_table_columns(
    cli_value: Optional[str],
    *,
    env_value: Optional[str],
) -> Optional[Tuple[str, ...]]:
    if cli_value is not None:
        return parse_service_table_columns(cli_value)
    return parse_service_table_columns(env_value)


def select_service_table_columns(
    columns: Optional[Sequence[str]],
) -> Tuple[Tuple[Dict[str, object], ...], bool]:
    if columns is None:
        return SERVICE_TABLE_COLUMNS, True

    by_key = {str(column["key"]): column for column in SERVICE_TABLE_COLUMNS}
    return tuple(dict(by_key[key]) for key in columns), False


def fit_service_table(
    rows: List[Dict[str, object]],
    max_width: Optional[int] = None,
    columns: Optional[Sequence[str]] = None,
) -> Tuple[List[str], List[List[str]]]:
    service_columns, allow_auto_hide = select_service_table_columns(columns)
    return common.fit_table(
        rows,
        service_columns=service_columns,
        shrink_order=SERVICE_TABLE_SHRINK_ORDER,
        hide_order=SERVICE_TABLE_HIDE_ORDER if allow_auto_hide else (),
        max_width=max_width,
    )


def sort_service_rows(rows: List[Dict[str, object]], sort_by: str) -> List[Dict[str, object]]:
    return sorted(rows, key=lambda row: common.service_sort_key(sort_by, row))


def render_host_panel(
    overview: Dict[str, str],
    render_table: Callable[[List[str], List[List[str]]], None],
) -> None:
    render_table(list(overview.keys()), [list(overview.values())])
    print()
