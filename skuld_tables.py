from typing import Callable, Dict, List, Optional, Tuple

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
SERVICE_TABLE_SHRINK_ORDER = ("triggers", "name", "ports")
SERVICE_TABLE_HIDE_ORDER = ("ports", "memory", "cpu", "triggers", "timer")


def shrink_service_table_widths(
    columns: List[Dict[str, object]],
    widths: Dict[str, int],
    max_width: int,
) -> Dict[str, int]:
    return common.shrink_table_widths(columns, widths, max_width, SERVICE_TABLE_SHRINK_ORDER)


def fit_service_table(
    rows: List[Dict[str, object]],
    max_width: Optional[int] = None,
) -> Tuple[List[str], List[List[str]]]:
    return common.fit_table(
        rows,
        service_columns=SERVICE_TABLE_COLUMNS,
        shrink_order=SERVICE_TABLE_SHRINK_ORDER,
        hide_order=SERVICE_TABLE_HIDE_ORDER,
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
