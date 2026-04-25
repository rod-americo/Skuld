from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import skuld_observability as observability


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def load_dotenv(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    env: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def find_sudo_password(
    *,
    use_env_sudo: bool,
    env_file_override: Optional[str],
    default_env_file: Path,
    script_dir: Path,
    state_home: Path,
) -> Optional[str]:
    if not use_env_sudo:
        return None

    from_env = os.environ.get("SKULD_SUDO_PASSWORD")
    if from_env:
        return from_env

    candidate_files: List[Path] = []
    if env_file_override:
        candidate_files.append(Path(env_file_override))
    candidate_files.extend(
        [
            Path.cwd() / default_env_file,
            script_dir / default_env_file,
            state_home / ".env",
        ]
    )

    for env_path in candidate_files:
        if not env_path.exists():
            continue
        value = load_dotenv(env_path).get("SKULD_SUDO_PASSWORD")
        if value:
            return value
    return None


def parse_bool(value: str, default: bool = True) -> bool:
    raw = (value or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def parse_int(value: str) -> int:
    try:
        num = int((value or "").strip())
    except ValueError:
        return 0
    return num if num > 0 else 0


def run_command(
    cmd: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
    input_text: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    observability.debug("run_command", capture=capture, check=check, cmd=" ".join(shlex.quote(item) for item in cmd))
    kwargs: Dict[str, Any] = {"text": True}
    if capture:
        kwargs["capture_output"] = True
    if input_text is not None:
        kwargs["input"] = input_text
    if env is not None:
        kwargs["env"] = env
    proc = subprocess.run(list(cmd), **kwargs)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(shlex.quote(c) for c in cmd)}")
    return proc


def run_sudo_command(
    cmd: Sequence[str],
    *,
    sudo_password: Optional[str],
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    observability.debug("run_sudo", capture=capture, check=check, password_set=bool(sudo_password), cmd=" ".join(shlex.quote(item) for item in cmd))
    full = ["sudo"] + list(cmd)
    if sudo_password:
        full = ["sudo", "-S", "-k", "-p", ""] + list(cmd)
        return run_command(full, check=check, capture=capture, input_text=sudo_password + "\n")
    return run_command(full, check=check, capture=capture)


def is_tty() -> bool:
    return sys.stdout.isatty()


def supports_unicode_output(*, force_ascii: bool, force_unicode: bool) -> bool:
    if force_ascii:
        return False
    if force_unicode:
        return True
    if not is_tty():
        return False
    term = (os.environ.get("TERM") or "").strip().lower()
    if term == "dumb":
        return False
    encoding = (sys.stdout.encoding or "").upper()
    if "UTF-8" in encoding or "UTF8" in encoding:
        return True
    locale_text = " ".join(
        [
            os.environ.get("LC_ALL", ""),
            os.environ.get("LC_CTYPE", ""),
            os.environ.get("LANG", ""),
        ]
    ).upper()
    return "UTF-8" in locale_text or "UTF8" in locale_text


def colorize(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    palette = {
        "green": "\033[32m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "cyan": "\033[36m",
        "gray": "\033[90m",
        "reset": "\033[0m",
    }
    return f"{palette.get(color, '')}{text}{palette['reset']}"


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def clip_text(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def parse_first_float(text: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", ANSI_RE.sub("", text or ""))
    if not match:
        return -1.0
    try:
        return float(match.group(0))
    except ValueError:
        return -1.0


def service_sort_key(sort_by: str, row: Dict[str, object]) -> Tuple[object, ...]:
    if sort_by == "name":
        return (str(row["name"]).lower(), int(row["id"]))
    if sort_by == "cpu":
        return (-parse_first_float(str(row["cpu"])), str(row["name"]).lower(), int(row["id"]))
    if sort_by == "memory":
        return (-parse_first_float(str(row["memory"])), str(row["name"]).lower(), int(row["id"]))
    return (int(row["id"]),)


def resolve_sort_arg(args: Optional[object], choices: Sequence[str]) -> str:
    sort_by = getattr(args, "sort", "name") if args is not None else "name"
    return sort_by if sort_by in choices else "name"


def format_bytes(value: str) -> str:
    raw = (value or "").strip()
    if not raw or raw in ("[not set]", "n/a"):
        return "-"
    try:
        num = int(raw)
    except ValueError:
        return "-"
    if num < 0:
        return "-"
    size_gb = num / (1024.0**3)
    return f"{size_gb:.2f}GB"


def format_duration_human(seconds: int) -> str:
    if seconds < 0:
        return "-"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def render_table(headers: List[str], rows: List[List[str]], *, unicode_box: bool) -> None:
    if not rows:
        return
    widths = [visible_len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], visible_len(cell))

    if unicode_box:
        box = {
            "top_left": "╭",
            "top_mid": "┬",
            "top_right": "╮",
            "mid_left": "├",
            "mid_mid": "┼",
            "mid_right": "┤",
            "bottom_left": "╰",
            "bottom_mid": "┴",
            "bottom_right": "╯",
            "vertical": "│",
            "fill": "─",
        }
    else:
        box = {
            "top_left": "+",
            "top_mid": "+",
            "top_right": "+",
            "mid_left": "+",
            "mid_mid": "+",
            "mid_right": "+",
            "bottom_left": "+",
            "bottom_mid": "+",
            "bottom_right": "+",
            "vertical": "|",
            "fill": "-",
        }

    def hline(left: str, middle: str, right: str) -> str:
        return left + middle.join(box["fill"] * (width + 2) for width in widths) + right

    def format_row(cells: List[str]) -> str:
        padded = []
        for index, cell in enumerate(cells):
            pad = widths[index] - visible_len(cell)
            padded.append(f" {cell}{' ' * max(0, pad)} ")
        return box["vertical"] + box["vertical"].join(padded) + box["vertical"]

    print(hline(box["top_left"], box["top_mid"], box["top_right"]))
    print(format_row(headers))
    print(hline(box["mid_left"], box["mid_mid"], box["mid_right"]))
    for row in rows:
        print(format_row(row))
    print(hline(box["bottom_left"], box["bottom_mid"], box["bottom_right"]))


def current_terminal_columns() -> Optional[int]:
    if not is_tty():
        return None
    try:
        columns = shutil.get_terminal_size().columns
    except OSError:
        return None
    return columns if columns > 0 else None


def table_widths(headers: List[str], rows: List[List[str]]) -> List[int]:
    widths = [visible_len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], visible_len(cell))
    return widths


def table_render_width(widths: List[int]) -> int:
    if not widths:
        return 0
    return sum(widths) + (3 * len(widths)) + 1


def clip_plain_text(text: str, width: int) -> str:
    if visible_len(text) <= width:
        return text
    return clip_text(text, width)


def shrink_table_widths(
    columns: List[Dict[str, object]],
    widths: Dict[str, int],
    max_width: int,
    shrink_order: Sequence[str],
) -> Dict[str, int]:
    adjusted = dict(widths)
    while True:
        total_width = table_render_width([adjusted[str(column["key"])] for column in columns])
        if total_width <= max_width:
            return adjusted
        changed = False
        for key in shrink_order:
            column = next((item for item in columns if item["key"] == key), None)
            if not column:
                continue
            min_width = max(int(column["min_width"]), visible_len(str(column["header"])))
            current_width = adjusted[key]
            if current_width <= min_width:
                continue
            adjusted[key] = current_width - 1
            changed = True
            break
        if not changed:
            return adjusted


def fit_table(
    rows: List[Dict[str, object]],
    *,
    service_columns: Sequence[Dict[str, object]],
    shrink_order: Sequence[str],
    hide_order: Sequence[str],
    max_width: Optional[int] = None,
) -> Tuple[List[str], List[List[str]]]:
    columns = [dict(item) for item in service_columns]
    if max_width is None:
        max_width = current_terminal_columns()

    while True:
        headers = [str(column["header"]) for column in columns]
        raw_rows = [[str(row[str(column["key"])]) for column in columns] for row in rows]
        if not raw_rows or max_width is None:
            return headers, raw_rows

        current_widths = table_widths(headers, raw_rows)
        width_map = {str(column["key"]): current_widths[index] for index, column in enumerate(columns)}
        width_map = shrink_table_widths(columns, width_map, max_width, shrink_order)
        fitted_rows = []
        for row in rows:
            fitted_row: List[str] = []
            for column in columns:
                key = str(column["key"])
                value = str(row[key])
                target_width = width_map[key]
                if column.get("shrink"):
                    value = clip_plain_text(value, target_width)
                fitted_row.append(value)
            fitted_rows.append(fitted_row)

        fitted_widths = table_widths(headers, fitted_rows)
        if table_render_width(fitted_widths) <= max_width:
            return headers, fitted_rows

        drop_key = next((key for key in hide_order if any(column["key"] == key for column in columns)), None)
        if drop_key is None:
            return headers, fitted_rows
        columns = [column for column in columns if column["key"] != drop_key]
