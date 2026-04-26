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
SERVICE_TABLE_COLUMN_DESCRIPTIONS = {
    "id": "registry id",
    "name": "display name",
    "service": "service state",
    "timer": "timer state",
    "triggers": "schedule summary",
    "cpu": "CPU usage",
    "memory": "memory usage",
    "ports": "listening ports",
}
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
    return parse_service_table_column_tokens([raw])


def parse_service_table_column_tokens(values: Sequence[str]) -> Optional[Tuple[str, ...]]:
    tokens: List[str] = []
    for value in values:
        for item in str(value).split(","):
            token = item.strip().lower()
            if token:
                tokens.append(token)
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in {"all", "auto", "default"}:
        return None

    selected: List[str] = []
    invalid: List[str] = []
    invalid_ids: List[str] = []
    for token in tokens:
        if token in {"all", "auto", "default"}:
            invalid.append(token)
            continue
        if token.isdigit():
            index = int(token)
            if index < 1 or index > len(SERVICE_TABLE_COLUMN_KEYS):
                invalid_ids.append(token)
                continue
            key = SERVICE_TABLE_COLUMN_KEYS[index - 1]
        elif token in SERVICE_TABLE_COLUMN_KEYS:
            key = token
        else:
            invalid.append(token)
            continue
        if key not in selected:
            selected.append(key)

    if invalid_ids:
        raise ValueError(
            f"Service table column id(s) not found: {', '.join(invalid_ids)}. "
            f"Use ids 1-{len(SERVICE_TABLE_COLUMN_KEYS)}."
        )
    if invalid:
        allowed = ", ".join(SERVICE_TABLE_COLUMN_KEYS)
        raise ValueError(
            f"Unknown service table column(s): {', '.join(invalid)}. "
            f"Allowed columns: ids 1-{len(SERVICE_TABLE_COLUMN_KEYS)} or {allowed}."
        )
    if not selected:
        raise ValueError("At least one service table column must be selected.")
    return tuple(selected)


def resolve_service_table_columns(
    cli_value: Optional[str],
    *,
    config_value: Optional[str] = None,
    env_value: Optional[str],
) -> Optional[Tuple[str, ...]]:
    if cli_value is not None:
        return parse_service_table_columns(cli_value)
    if config_value is not None:
        return parse_service_table_columns(config_value)
    return parse_service_table_columns(env_value)


def select_service_table_columns(
    columns: Optional[Sequence[str]],
) -> Tuple[Tuple[Dict[str, object], ...], bool]:
    if columns is None:
        return SERVICE_TABLE_COLUMNS, True

    by_key = {str(column["key"]): column for column in SERVICE_TABLE_COLUMNS}
    return tuple(dict(by_key[key]) for key in columns), False


def service_table_column_catalog_lines(
    columns: Optional[Sequence[str]],
) -> List[str]:
    current = ",".join(columns) if columns else "default"
    selected = set(columns or ())
    lines = [f"Current saved columns: {current}", "", "Available table columns:"]
    for index, key in enumerate(SERVICE_TABLE_COLUMN_KEYS, start=1):
        marker = "*" if key in selected else " "
        description = SERVICE_TABLE_COLUMN_DESCRIPTIONS.get(key, "")
        lines.append(f"{index:>3}. {marker} {key:<8} {description}".rstrip())
    lines.extend(
        [
            "",
            "Use: skuld config columns <id ...>, skuld config columns <name ...>,",
            "or skuld config columns default",
        ]
    )
    return lines


def fit_service_table(
    rows: List[Dict[str, object]],
    max_width: Optional[int] = None,
    columns: Optional[Sequence[str]] = None,
) -> Tuple[List[str], List[List[str]]]:
    service_columns, allow_auto_hide = select_service_table_columns(columns)
    rows = format_service_table_ids(rows)
    return common.fit_table(
        rows,
        service_columns=service_columns,
        shrink_order=SERVICE_TABLE_SHRINK_ORDER,
        hide_order=SERVICE_TABLE_HIDE_ORDER if allow_auto_hide else (),
        max_width=max_width,
    )


def sort_service_rows(rows: List[Dict[str, object]], sort_by: str) -> List[Dict[str, object]]:
    return sorted(rows, key=lambda row: common.service_sort_key(sort_by, row))


def format_service_table_ids(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not rows:
        return rows
    width = max(len(str(row.get("id", ""))) for row in rows)
    width = max(width, 1)
    result: List[Dict[str, object]] = []
    for row in rows:
        item = dict(row)
        raw_id = str(item.get("id", ""))
        item["id"] = raw_id.zfill(width) if raw_id.isdigit() else raw_id
        result.append(item)
    return result


def render_host_panel(
    overview: Dict[str, str],
    render_table: Callable[[List[str], List[List[str]]], None],
) -> None:
    render_table(list(overview.keys()), [list(overview.values())])
    print()
