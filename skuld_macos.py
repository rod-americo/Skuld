#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import plistlib
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import skuld_common as common
import skuld_cli
import skuld_macos_launchd as launchd
from skuld_registry import RegistryStore

VERSION = "0.3.0"
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._@-]*$")
DEFAULT_ENV_FILE = Path(".env")
SKULD_HOME = Path(os.environ.get("SKULD_HOME", Path.home() / "Library/Application Support/skuld"))
REGISTRY_FILE = SKULD_HOME / "services.json"
RUNTIME_STATS_FILE = SKULD_HOME / "runtime_stats.json"
USE_ENV_SUDO = True
FORCE_TABLE_ASCII = False
FORCE_TABLE_UNICODE = False
SORT_CHOICES = ("id", "name", "cpu", "memory")
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
WEEKDAY_MAP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


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


def ensure_storage() -> None:
    SKULD_HOME.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("[]", encoding="utf-8")
    if not RUNTIME_STATS_FILE.exists():
        RUNTIME_STATS_FILE.write_text('{"services": {}}\n', encoding="utf-8")


def load_dotenv(path: Path) -> Dict[str, str]:
    return common.load_dotenv(path)


def get_sudo_password() -> Optional[str]:
    return common.find_sudo_password(
        use_env_sudo=USE_ENV_SUDO,
        env_file_override=os.environ.get("SKULD_ENV_FILE"),
        default_env_file=DEFAULT_ENV_FILE,
        script_dir=Path(__file__).resolve().parent,
        state_home=SKULD_HOME,
    )


def parse_bool(value: str, default: bool = True) -> bool:
    return common.parse_bool(value, default=default)


def parse_int(value: str) -> int:
    return common.parse_int(value)


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError("Invalid name. Use [a-zA-Z0-9._@-] and start with a letter/number.")


def ensure_display_name_available(display_name: str, current_name: Optional[str] = None) -> None:
    validate_name(display_name)
    for svc in load_registry():
        if svc.display_name != display_name:
            continue
        if current_name is not None and svc.name == current_name:
            return
        raise RuntimeError(f"Display name '{display_name}' is already in use.")


def suggest_display_name(label: str) -> str:
    raw = (label or "").strip()
    tokens = [part for part in raw.split(".") if part]
    if tokens and tokens[0] == "application":
        tokens = tokens[1:]
    while tokens and tokens[-1].isdigit():
        tokens.pop()
    if len(tokens) >= 2 and tokens[-1].lower() in {"mac", "desktop", "agent", "daemon", "helper"}:
        suggestion = "-".join(tokens[-2:])
    elif tokens:
        suggestion = tokens[-1]
    else:
        suggestion = raw
    suggestion = suggestion.replace(" ", "-")
    validate_name(suggestion)
    return suggestion


def prompt_display_name(target: str, suggested: str) -> str:
    if not sys.stdin.isatty():
        return suggested
    value = input(f"Display name for {target} [{suggested}]: ").strip()
    chosen = value or suggested
    validate_name(chosen)
    return chosen


def resolve_scope(value: str) -> str:
    scope = (value or "agent").strip().lower()
    if scope not in {"daemon", "agent"}:
        raise RuntimeError("Invalid scope. Use 'daemon' or 'agent'.")
    return scope


def resolve_name_arg(args: argparse.Namespace, required: bool = True) -> Optional[str]:
    positional = getattr(args, "name", None)
    flag_value = getattr(args, "name_flag", None)
    if positional and flag_value and positional != flag_value:
        raise RuntimeError(f"Conflicting names provided: positional='{positional}' and --name='{flag_value}'.")
    name = flag_value or positional
    if required and not name:
        raise RuntimeError("Service name is required. Use NAME or --name NAME.")
    return name


def is_tty() -> bool:
    return common.is_tty()


def supports_unicode_output() -> bool:
    return common.supports_unicode_output(
        force_ascii=FORCE_TABLE_ASCII,
        force_unicode=FORCE_TABLE_UNICODE,
    )


def colorize(text: str, color: str) -> str:
    return common.colorize(text, color, enabled=is_tty())


def visible_len(text: str) -> int:
    return common.visible_len(text)


def clip_text(text: str, width: int) -> str:
    return common.clip_text(text, width)


def parse_first_float(text: str) -> float:
    return common.parse_first_float(text)


def service_sort_key(sort_by: str, row: Dict[str, object]) -> Tuple[object, ...]:
    return common.service_sort_key(sort_by, row)


def resolve_sort_arg(args: Optional[argparse.Namespace]) -> str:
    return common.resolve_sort_arg(args, SORT_CHOICES)


def info(msg: str) -> None:
    print(f"[skuld] {msg}")


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


def err(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)


def run(cmd: List[str], check: bool = True, capture: bool = False, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return common.run_command(
        cmd,
        check=check,
        capture=capture,
        input_text=input_text,
    )


def run_sudo(cmd: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return common.run_sudo_command(
        cmd,
        sudo_password=get_sudo_password(),
        check=check,
        capture=capture,
    )


def warn_env_sudo_usage() -> None:
    if get_sudo_password():
        info("Warning: using SKULD_SUDO_PASSWORD from env/.env. Keep this for short-lived local use only.")


def sudo_check(_args: argparse.Namespace) -> None:
    warn_env_sudo_usage()
    password = get_sudo_password()
    if password:
        proc = run(["sudo", "-S", "-k", "-p", "", "true"], check=False, capture=True, input_text=password + "\n")
    else:
        proc = run(["sudo", "-n", "true"], check=False, capture=True)
    if proc.returncode == 0:
        ok("sudo is available.")
        return
    details = (proc.stderr or proc.stdout or "").strip()
    raise RuntimeError(f"sudo is not available non-interactively. {details}".strip())


def sudo_run_command(args: argparse.Namespace) -> None:
    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise RuntimeError("Use: skuld sudo run -- <command> [args...]")
    warn_env_sudo_usage()
    proc = run_sudo(command, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"sudo command failed with exit code {proc.returncode}.")


def format_bytes_from_kib(kib: int) -> str:
    return format_bytes(str(kib * 1024))


def format_bytes(value: str) -> str:
    return common.format_bytes(value)


def format_duration_human(seconds: int) -> str:
    return common.format_duration_human(seconds)


def render_table(headers: List[str], rows: List[List[str]]) -> None:
    common.render_table(headers, rows, unicode_box=supports_unicode_output())


def current_terminal_columns() -> Optional[int]:
    return common.current_terminal_columns()


def table_widths(headers: List[str], rows: List[List[str]]) -> List[int]:
    return common.table_widths(headers, rows)


def table_render_width(widths: List[int]) -> int:
    return common.table_render_width(widths)


def clip_plain_text(text: str, width: int) -> str:
    return common.clip_plain_text(text, width)


def shrink_service_table_widths(columns: List[Dict[str, object]], widths: Dict[str, int], max_width: int) -> Dict[str, int]:
    return common.shrink_table_widths(columns, widths, max_width, SERVICE_TABLE_SHRINK_ORDER)


def fit_service_table(rows: List[Dict[str, object]], max_width: Optional[int] = None) -> Tuple[List[str], List[List[str]]]:
    return common.fit_table(
        rows,
        service_columns=SERVICE_TABLE_COLUMNS,
        shrink_order=SERVICE_TABLE_SHRINK_ORDER,
        hide_order=SERVICE_TABLE_HIDE_ORDER,
        max_width=max_width,
    )


def current_user_home() -> Path:
    return Path.home()


def service_label(name: str) -> str:
    return f"io.skuld.{name}"


def launchd_label_for_service(service: ManagedService) -> str:
    return service.launchd_label or service_label(service.name)


def plist_path_for_service(service: ManagedService) -> Path:
    if service.plist_path_hint:
        return Path(service.plist_path_hint)
    if service.scope == "agent":
        return current_user_home() / "Library/LaunchAgents" / f"{service_label(service.name)}.plist"
    return Path("/Library/LaunchDaemons") / f"{service_label(service.name)}.plist"


def jobs_root_for_scope(scope: str) -> Path:
    if scope == "agent":
        return SKULD_HOME / "jobs"
    return Path("/Library/Application Support/skuld/jobs")


def logs_root_for_scope(scope: str) -> Path:
    if scope == "agent":
        return SKULD_HOME / "logs"
    return Path("/Library/Application Support/skuld/logs")


def events_root_for_scope(scope: str) -> Path:
    if scope == "agent":
        return SKULD_HOME / "events"
    return Path("/Library/Application Support/skuld/events")


def log_dir_for_service(name: str, scope: str) -> Path:
    return logs_root_for_scope(scope) / name


def event_file_for_service(name: str, scope: str) -> Path:
    return events_root_for_scope(scope) / f"{name}.jsonl"


def wrapper_script_for_service(name: str, scope: str) -> Path:
    return jobs_root_for_scope(scope) / f"{name}.sh"


def normalize_service(item: Dict[str, object]) -> ManagedService:
    scope = resolve_scope(str(item.get("scope", "daemon")))
    name = str(item.get("name", "")).strip()
    managed_by_skuld = parse_bool(str(item.get("managed_by_skuld", True)))
    log_dir_default = str(log_dir_for_service(name, scope)) if managed_by_skuld else ""
    log_dir = str(item.get("log_dir", "")).strip() or log_dir_default
    return ManagedService(
        name=name,
        exec_cmd=str(item.get("exec_cmd", "")).strip(),
        description=str(item.get("description", "")).strip(),
        display_name=str(item.get("display_name", name)).strip() or name,
        launchd_label=str(item.get("launchd_label", service_label(name))).strip() or service_label(name),
        plist_path_hint=str(item.get("plist_path_hint", "")).strip(),
        managed_by_skuld=managed_by_skuld,
        schedule=str(item.get("schedule", "")).strip(),
        working_dir=str(item.get("working_dir", "")).strip(),
        user=str(item.get("user", "")).strip(),
        restart=str(item.get("restart", "on-failure")).strip() or "on-failure",
        timer_persistent=parse_bool(str(item.get("timer_persistent", True))),
        id=parse_int(str(item.get("id", 0))),
        backend="launchd",
        scope=scope,
        log_dir=log_dir,
    )


def validate_registry_service(service: ManagedService, index: int) -> None:
    validate_name(service.name)
    validate_name(service.display_name)
    if service.scope == "agent" and service.user:
        raise RuntimeError(f"Invalid registry entry #{index}: 'user' is only valid for daemon scope.")


def managed_sort_key(service: ManagedService) -> tuple:
    return (service.name.lower(), service.id)


def registry_store() -> RegistryStore[ManagedService]:
    return RegistryStore(
        home=SKULD_HOME,
        registry_file=REGISTRY_FILE,
        normalize_item=normalize_service,
        validate_service=validate_registry_service,
        sort_key=managed_sort_key,
        service_key=lambda service: service.name,
        required_fields=("name", "exec_cmd", "description"),
    )


def load_registry(*, write_back: bool = False) -> List[ManagedService]:
    ensure_storage()
    return registry_store().load(write_back=write_back)


def save_registry(services: List[ManagedService]) -> None:
    ensure_storage()
    registry_store().save(services)


def upsert_registry(service: ManagedService) -> None:
    ensure_storage()
    registry_store().upsert(service)


def remove_registry(name: str) -> None:
    ensure_storage()
    registry_store().remove(name)


def get_managed(name: str) -> Optional[ManagedService]:
    for svc in load_registry():
        if svc.name == name:
            return svc
    return None


def get_managed_by_display_name(display_name: str) -> Optional[ManagedService]:
    for svc in load_registry():
        if svc.display_name == display_name:
            return svc
    return None


def get_managed_by_id(service_id: int) -> Optional[ManagedService]:
    for svc in load_registry():
        if svc.id == service_id:
            return svc
    return None


def resolve_managed_from_token(token: str) -> Optional[ManagedService]:
    svc = get_managed(token)
    if svc:
        return svc
    svc = get_managed_by_display_name(token)
    if svc:
        return svc
    if token.isdigit():
        return get_managed_by_id(int(token))
    return None


def resolve_managed_arg(args: argparse.Namespace, required: bool = True) -> Optional[ManagedService]:
    positional = getattr(args, "name", None)
    name_flag = getattr(args, "name_flag", None)
    id_flag = getattr(args, "id_flag", None)
    if positional and name_flag and positional != name_flag:
        raise RuntimeError(
            f"Conflicting targets provided: positional='{positional}' and --name='{name_flag}'."
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
            f"Conflicting targets provided: '{token}' resolves to id={by_token.id}, but --id={id_flag}."
        )
    svc = by_id or by_token
    if required and not svc:
        raise RuntimeError("Service target is required. Use NAME/ID, --name NAME, or --id ID.")
    return svc


def resolve_managed_many_arg(args: argparse.Namespace) -> List[ManagedService]:
    tokens = list(getattr(args, "targets", None) or [])
    name_flag = getattr(args, "name_flag", None)
    id_flag = getattr(args, "id_flag", None)
    if name_flag:
        tokens.append(name_flag)
    if id_flag is not None:
        tokens.append(str(id_flag))
    if not tokens:
        raise RuntimeError("At least one service target is required. Use NAME/ID, --name NAME, or --id ID.")
    resolved: List[ManagedService] = []
    seen_ids = set()
    for token in tokens:
        svc = resolve_managed_from_token(token)
        if not svc:
            raise RuntimeError(f"Managed service '{token}' not found (name or id).")
        if svc.id in seen_ids:
            continue
        seen_ids.add(svc.id)
        resolved.append(svc)
    return resolved


def resolve_lines_arg(args: argparse.Namespace, default: int = 100) -> int:
    lines_flag = getattr(args, "lines", None)
    lines_pos = getattr(args, "lines_pos", None)
    if lines_flag is not None:
        return lines_flag
    if lines_pos is not None:
        return lines_pos
    return default


def discover_launchd_services() -> List[DiscoverableService]:
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
        entries.append(DiscoverableService(index=0, label=label.strip(), pid=pid.strip(), status=status.strip()))
    entries.sort(key=lambda item: item.label.lower())
    for idx, entry in enumerate(entries, start=1):
        entry.index = idx
    return entries


def resolve_discoverable_targets(tokens: List[str]) -> List[DiscoverableService]:
    catalog = discover_launchd_services()
    by_index = {entry.index: entry for entry in catalog}
    by_label = {entry.label: entry for entry in catalog}
    resolved: List[DiscoverableService] = []
    seen_labels = set()
    for token in tokens:
        entry = None
        if token.isdigit():
            entry = by_index.get(int(token))
        else:
            entry = by_label.get(token)
        if not entry:
            raise RuntimeError(f"Launchd service '{token}' not found in the current catalog.")
        if entry.label in seen_labels:
            continue
        seen_labels.add(entry.label)
        resolved.append(entry)
    return resolved


def launchctl_print_service_raw(label: str) -> str:
    return launchd.print_service_raw(label)


def extract_launchctl_value(text: str, key: str) -> str:
    return launchd.extract_value(text, key)


def render_discoverable_services_hint() -> None:
    catalog = discover_launchd_services()
    if not catalog:
        print("No services tracked by skuld.")
        print("No visible launchd services were discovered in the current session.")
        return
    print("No services tracked by skuld.")
    print()
    for entry in catalog[:60]:
        pid = "-" if entry.pid == "-" else entry.pid
        print(f"{entry.index:>3}. {entry.label}  pid={pid} status={entry.status}")
    print()
    print("Use `skuld track <id ...>` or `skuld track <label ...>` to start tracking services from this catalog.")


def launchctl_cmd(scope: str, args: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return launchd.run_launchctl(
        scope,
        args,
        sudo_password=get_sudo_password(),
        check=check,
        capture=capture,
    )


def domain_target(scope: str) -> str:
    return launchd.domain_target(scope)


def service_target(service: ManagedService) -> str:
    return launchd.service_target(service.scope, launchd_label_for_service(service))


def service_loaded(service: ManagedService) -> bool:
    return launchd.service_loaded(
        service.scope,
        launchd_label_for_service(service),
        sudo_password=get_sudo_password(),
    )


def parse_launchctl_kv(text: str) -> Dict[str, str]:
    return launchd.parse_kv(text)


def launchctl_service_info(service: ManagedService) -> Dict[str, str]:
    return launchd.service_info(
        service.scope,
        launchd_label_for_service(service),
        sudo_password=get_sudo_password(),
    )


def read_pid(service: ManagedService) -> int:
    return parse_int(launchctl_service_info(service).get("PID", "0"))


def read_process_tree_pids(root_pid: int) -> List[int]:
    if root_pid <= 0:
        return []
    proc = run(["ps", "-axo", "pid=,ppid="], check=False, capture=True)
    children_by_parent: Dict[int, Set[int]] = {}
    for raw in (proc.stdout or "").splitlines():
        parts = raw.split()
        if len(parts) != 2:
            continue
        pid = parse_int(parts[0])
        ppid = parse_int(parts[1])
        if pid <= 0 or ppid <= 0:
            continue
        children_by_parent.setdefault(ppid, set()).add(pid)
    seen: Set[int] = set()
    queue = [root_pid]
    while queue:
        current = queue.pop(0)
        if current in seen or current <= 0:
            continue
        seen.add(current)
        queue.extend(sorted(children_by_parent.get(current, set())))
    return sorted(seen)


def terminate_process_tree(root_pid: int, grace_seconds: float = 2.0) -> None:
    pids = read_process_tree_pids(root_pid)
    if not pids:
        return

    ordered = sorted(pids, reverse=True)

    for pid in ordered:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue

    deadline = time.time() + max(0.1, grace_seconds)
    while time.time() < deadline:
        alive = []
        for pid in ordered:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except ProcessLookupError:
                continue
            except PermissionError:
                alive.append(pid)
        if not alive:
            return
        time.sleep(0.1)

    for pid in ordered:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue


def restart_policy_allows_restart(value: str) -> bool:
    policy = (value or "on-failure").strip().lower()
    return policy not in {"no", "never"}


def parse_schedule(schedule: str) -> Tuple[Optional[str], object]:
    value = (schedule or "").strip()
    if not value:
        return None, None
    match = re.match(r"^\*-\*-\* \*:00/(\d{1,2}):00$", value)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0 or minutes > 59:
            raise RuntimeError("Unsupported --schedule interval. Use minutes between 1 and 59.")
        return "StartInterval", minutes * 60
    match = re.match(r"^\*-\*-\* \*:(\d{2}):(\d{2})$", value)
    if match:
        minute = int(match.group(1))
        second = int(match.group(2))
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Minute": minute}
    match = re.match(r"^\*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        hour, minute, second = map(int, match.groups())
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Hour": hour, "Minute": minute}
    match = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        weekday, hour, minute, second = match.groups()
        if int(second) != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Weekday": WEEKDAY_MAP[weekday.lower()], "Hour": int(hour), "Minute": int(minute)}
    match = re.match(r"^\*-\*-(\d{2}) (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        day, hour, minute, second = map(int, match.groups())
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Day": day, "Hour": hour, "Minute": minute}
    raise RuntimeError(
        "Unsupported --schedule for macOS. Supported subset: "
        "'*-*-* *:00/15:00', '*-*-* *:05:00', '*-*-* 02:30:00', "
        "'Mon *-*-* 08:00:00', '*-*-01 00:01:00'."
    )


def humanize_schedule_for_display(schedule: str, timer_persistent: bool, max_width: int = 48) -> str:
    value = (schedule or "").strip()
    if not value:
        return "-"

    match = re.match(r"^\*-\*-\* \*:00/(\d{1,2}):00$", value)
    if match:
        minutes = int(match.group(1))
        summary = f"every {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        match = re.match(r"^\*-\*-\* \*:(\d{2}):00$", value)
        if match:
            summary = f"hourly at :{match.group(1)}"
        else:
            match = re.match(r"^\*-\*-\* (\d{2}):(\d{2}):00$", value)
            if match:
                summary = f"daily at {match.group(1)}:{match.group(2)}"
            else:
                match = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \*-\*-\* (\d{2}):(\d{2}):00$", value)
                if match:
                    summary = f"{match.group(1)} at {match.group(2)}:{match.group(3)}"
                else:
                    match = re.match(r"^\*-\*-(\d{2}) (\d{2}):(\d{2}):00$", value)
                    if match:
                        summary = f"monthly on day {int(match.group(1))} at {match.group(2)}:{match.group(3)}"
                    else:
                        summary = value

    return clip_text(summary, max_width)


def compute_next_run(schedule: str, now: Optional[dt.datetime] = None) -> str:
    if not schedule:
        return "-"
    now = now or dt.datetime.now().astimezone()
    sched_type, data = parse_schedule(schedule)
    if sched_type == "StartInterval":
        seconds = int(data)
        epoch = int(now.timestamp())
        next_epoch = ((epoch // seconds) + 1) * seconds
        return dt.datetime.fromtimestamp(next_epoch, tz=now.tzinfo).strftime("%Y-%m-%d %H:%M")
    if sched_type != "StartCalendarInterval":
        return "-"
    info = dict(data)
    for offset in range(1, 366 * 2):
        candidate_date = now.date() + dt.timedelta(days=offset // 1440)
        for minute_of_day in range(1440):
            candidate = dt.datetime.combine(
                candidate_date,
                dt.time(hour=minute_of_day // 60, minute=minute_of_day % 60, tzinfo=now.tzinfo),
            )
            if candidate <= now:
                continue
            if "Minute" in info and candidate.minute != info["Minute"]:
                continue
            if "Hour" in info and candidate.hour != info["Hour"]:
                continue
            if "Day" in info and candidate.day != info["Day"]:
                continue
            if "Weekday" in info:
                candidate_weekday = (candidate.weekday() + 1) % 7
                if candidate_weekday != info["Weekday"]:
                    continue
            if "Month" in info and candidate.month != info["Month"]:
                continue
            return candidate.strftime("%Y-%m-%d %H:%M")
    return "-"


def format_event_timestamp(value: str) -> str:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def read_event_stats(service: ManagedService) -> Dict[str, object]:
    event_path = event_file_for_service(service.name, service.scope)
    executions = 0
    last_run = "-"
    last_exit_status = "-"
    if not event_path.exists():
        return {
            "executions": 0,
            "restarts": 0,
            "last_run": "-",
            "last_exit_status": "-",
        }
    for raw in event_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if item.get("event") == "start":
            executions += 1
            last_run = format_event_timestamp(str(item.get("ts", "-")))
        elif item.get("event") == "end":
            last_exit_status = str(item.get("exit_status", "-"))
    restarts = max(0, executions - 1) if (not service.schedule and restart_policy_allows_restart(service.restart)) else 0
    return {
        "executions": executions,
        "restarts": restarts,
        "last_run": last_run,
        "last_exit_status": last_exit_status,
    }


def update_runtime_stats(service: ManagedService) -> Dict[str, Dict[str, object]]:
    ensure_storage()
    try:
        payload = json.loads(RUNTIME_STATS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {"services": {}}
    if not isinstance(payload, dict):
        payload = {"services": {}}
    services = payload.get("services")
    if not isinstance(services, dict):
        services = {}
        payload["services"] = services
    stats = read_event_stats(service)
    services[service.name] = stats
    RUNTIME_STATS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return services


def read_service_events(service: ManagedService) -> List[Dict[str, object]]:
    path = event_file_for_service(service.name, service.scope)
    if not path.exists():
        return []
    events: List[Dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def read_recent_run_root_pids(service: ManagedService, limit: int = 3) -> List[int]:
    starts = []
    for item in read_service_events(service):
        if str(item.get("event")) != "start":
            continue
        pid = parse_int(str(item.get("child_pid", item.get("pid", 0))))
        if pid > 0:
            starts.append(pid)
    if not starts:
        return []
    return list(reversed(starts[-max(1, limit):]))


def format_restarts_exec(service: ManagedService, runtime_stats: Dict[str, Dict[str, object]]) -> str:
    item = runtime_stats.get(service.name)
    if not item:
        return "-"
    return f"{item.get('restarts', 0)}/{item.get('executions', 0)}"


def bootstrap_service(service: ManagedService) -> None:
    proc = launchd.bootstrap_service(
        service.scope,
        launchd_label_for_service(service),
        plist_path_for_service(service),
        sudo_password=get_sudo_password(),
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Failed to bootstrap {service.name}. {details}".strip())


def bootout_service(service: ManagedService) -> None:
    launchd.bootout_service(
        service.scope,
        launchd_label_for_service(service),
        sudo_password=get_sudo_password(),
    )


def kickstart_service(service: ManagedService, kill_existing: bool = False) -> subprocess.CompletedProcess:
    return launchd.kickstart_service(
        service.scope,
        launchd_label_for_service(service),
        sudo_password=get_sudo_password(),
        kill_existing=kill_existing,
    )


def sync_registry_from_launchd(name: Optional[str] = None) -> int:
    services = load_registry(write_back=True)
    changed = 0
    target_names = {name} if name else None
    updated: List[ManagedService] = []
    for svc in services:
        if target_names and svc.name not in target_names:
            updated.append(svc)
            continue
        new_svc = ManagedService(**asdict(svc))
        path = plist_path_for_service(svc)
        if path.exists():
            with path.open("rb") as handle:
                plist = plistlib.load(handle)
            new_svc.working_dir = str(plist.get("WorkingDirectory", new_svc.working_dir))
            new_svc.user = str(plist.get("UserName", new_svc.user))
            stdout_path = str(plist.get("StandardOutPath", "")).strip()
            if stdout_path:
                new_svc.log_dir = str(Path(stdout_path).parent)
        if asdict(new_svc) != asdict(svc):
            changed += 1
            updated.append(new_svc)
        else:
            updated.append(svc)
    if changed:
        save_registry(updated)
    return changed


def track(args: argparse.Namespace) -> None:
    targets = list(args.targets or [])
    if not targets:
        raise RuntimeError("Use: skuld track <id ...> or skuld track <label ...>")
    if args.alias and len(targets) != 1:
        raise RuntimeError("--alias can only be used when tracking exactly one service.")

    resolved = resolve_discoverable_targets(targets)
    for entry in resolved:
        label = entry.label
        suggested = suggest_display_name(label)
        alias = (args.alias or prompt_display_name(label, suggested)).strip()
        ensure_display_name_available(alias)
        if get_managed(label):
            raise RuntimeError(f"'{label}' is already tracked in skuld.")
        raw = launchctl_print_service_raw(label)
        if not raw:
            raise RuntimeError(f"Could not inspect launchd service '{label}'.")
        plist_path = extract_launchctl_value(raw, "path")
        program = extract_launchctl_value(raw, "program") or label
        state = extract_launchctl_value(raw, "state")
        description = label if not state else f"{label} ({state})"
        service = ManagedService(
            name=label,
            exec_cmd=program,
            description=description,
            display_name=alias,
            launchd_label=label,
            plist_path_hint=plist_path,
            managed_by_skuld=False,
            scope="agent",
            log_dir="",
        )
        upsert_registry(service)
        ok(f"Tracked '{label}' as '{alias}'.")

def managed_uses_schedule(service: ManagedService) -> bool:
    return bool(service.schedule)


def apply_action_for_managed(service: ManagedService, action: str) -> None:
    if action == "start":
        bootstrap_service(service)
        if not managed_uses_schedule(service):
            proc = kickstart_service(service, kill_existing=False)
            if proc.returncode != 0:
                details = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(f"Failed to start {service.name}. {details}".strip())
        ok(f"start -> {service.display_name}")
        return
    if action == "stop":
        pid = read_pid(service)
        extra_pids = read_recent_run_root_pids(service)
        bootout_service(service)
        terminate_process_tree(pid)
        for extra_pid in extra_pids:
            if extra_pid != pid:
                terminate_process_tree(extra_pid)
        ok(f"stop -> {service.display_name}")
        return
    if action == "restart":
        pid = read_pid(service)
        extra_pids = read_recent_run_root_pids(service)
        bootout_service(service)
        terminate_process_tree(pid)
        for extra_pid in extra_pids:
            if extra_pid != pid:
                terminate_process_tree(extra_pid)
        bootstrap_service(service)
        if not managed_uses_schedule(service):
            proc = kickstart_service(service, kill_existing=True)
            if proc.returncode != 0:
                details = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(f"Failed to restart {service.name}. {details}".strip())
        ok(f"restart -> {service.display_name}")
        return
    raise RuntimeError(f"Unsupported action: {action}")


def start_stop(args: argparse.Namespace, action: str) -> None:
    for service in resolve_managed_many_arg(args):
        apply_action_for_managed(service, action)


def restart(args: argparse.Namespace) -> None:
    start_stop(args, "restart")


def exec_now(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    bootstrap_service(service)
    proc = kickstart_service(service, kill_existing=False)
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Failed to execute {service.name}. {details}".strip())
    ok(f"Execution started: {service.display_name}")


def status(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    info_map = launchctl_service_info(service)
    print(f"name: {service.display_name}")
    print(f"target: {service.name}")
    print(f"label: {launchd_label_for_service(service)}")
    print(f"scope: {service.scope}")
    print(f"domain: {domain_target(service.scope)}")
    print(f"loaded: {'yes' if info_map else 'no'}")
    print(f"pid: {info_map.get('PID', '-') if info_map else '-'}")
    print(f"last_exit_status: {info_map.get('LastExitStatus', '-') if info_map else '-'}")
    print(f"plist: {plist_path_for_service(service)}")


def tail_file(path: Path, lines: int, follow: bool) -> None:
    cmd = ["tail", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(str(path))
    try:
        run(cmd, check=False)
    except KeyboardInterrupt:
        return


def log_paths_for_service(service: ManagedService) -> Tuple[Optional[Path], Optional[Path]]:
    if service.managed_by_skuld or service.log_dir:
        log_dir = Path(service.log_dir)
        return log_dir / "stdout.log", log_dir / "stderr.log"

    plist_path = plist_path_for_service(service)
    if not plist_path.exists():
        return None, None

    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except Exception:
        return None, None

    stdout_raw = str(plist.get("StandardOutPath", "")).strip()
    stderr_raw = str(plist.get("StandardErrorPath", "")).strip()
    stdout_path = Path(stdout_raw) if stdout_raw else None
    stderr_path = Path(stderr_raw) if stderr_raw else None
    return stdout_path, stderr_path


def logs(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    if args.since:
        raise RuntimeError("--since is not supported on macOS yet. Logs are read from files.")
    if args.timer:
        info("--timer has no effect on macOS. launchd uses a single plist/job.")
    lines = resolve_lines_arg(args, default=100)
    stdout_path, stderr_path = log_paths_for_service(service)
    if not stdout_path and not stderr_path:
        raise RuntimeError(
            "Logs are only available on macOS when the registry entry has a "
            "compatible log_dir or the launchd plist declares StandardOutPath/StandardErrorPath."
        )
    stdout_exists = bool(stdout_path and stdout_path.exists())
    stderr_exists = bool(stderr_path and stderr_path.exists())
    if not stdout_exists and not stderr_exists:
        print("No logs found.")
        return
    if args.follow:
        workers: List[threading.Thread] = []
        if stdout_exists and stdout_path:
            print(f"==> {stdout_path}")
            workers.append(threading.Thread(target=tail_file, args=(stdout_path, lines, True), daemon=True))
        if stderr_exists and stderr_path:
            if stdout_exists:
                print()
            print(f"==> {stderr_path}")
            workers.append(threading.Thread(target=tail_file, args=(stderr_path, lines, True), daemon=True))
        for worker in workers:
            worker.start()
        try:
            for worker in workers:
                worker.join()
        except KeyboardInterrupt:
            return
        return

    if stdout_exists and stdout_path:
        print(f"==> {stdout_path}")
        tail_file(stdout_path, lines, False)
    if stderr_exists and stderr_path:
        if stdout_exists:
            print()
        print(f"==> {stderr_path}")
        tail_file(stderr_path, lines, False)


def read_cpu_memory(pid: int) -> Dict[str, str]:
    if pid <= 0:
        return {"cpu": "-", "memory": "-"}
    proc = run(["ps", "-o", "%cpu=", "-o", "rss=", "-p", str(pid)], check=False, capture=True)
    output = (proc.stdout or "").strip()
    if not output:
        return {"cpu": "-", "memory": "-"}
    parts = output.split()
    if len(parts) < 2:
        return {"cpu": "-", "memory": "-"}
    cpu = parts[0].replace(",", ".")
    try:
        memory_kib = int(parts[1])
    except ValueError:
        memory_kib = 0
    return {"cpu": f"{cpu}%", "memory": format_bytes_from_kib(memory_kib)}


def read_ports(pid: int) -> str:
    pids = read_process_tree_pids(pid)
    if not pids:
        return "-"
    proc = run(
        ["lsof", "-Pan", "-p", ",".join(str(item) for item in pids), "-iTCP", "-sTCP:LISTEN", "-iUDP"],
        check=False,
        capture=True,
    )
    tags: Set[str] = set()
    for raw in (proc.stdout or "").splitlines()[1:]:
        line = raw.strip()
        tcp_match = re.search(r"TCP .*:(\d+) \(LISTEN\)", line)
        if tcp_match:
            tags.add(f"{tcp_match.group(1)}/tcp")
        udp_match = re.search(r"UDP .*:(\d+)$", line)
        if udp_match:
            tags.add(f"{udp_match.group(1)}/udp")
    if not tags:
        return "-"
    ports = sorted(tags)
    if len(ports) <= 2:
        return ",".join(ports)
    return f"{','.join(ports[:2])}+{len(ports) - 2}"


def parse_vm_stat_count(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    if not digits:
        return 0
    return int(digits)


def read_host_overview() -> Dict[str, str]:
    uptime = "-"
    proc = run(["sysctl", "-n", "kern.boottime"], check=False, capture=True)
    match = re.search(r"sec = (\d+)", proc.stdout or "")
    if match:
        boot_time = int(match.group(1))
        uptime = format_duration_human(max(0, int(dt.datetime.now().timestamp()) - boot_time))
    cpu = "-"
    try:
        load1, load5, load15 = os.getloadavg()
        cores = max(1, os.cpu_count() or 1)
        pct = int((load1 / cores) * 100)
        cpu = f"{load1:.2f} {load5:.2f} {load15:.2f} ({pct}%)"
    except Exception:
        pass
    memory = "-"
    total_proc = run(["sysctl", "-n", "hw.memsize"], check=False, capture=True)
    vm_proc = run(["vm_stat"], check=False, capture=True)
    try:
        total = int((total_proc.stdout or "0").strip())
        page_size_match = re.search(r"page size of (\d+) bytes", vm_proc.stdout or "")
        page_size = int(page_size_match.group(1)) if page_size_match else 4096
        pages_free = 0
        pages_inactive = 0
        pages_speculative = 0
        for raw in (vm_proc.stdout or "").splitlines():
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            count = parse_vm_stat_count(value)
            if key.startswith("Pages free"):
                pages_free = count
            elif key.startswith("Pages inactive"):
                pages_inactive = count
            elif key.startswith("Pages speculative"):
                pages_speculative = count
        available = (pages_free + pages_inactive + pages_speculative) * page_size
        used = max(0, total - available)
        if total > 0:
            pct = int((used / total) * 100)
            memory = f"{format_bytes(str(used))}/{format_bytes(str(total))} ({pct}%)"
    except Exception:
        pass
    return {"uptime": uptime, "cpu(load1/5/15)": cpu, "memory": memory}


def render_host_panel() -> None:
    overview = read_host_overview()
    render_table(list(overview.keys()), [list(overview.values())])
    print()


def _render_services_table(compact: bool, sort_by: str = "name") -> None:
    services = list(load_registry())
    if not services:
        render_discoverable_services_hint()
        return
    runtime_stats: Dict[str, Dict[str, object]] = {}
    rows: List[Dict[str, object]] = []
    print()
    render_host_panel()
    for service in services:
        runtime_stats[service.name] = read_event_stats(service)
        pid = read_pid(service)
        usage = read_cpu_memory(pid)
        loaded = service_loaded(service)
        kind = "timer" if service.schedule else service.scope
        if loaded and pid > 0:
            service_state = colorize("active", "green")
        elif loaded:
            service_state = colorize("loaded", "yellow")
        else:
            service_state = colorize("inactive", "yellow")
        timer_state = colorize("scheduled", "green") if service.schedule and loaded else (colorize("inactive", "yellow") if service.schedule else colorize("n/a", "gray"))
        stats = runtime_stats[service.name]
        rows.append(
            {
                "id": service.id,
                "name": service.display_name,
                "service": service_state,
                "timer": timer_state,
                "triggers": humanize_schedule_for_display(service.schedule, service.timer_persistent),
                "cpu": usage["cpu"],
                "memory": usage["memory"],
                "ports": read_ports(pid),
            }
        )
    ordered_rows = sorted(rows, key=lambda row: service_sort_key(sort_by, row))
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    print()


def list_services(args: argparse.Namespace) -> None:
    _render_services_table(compact=False, sort_by=resolve_sort_arg(args))


def list_services_compact(sort_by: str = "name") -> None:
    _render_services_table(compact=True, sort_by=sort_by)


def catalog(_args: argparse.Namespace) -> None:
    render_discoverable_services_hint()


def stats(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    item = update_runtime_stats(service)[service.name]
    print(f"name: {service.display_name}")
    print(f"target: {service.name}")
    print(f"scope: {service.scope}")
    print(f"window: all retained event entries")
    print(f"executions: {item.get('executions', 0)}")
    print(f"restarts: {item.get('restarts', 0)}")
    print(f"last_run: {item.get('last_run', '-')}")
    print(f"last_exit_status: {item.get('last_exit_status', '-')}")

def doctor(_args: argparse.Namespace) -> None:
    services = load_registry()
    if not services:
        render_discoverable_services_hint()
        return
    issues = 0
    for service in services:
        prefix = f"[{service.display_name}|{service.name}]"
        plist_path = plist_path_for_service(service)
        if not plist_path.exists():
            print(f"{prefix} ERROR missing plist ({plist_path})")
            issues += 1
        else:
            print(f"{prefix} plist=ok")
        if service.managed_by_skuld and not wrapper_script_for_service(service.name, service.scope).exists():
            print(f"{prefix} ERROR missing wrapper script")
            issues += 1
        loaded = service_loaded(service)
        print(f"{prefix} loaded={'yes' if loaded else 'no'}")
        if service.scope == "agent" and service.user:
            print(f"{prefix} ERROR agent scope cannot store user")
            issues += 1
    if issues == 0:
        ok("doctor: no issues found.")
    else:
        err(f"doctor: found {issues} issue(s).")

def rename(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    new_name = (args.new_name or "").strip()
    ensure_display_name_available(new_name, current_name=service.name)
    if service.display_name == new_name:
        info("No changes detected.")
        return
    upsert_registry(
        ManagedService(
            name=service.name,
            exec_cmd=service.exec_cmd,
            description=service.description,
            display_name=new_name,
            launchd_label=service.launchd_label,
            plist_path_hint=service.plist_path_hint,
            managed_by_skuld=service.managed_by_skuld,
            schedule=service.schedule,
            working_dir=service.working_dir,
            user=service.user,
            restart=service.restart,
            timer_persistent=service.timer_persistent,
            id=service.id,
            backend=service.backend,
            scope=service.scope,
            log_dir=service.log_dir,
        )
    )
    ok(f"Renamed '{service.display_name}' to '{new_name}'.")


def untrack(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    remove_registry(service.name)
    ok(f"Removed '{service.display_name}' from the skuld registry.")


def describe(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    info_map = launchctl_service_info(service)
    stats_map = read_event_stats(service)
    print(f"name: {service.display_name}")
    print(f"target: {service.name}")
    print(f"description: {service.description}")
    print(f"exec: {service.exec_cmd}")
    print(f"scope: {service.scope}")
    print(f"user: {service.user or '-'}")
    print(f"working_dir: {service.working_dir or '-'}")
    print(f"restart: {service.restart}")
    print(f"schedule: {service.schedule or '-'}")
    print(f"timer_persistent: {service.timer_persistent}")
    print(f"log_dir: {service.log_dir}")
    print("---")
    print(f"loaded: {'yes' if info_map else 'no'}")
    print(f"pid: {info_map.get('PID', '-') if info_map else '-'}")
    print(f"last_exit_status: {info_map.get('LastExitStatus', '-') if info_map else '-'}")
    print(f"next_run: {compute_next_run(service.schedule)}")
    print(f"last_run: {stats_map.get('last_run', '-')}")
    print(f"plist: {plist_path_for_service(service)}")


def sync(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args, required=False)
    name = service.name if service else None
    changed = sync_registry_from_launchd(name)
    if changed == 0:
        ok("Registry is already up to date.")
    else:
        ok(f"Registry updated for {changed} service(s).")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skuld", description="CLI for tracking and operating launchd jobs")
    parser.add_argument(
        "--no-env-sudo",
        action="store_true",
        help="Disable SKULD_SUDO_PASSWORD from env/.env and use regular sudo behavior",
    )
    parser.add_argument("--ascii", action="store_true", help="Force ASCII table borders")
    parser.add_argument("--unicode", action="store_true", help="Force Unicode table borders")
    parser.add_argument("--sort", choices=SORT_CHOICES, default="name", help="Sort service views by name, id, cpu, or memory")
    sub = parser.add_subparsers(dest="command", required=False)

    list_parser = sub.add_parser("list", help="List services tracked by skuld")
    list_parser.add_argument("--sort", choices=SORT_CHOICES, default="name", help="Sort by name, id, cpu, or memory")
    list_parser.set_defaults(func=list_services)

    catalog_parser = sub.add_parser("catalog", help="Show the current launchd discovery catalog")
    catalog_parser.set_defaults(func=catalog)

    track_parser = sub.add_parser("track", help="Track launchd services from the current session catalog")
    track_parser.add_argument("targets", nargs="+", help="Catalog ids or launchd labels")
    track_parser.add_argument("--alias", help="Friendly name shown by skuld when tracking a single service")
    track_parser.set_defaults(func=track)

    rename_parser = sub.add_parser("rename", help="Change the display name of a tracked service")
    rename_parser.add_argument("name", nargs="?")
    rename_parser.add_argument("new_name")
    rename_parser.add_argument("--name", dest="name_flag")
    rename_parser.add_argument("--id", dest="id_flag", type=int)
    rename_parser.set_defaults(func=rename)

    untrack_parser = sub.add_parser("untrack", help="Remove a service from the skuld registry without touching launchd")
    untrack_parser.add_argument("name", nargs="?")
    untrack_parser.add_argument("--name", dest="name_flag")
    untrack_parser.add_argument("--id", dest="id_flag", type=int)
    untrack_parser.set_defaults(func=untrack)

    exec_parser = sub.add_parser("exec", help="Execute a service immediately")
    exec_parser.add_argument("name", nargs="?")
    exec_parser.add_argument("--name", dest="name_flag")
    exec_parser.add_argument("--id", dest="id_flag", type=int)
    exec_parser.set_defaults(func=exec_now)

    start_parser = sub.add_parser("start", help="Start one or more services")
    start_parser.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    start_parser.add_argument("--name", dest="name_flag")
    start_parser.add_argument("--id", dest="id_flag", type=int)
    start_parser.set_defaults(func=lambda a: start_stop(a, "start"))

    stop_parser = sub.add_parser("stop", help="Stop one or more services")
    stop_parser.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    stop_parser.add_argument("--name", dest="name_flag")
    stop_parser.add_argument("--id", dest="id_flag", type=int)
    stop_parser.set_defaults(func=lambda a: start_stop(a, "stop"))

    restart_parser = sub.add_parser("restart", help="Restart one or more services")
    restart_parser.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    restart_parser.add_argument("--name", dest="name_flag")
    restart_parser.add_argument("--id", dest="id_flag", type=int)
    restart_parser.set_defaults(func=restart)

    status_parser = sub.add_parser("status", help="Service status")
    status_parser.add_argument("name", nargs="?")
    status_parser.add_argument("--name", dest="name_flag")
    status_parser.add_argument("--id", dest="id_flag", type=int)
    status_parser.set_defaults(func=status)

    logs_parser = sub.add_parser("logs", help="Show logs from files")
    logs_parser.add_argument("name", nargs="?")
    logs_parser.add_argument("lines_pos", nargs="?", type=int)
    logs_parser.add_argument("--name", dest="name_flag")
    logs_parser.add_argument("--id", dest="id_flag", type=int)
    logs_parser.add_argument("--lines", type=int, default=None)
    logs_parser.add_argument("--follow", action="store_true", help="Follow logs in real time")
    logs_parser.add_argument("--folow", dest="follow", action="store_true", help=argparse.SUPPRESS)
    logs_parser.add_argument("--since", help="Not supported on macOS file logs")
    logs_parser.add_argument("--timer", action="store_true", help="No effect on macOS; kept for CLI compatibility")
    logs_parser.add_argument("--output", default="short", help="Ignored on macOS file logs")
    logs_parser.add_argument("--plain", action="store_true", help="Ignored on macOS file logs")
    logs_parser.set_defaults(func=logs)

    stats_parser = sub.add_parser("stats", help="Show execution/restart counters for a tracked service")
    stats_parser.add_argument("name", nargs="?")
    stats_parser.add_argument("--name", dest="name_flag")
    stats_parser.add_argument("--id", dest="id_flag", type=int)
    stats_parser.add_argument("--since", help="Ignored on macOS event stats")
    stats_parser.add_argument("--boot", action="store_true", help="Ignored on macOS event stats")
    stats_parser.set_defaults(func=stats)

    doctor_parser = sub.add_parser("doctor", help="Check registry/launchd inconsistencies")
    doctor_parser.set_defaults(func=doctor)

    describe_parser = sub.add_parser("describe", help="Show details for a tracked service")
    describe_parser.add_argument("name", nargs="?")
    describe_parser.add_argument("--name", dest="name_flag")
    describe_parser.add_argument("--id", dest="id_flag", type=int)
    describe_parser.set_defaults(func=describe)

    sync_parser = sub.add_parser("sync", help="Backfill missing registry fields from launchd")
    sync_parser.add_argument("name", nargs="?", help="Sync only one managed service")
    sync_parser.add_argument("--name", dest="name_flag", help="Sync only one managed service")
    sync_parser.add_argument("--id", dest="id_flag", type=int, help="Sync only one managed service by id")
    sync_parser.set_defaults(func=sync)

    version_parser = sub.add_parser("version", help="Show version")
    version_parser.set_defaults(func=lambda _args: print(VERSION))

    sudo_parser = sub.add_parser("sudo", help="Helpers for one-off sudo usage")
    sudo_sub = sudo_parser.add_subparsers(dest="sudo_command", required=True)

    sudo_check_parser = sudo_sub.add_parser("check", help="Check whether sudo can run non-interactively")
    sudo_check_parser.set_defaults(func=sudo_check)

    sudo_run_parser = sudo_sub.add_parser("run", help="Run one command through sudo")
    sudo_run_parser.add_argument("command", nargs=argparse.REMAINDER)
    sudo_run_parser.set_defaults(func=sudo_run_command)

    return parser


def configure_cli_globals(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    global USE_ENV_SUDO, FORCE_TABLE_ASCII, FORCE_TABLE_UNICODE
    USE_ENV_SUDO = not args.no_env_sudo
    FORCE_TABLE_ASCII = bool(args.ascii)
    FORCE_TABLE_UNICODE = bool(args.unicode)
    if FORCE_TABLE_ASCII and FORCE_TABLE_UNICODE:
        parser.error("choose only one of --ascii or --unicode")


def main() -> int:
    return skuld_cli.run_current_process_backend(
        parser=build_parser(),
        configure_globals=configure_cli_globals,
        load_registry=load_registry,
        list_services_compact=list_services_compact,
        resolve_sort_arg=resolve_sort_arg,
        err=err,
    )


if __name__ == "__main__":
    raise SystemExit(main())
