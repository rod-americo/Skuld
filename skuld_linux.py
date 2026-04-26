#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import skuld_common as common
import skuld_cli
import skuld_linux_actions as linux_actions
import skuld_linux_commands as linux_commands
from skuld_linux_model import (
    DiscoverableService,
    ManagedService,
    VALID_SCOPES,
    format_scoped_name,
    managed_service_key,
    managed_sort_key,
    normalize_registry_item,
    normalize_scope,
    scope_sort_value,
    split_scope_token,
    validate_registry_service,
)
import skuld_linux_runtime as linux_runtime
import skuld_linux_stats as linux_stats
import skuld_linux_systemd as systemd
import skuld_linux_sync as linux_sync
import skuld_linux_targets as linux_targets
import skuld_linux_timers as timers
import skuld_linux_view as linux_view
import skuld_tables as tables
from skuld_registry import RegistryStore

VERSION = "0.3.0"
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._@-]*$")
SHELL_SAFE_RE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")
SKULD_HOME = Path(os.environ.get("SKULD_HOME", Path.home() / ".local/share/skuld"))
REGISTRY_FILE = SKULD_HOME / "services.json"
RUNTIME_STATS_FILE = Path(os.environ.get("SKULD_RUNTIME_STATS_FILE", "/var/lib/skuld/journal_stats.json"))
DEFAULT_ENV_FILE = Path(".env")
USE_ENV_SUDO = True
FORCE_TABLE_ASCII = False
FORCE_TABLE_UNICODE = False
SYSTEMD_UNIT_STARTED_MESSAGE_ID = linux_runtime.SYSTEMD_UNIT_STARTED_MESSAGE_ID
SORT_CHOICES = ("id", "name", "cpu", "memory")
DISCOVERABLE_SCOPE_CHOICES = ("all", "system", "user")


def ensure_storage() -> None:
    SKULD_HOME.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("[]", encoding="utf-8")


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


def registry_store() -> RegistryStore[ManagedService]:
    return RegistryStore(
        home=SKULD_HOME,
        registry_file=REGISTRY_FILE,
        normalize_item=normalize_registry_item,
        validate_service=validate_registry_service,
        sort_key=managed_sort_key,
        service_key=lambda service: managed_service_key(service.name, service.scope),
        required_fields=("name", "exec_cmd", "description"),
    )


def load_registry(*, write_back: bool = False) -> List[ManagedService]:
    return registry_store().load(write_back=write_back)


def save_registry(services: List[ManagedService]) -> None:
    registry_store().save(services)


def upsert_registry(service: ManagedService) -> None:
    registry_store().upsert(service)


def remove_registry(name: str, scope: str) -> None:
    registry_store().remove(managed_service_key(name, scope))


def find_managed_by_name(name: str) -> List[ManagedService]:
    return [svc for svc in load_registry() if svc.name == name]


def get_managed(name: str, scope: Optional[str] = None) -> Optional[ManagedService]:
    matches = find_managed_by_name(name)
    if scope is not None:
        normalized_scope = normalize_scope(scope)
        for svc in matches:
            if svc.scope == normalized_scope:
                return svc
        return None
    if len(matches) == 1:
        return matches[0]
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


def require_managed(name: str, scope: Optional[str] = None) -> ManagedService:
    svc = get_managed(name, scope=scope)
    if not svc:
        raise RuntimeError(
            f"'{name}' is not in the skuld registry. "
            "Only services tracked by skuld can be monitored."
        )
    return svc


def err(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"[skuld] {msg}")


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


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


def parse_first_float(text: str) -> float:
    return common.parse_first_float(text)


def service_sort_key(sort_by: str, row: Dict[str, object]) -> tuple:
    return common.service_sort_key(sort_by, row)


def resolve_sort_arg(args: Optional[argparse.Namespace]) -> str:
    return common.resolve_sort_arg(args, SORT_CHOICES)


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError("Invalid name. Use [a-zA-Z0-9._@-] and start with a letter/number.")


def ensure_display_name_available(display_name: str, current_id: Optional[int] = None) -> None:
    linux_targets.ensure_display_name_available(
        display_name,
        current_id=current_id,
        validate_name=validate_name,
        load_registry=load_registry,
    )


def normalize_service_name(value: str) -> str:
    raw = (value or "").strip()
    if raw.endswith(".service"):
        raw = raw[:-8]
    elif raw.endswith(".timer"):
        raw = raw[:-6]
    validate_name(raw)
    return raw


def normalize_target_token(value: str) -> tuple[Optional[str], str]:
    scope, raw_name = split_scope_token(value)
    return scope, normalize_service_name(raw_name)


def suggest_display_name(value: str) -> str:
    raw = normalize_service_name(value)
    tokens = [part for part in raw.split(".") if part]
    if len(tokens) >= 2 and tokens[-1].isdigit():
        while tokens and tokens[-1].isdigit():
            tokens.pop()
    if len(tokens) >= 2:
        return "-".join(tokens[-2:])
    return raw


def prompt_display_name(target: str, suggested: str) -> str:
    if not sys.stdin.isatty():
        return suggested
    value = input(f"Display name for {target} [{suggested}]: ").strip()
    chosen = value or suggested
    validate_name(chosen)
    return chosen


def resolve_name_arg(args: argparse.Namespace, required: bool = True) -> Optional[str]:
    return linux_targets.resolve_name_arg(args, required=required)


def resolve_managed_from_token(token: str) -> Optional[ManagedService]:
    return linux_targets.resolve_managed_from_token(
        token,
        get_managed_by_display_name=get_managed_by_display_name,
        get_managed_by_id=get_managed_by_id,
        normalize_target_token=normalize_target_token,
        get_managed=get_managed,
        find_managed_by_name=find_managed_by_name,
        format_scoped_name=format_scoped_name,
        managed_sort_key=managed_sort_key,
    )


def resolve_managed_arg(args: argparse.Namespace, required: bool = True) -> Optional[ManagedService]:
    return linux_targets.resolve_managed_arg(
        args,
        required=required,
        resolve_managed_from_token=resolve_managed_from_token,
        get_managed_by_id=get_managed_by_id,
    )


def resolve_managed_many_arg(args: argparse.Namespace) -> List[ManagedService]:
    return linux_targets.resolve_managed_many_arg(
        args,
        resolve_managed_from_token=resolve_managed_from_token,
    )


def resolve_lines_arg(args: argparse.Namespace, default: int = 100) -> int:
    lines_flag = getattr(args, "lines", None)
    lines_pos = getattr(args, "lines_pos", None)
    if lines_flag is not None:
        return lines_flag
    if lines_pos is not None:
        return lines_pos
    return default


def run(
    cmd: List[str],
    check: bool = True,
    capture: bool = False,
    input_text: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    return common.run_command(
        cmd,
        check=check,
        capture=capture,
        input_text=input_text,
        env=env,
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


def journal_permission_hint(stderr_text: str) -> bool:
    return linux_runtime.journal_permission_hint(stderr_text)


def require_systemctl() -> None:
    systemd.require_systemctl()


def systemd_scope_env(scope: str) -> Optional[Dict[str, str]]:
    return systemd.scope_env(scope)


def systemctl_command(scope: str, args: List[str]) -> List[str]:
    return systemd.systemctl_command(scope, args)


def journalctl_command(scope: str, args: List[str]) -> List[str]:
    return systemd.journalctl_command(scope, args)


def run_systemctl_action(scope: str, args: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return systemd.run_systemctl_action(
        scope,
        args,
        sudo_password=get_sudo_password(),
        check=check,
        capture=capture,
    )


def unit_exists(unit: str, scope: str = "system") -> bool:
    return systemd.unit_exists(unit, scope=scope)


def unit_active(unit: str, scope: str = "system") -> str:
    return systemd.unit_active(unit, scope=scope)


def display_unit_state(status: str) -> str:
    if status == "activating":
        return "running"
    return status


def format_bytes(value: str) -> str:
    return common.format_bytes(value)


def format_cpu_nsec(value: str) -> str:
    return linux_stats.format_cpu_nsec(value)


def format_duration_human(seconds: int) -> str:
    return common.format_duration_human(seconds)


def read_host_overview() -> Dict[str, str]:
    return linux_stats.read_host_overview()


def parse_int(value: str) -> int:
    return common.parse_int(value)


def read_proc_cpu_nsec(pid: int) -> Optional[int]:
    return linux_stats.read_proc_cpu_nsec(pid)


def read_proc_memory_bytes(pid: int) -> Optional[int]:
    return linux_stats.read_proc_memory_bytes(pid)


def format_gpu_mib(value: int) -> str:
    return linux_stats.format_gpu_mib(value)


def read_gpu_memory_by_pid() -> Optional[Dict[int, int]]:
    return linux_stats.read_gpu_memory_by_pid(run)


def read_unit_usage(service_unit: str, scope: str = "system", gpu_memory_by_pid: Optional[Dict[int, int]] = None) -> Dict[str, str]:
    return linux_stats.read_unit_usage(
        unit_exists,
        systemctl_show,
        service_unit,
        scope=scope,
        gpu_memory_by_pid=gpu_memory_by_pid,
    )


def get_main_pid(service_unit: str, scope: str = "system") -> int:
    return linux_stats.get_main_pid(unit_exists, systemctl_show, service_unit, scope=scope)


def read_unit_pids(service_unit: str, scope: str = "system") -> List[int]:
    return linux_stats.read_unit_pids(unit_exists, systemctl_show, service_unit, scope=scope)


def parse_listen_ports_from_ss(output: str, pids: Set[int]) -> List[str]:
    return linux_stats.parse_listen_ports_from_ss(output, pids)


def summarize_ports(ports: List[str], max_items: int = 2) -> str:
    return linux_stats.summarize_ports(ports, max_items=max_items)


def read_socket_inodes_for_pid(pid: int) -> Set[str]:
    return linux_stats.read_socket_inodes_for_pid(pid)


def parse_proc_net_ports(path: Path, proto: str, socket_inodes: Set[str]) -> Set[str]:
    return linux_stats.parse_proc_net_ports(path, proto, socket_inodes)


def read_unit_ports_from_proc(pid: int) -> List[str]:
    return linux_stats.read_unit_ports_from_proc(pid)


def read_unit_ports_from_proc_pids(pids: List[int]) -> List[str]:
    return linux_stats.read_unit_ports_from_proc_pids(pids)


def read_unit_ports(service_unit: str, scope: str = "system") -> str:
    return linux_stats.read_unit_ports(read_unit_pids, run, run_sudo, service_unit, scope=scope)


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
    return tables.shrink_service_table_widths(columns, widths, max_width)


def fit_service_table(rows: List[Dict[str, object]], max_width: Optional[int] = None) -> tuple[List[str], List[List[str]]]:
    return tables.fit_service_table(rows, max_width=max_width)


def render_host_panel() -> None:
    tables.render_host_panel(read_host_overview(), render_table)


def load_runtime_stats() -> Dict[str, Dict[str, int]]:
    return linux_runtime.load_runtime_stats(RUNTIME_STATS_FILE)


def format_restarts_exec(name: str, runtime_stats: Dict[str, Dict[str, int]]) -> str:
    return linux_runtime.format_restarts_exec(name, runtime_stats)


def clip_text(text: str, width: int) -> str:
    return common.clip_text(text, width)


def timer_triggers_for_display(svc: ManagedService, max_width: int = 48) -> str:
    timer_unit = f"{svc.name}.timer"
    summary = "-"

    if unit_exists(timer_unit, scope=svc.scope):
        directives = timers.parse_unit_directive_values(systemctl_cat(timer_unit, scope=svc.scope))
        calendar_parts = [timers.humanize_timer_calendar(raw) for raw in directives.get("OnCalendar", []) if raw.strip()]
        calendar_summary = timers.summarize_calendar_phrases(calendar_parts)
        if calendar_summary:
            summary = calendar_summary
        elif directives.get("OnUnitActiveSec"):
            summary = f"every {timers.compact_systemd_duration(directives['OnUnitActiveSec'][0])}"
        elif directives.get("OnUnitInactiveSec"):
            summary = f"every {timers.compact_systemd_duration(directives['OnUnitInactiveSec'][0])} after stop"
        elif directives.get("OnStartupSec"):
            summary = f"{timers.compact_systemd_duration(directives['OnStartupSec'][0])} after startup"
        elif directives.get("OnBootSec"):
            summary = f"{timers.compact_systemd_duration(directives['OnBootSec'][0])} after boot"
        elif directives.get("OnActiveSec"):
            summary = f"{timers.compact_systemd_duration(directives['OnActiveSec'][0])} after timer starts"

    if summary == "-":
        schedule = schedule_for_display(svc)
        if schedule:
            summary = timers.humanize_timer_calendar(schedule)

    return clip_text(summary, max_width) if max_width > 0 else summary


def read_timer_schedule(name: str, scope: str = "system") -> str:
    timer_unit = f"{name}.timer"
    show = systemctl_show(timer_unit, ["OnCalendar"], scope=scope)
    schedule = (show.get("OnCalendar", "") or "").strip()
    if schedule:
        return schedule
    directives = parse_unit_directives(systemctl_cat(timer_unit, scope=scope))
    return (directives.get("OnCalendar", "") or "").strip()


def read_timer_persistent(name: str, scope: str = "system", default: bool = True) -> bool:
    timer_unit = f"{name}.timer"
    if not unit_exists(timer_unit, scope=scope):
        return default
    show = systemctl_show(timer_unit, ["Persistent"], scope=scope)
    value = (show.get("Persistent", "") or "").strip()
    if value:
        return parse_bool(value, default=default)
    directives = parse_unit_directives(systemctl_cat(timer_unit, scope=scope))
    raw = (directives.get("Persistent", "") or "").strip()
    if raw:
        return parse_bool(raw, default=default)
    return default


def read_timer_next_run(name: str, scope: str = "system") -> str:
    timer_unit = f"{name}.timer"
    show = systemctl_show(timer_unit, ["NextElapseUSecRealtime"], scope=scope)
    value = (show.get("NextElapseUSecRealtime", "") or "").strip()
    if not value or value.lower() == "n/a":
        return "-"
    return value


def read_timer_last_run(name: str, scope: str = "system") -> str:
    timer_unit = f"{name}.timer"
    show = systemctl_show(timer_unit, ["LastTriggerUSec"], scope=scope)
    value = (show.get("LastTriggerUSec", "") or "").strip()
    if not value or value.lower() == "n/a":
        return "-"
    return value


def schedule_for_display(svc: ManagedService) -> str:
    if svc.schedule:
        return svc.schedule
    return read_timer_schedule(svc.name, scope=svc.scope)


def sync_registry_from_systemd(target: Optional[ManagedService] = None) -> int:
    return linux_sync.sync_registry_from_systemd(
        target,
        load_registry=load_registry,
        save_registry=save_registry,
        managed_service_key=managed_service_key,
        unit_exists=unit_exists,
        systemctl_show=systemctl_show,
        read_timer_schedule=read_timer_schedule,
        read_timer_persistent=read_timer_persistent,
    )


def systemctl_show(unit: str, props: List[str], scope: str = "system") -> Dict[str, str]:
    return systemd.systemctl_show(unit, props, scope=scope)


def systemctl_cat(unit: str, scope: str = "system") -> str:
    return systemd.systemctl_cat(unit, scope=scope)


def list_discoverable_services_for_scope(scope: str) -> List[DiscoverableService]:
    proc = run(
        systemctl_command(scope, ["list-unit-files", "--type=service", "--type=timer", "--no-legend", "--no-pager"]),
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

    names = sorted(name for name, states in discovered.items() if states.get("service"))
    result: List[DiscoverableService] = []
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
        raise ValueError(f"Invalid catalog scope '{value}'. Use 'all', 'system', or 'user'.")
    return raw


def list_discoverable_services(scope_filter: str = "all") -> List[DiscoverableService]:
    require_systemctl()
    normalized_scope = normalize_discoverable_scope(scope_filter)
    entries = list_discoverable_services_for_scope("system") + list_discoverable_services_for_scope("user")
    entries.sort(key=lambda item: (item.name.lower(), scope_sort_value(item.scope)))
    for idx, entry in enumerate(entries, start=1):
        entry.index = idx
    if normalized_scope == "all":
        return entries
    return [entry for entry in entries if entry.scope == normalized_scope]


def render_discoverable_services_hint(empty_registry_note: bool = True, scope_filter: str = "all") -> None:
    if empty_registry_note:
        print("No services tracked by skuld.")
    normalized_scope = normalize_discoverable_scope(scope_filter)
    entries = list_discoverable_services(scope_filter=normalized_scope)
    if not entries:
        if normalized_scope == "all":
            print("No systemd services were found.")
        else:
            print(f"No {normalized_scope} systemd services were found.")
        return
    if normalized_scope == "all":
        print("Available systemd services (system + user):")
    else:
        print(f"Available systemd services ({normalized_scope} only):")
    for entry in entries:
        print(
            f"  {entry.index}. [{entry.scope}] {entry.name}  "
            f"service={entry.service_state}  timer={entry.timer_state}"
        )
    print()
    print("Use: skuld track <id ...>, skuld track <service ...>, or skuld track <system:name|user:name ...>")


def resolve_discoverable_target_by_name(name: str, scope: Optional[str], entries: List[DiscoverableService]) -> DiscoverableService:
    matches = [entry for entry in entries if entry.name == name and (scope is None or entry.scope == scope)]
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
            raise RuntimeError(f"Service '{name}.service' does not exist in the {scope} systemd catalog.")
        raise RuntimeError(f"Service '{name}.service' does not exist in systemd.")
    if len(matches) > 1:
        scopes = ", ".join(format_scoped_name(name, item.scope) for item in sorted(matches, key=lambda item: scope_sort_value(item.scope)))
        raise RuntimeError(f"Service '{name}' exists in multiple scopes. Use one of: {scopes}.")
    return matches[0]


def resolve_discoverable_targets(targets: List[str]) -> List[DiscoverableService]:
    entries = list_discoverable_services()
    by_index = {entry.index: entry for entry in entries}
    resolved: List[DiscoverableService] = []
    seen: Set[tuple] = set()
    for raw_target in targets:
        token = (raw_target or "").strip()
        if not token:
            continue
        entry: Optional[DiscoverableService]
        if token.isdigit():
            entry = by_index.get(int(token))
            if not entry:
                raise RuntimeError(f"Catalog id '{token}' not found.")
        else:
            scope, name = normalize_target_token(token)
            entry = resolve_discoverable_target_by_name(name, scope, entries)
        key = (entry.scope, entry.name)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(entry)
    if not resolved:
        raise RuntimeError("Use: skuld track <id ...>, skuld track <service ...>, or skuld track <system:name|user:name ...>")
    return resolved


def parse_unit_directives(unit_text: str) -> Dict[str, str]:
    directives: Dict[str, str] = {}
    for raw in unit_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        directives[k] = v
    return directives


def parse_bool(value: str, default: bool = True) -> bool:
    return common.parse_bool(value, default=default)


def _render_services_table(compact: bool, sort_by: str = "name") -> None:
    require_systemctl()
    services = list(load_registry())
    if not services:
        render_discoverable_services_hint()
        return

    gpu_memory_by_pid = read_gpu_memory_by_pid()
    print()
    render_host_panel()
    rows = linux_view.build_service_rows(
        services,
        unit_exists=unit_exists,
        unit_active=unit_active,
        display_unit_state=display_unit_state,
        colorize=colorize,
        read_unit_usage=read_unit_usage,
        timer_triggers_for_display=timer_triggers_for_display,
        read_unit_ports=read_unit_ports,
        gpu_memory_by_pid=gpu_memory_by_pid,
    )
    ordered_rows = tables.sort_service_rows(rows, sort_by)
    headers, fitted_rows = fit_service_table(ordered_rows)
    render_table(headers, fitted_rows)
    print()


def list_services(args: argparse.Namespace) -> None:
    _render_services_table(compact=False, sort_by=resolve_sort_arg(args))


def list_services_compact(sort_by: str = "name") -> None:
    _render_services_table(compact=True, sort_by=sort_by)


def catalog(args: argparse.Namespace) -> None:
    render_discoverable_services_hint(
        empty_registry_note=False,
        scope_filter=getattr(args, "scope", "all"),
    )


def exec_now(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    require_systemctl()
    linux_actions.execute_now(
        svc,
        run_systemctl_action=run_systemctl_action,
        ok=ok,
    )


def start_stop(args: argparse.Namespace, action: str) -> None:
    services = resolve_managed_many_arg(args)
    require_systemctl()
    linux_actions.apply_lifecycle_action_to_services(
        services,
        action,
        unit_exists=unit_exists,
        run_systemctl_action=run_systemctl_action,
        ok=ok,
    )


def restart(args: argparse.Namespace) -> None:
    start_stop(args, "restart")


def status(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    require_systemctl()
    linux_commands.show_status(
        svc,
        format_scoped_name=format_scoped_name,
        systemd_scope_env=systemd_scope_env,
        systemctl_command=systemctl_command,
        run=run,
    )


def logs(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    lines = resolve_lines_arg(args, default=100)
    require_systemctl()
    linux_commands.show_logs(
        svc,
        timer=args.timer,
        since=args.since,
        follow=args.follow,
        plain=args.plain,
        output=args.output,
        lines=lines,
        journalctl_command=journalctl_command,
        systemd_scope_env=systemd_scope_env,
        run=run,
        run_sudo=run_sudo,
        journal_permission_hint=journal_permission_hint,
    )


def count_unit_starts(unit: str, scope: str = "system", since: Optional[str] = None, boot: bool = False) -> int:
    return linux_runtime.count_unit_starts(
        unit=unit,
        scope=scope,
        systemd_scope_env=systemd_scope_env,
        journalctl_command=journalctl_command,
        run_cmd=run,
        run_sudo_cmd=run_sudo,
        since=since,
        boot=boot,
    )


def read_restart_count(name: str, scope: str = "system") -> str:
    return linux_runtime.read_restart_count(
        name=name,
        scope=scope,
        unit_exists=unit_exists,
        systemctl_show=systemctl_show,
    )


def stats(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    require_systemctl()
    linux_commands.show_stats(
        svc,
        since=args.since,
        boot=args.boot,
        sync_registry_from_systemd=sync_registry_from_systemd,
        count_unit_starts=count_unit_starts,
        read_restart_count=read_restart_count,
        format_scoped_name=format_scoped_name,
    )


def track(args: argparse.Namespace) -> None:
    require_systemctl()
    targets = list(args.targets or [])
    if not targets:
        raise RuntimeError("Use: skuld track <id ...>, skuld track <service ...>, or skuld track <system:name|user:name ...>")
    if args.alias and len(targets) != 1:
        raise RuntimeError("--alias can only be used when tracking exactly one service.")

    resolved = resolve_discoverable_targets(targets)
    for entry in resolved:
        name = entry.name
        suggested = suggest_display_name(name)
        target_label = format_scoped_name(name, entry.scope)
        alias = (args.alias or prompt_display_name(target_label, suggested)).strip()
        ensure_display_name_available(alias)
        if get_managed(name, scope=entry.scope):
            raise RuntimeError(f"'{target_label}' is already tracked in skuld.")

        service_unit = f"{name}.service"
        timer_unit = f"{name}.timer"
        service_text = systemctl_cat(service_unit, scope=entry.scope)
        directives = parse_unit_directives(service_text)
        exec_line = directives.get("ExecStart", "")
        if exec_line.startswith("/bin/bash -lc "):
            exec_line = exec_line[len("/bin/bash -lc "):].strip()
            if len(exec_line) >= 2 and exec_line[0] == exec_line[-1] and exec_line[0] in ("'", '"'):
                exec_line = exec_line[1:-1]
        if not exec_line:
            exec_line = service_unit

        show_service = systemctl_show(
            service_unit,
            ["Description", "WorkingDirectory", "User", "Restart"],
            scope=entry.scope,
        )
        schedule = ""
        timer_persistent = True
        if unit_exists(timer_unit, scope=entry.scope):
            show_timer = systemctl_show(timer_unit, ["OnCalendar", "Persistent"], scope=entry.scope)
            schedule = show_timer.get("OnCalendar", "") or ""
            timer_persistent = parse_bool(show_timer.get("Persistent", "true"), default=True)

        upsert_registry(
            ManagedService(
                name=name,
                scope=entry.scope,
                exec_cmd=exec_line,
                description=show_service.get("Description", f"Tracked service: {name}"),
                display_name=alias,
                schedule=schedule,
                working_dir=show_service.get("WorkingDirectory", "") or "",
                user=show_service.get("User", "") or "",
                restart=show_service.get("Restart", "on-failure") or "on-failure",
                timer_persistent=timer_persistent,
            )
        )
        ok(f"Tracked '{target_label}' as '{alias}'.")


def rename(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    linux_commands.rename_service(
        svc,
        args.new_name,
        ensure_display_name_available=ensure_display_name_available,
        service_factory=ManagedService,
        upsert_registry=upsert_registry,
        info=info,
        ok=ok,
    )


def untrack(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args)
    linux_commands.untrack_service(svc, remove_registry=remove_registry, ok=ok)


def doctor(_args: argparse.Namespace) -> None:
    require_systemctl()
    services = load_registry()
    if not services:
        print("No services tracked by skuld.")
        return
    linux_commands.doctor_services(
        services,
        unit_exists=unit_exists,
        unit_active=unit_active,
        display_unit_state=display_unit_state,
        read_timer_schedule=read_timer_schedule,
        systemctl_cat=systemctl_cat,
        parse_unit_directives=parse_unit_directives,
        format_scoped_name=format_scoped_name,
        ok=ok,
        err=err,
    )


def describe(args: argparse.Namespace) -> None:
    target = resolve_managed_arg(args)
    require_systemctl()
    linux_commands.describe_service(
        target,
        require_managed=require_managed,
        unit_exists=unit_exists,
        systemctl_show=systemctl_show,
        format_scoped_name=format_scoped_name,
    )


def sync(args: argparse.Namespace) -> None:
    svc = resolve_managed_arg(args, required=False)
    require_systemctl()
    changed = sync_registry_from_systemd(svc)
    if changed == 0:
        ok("Registry is already up to date.")
    else:
        ok(f"Registry updated for {changed} service(s).")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skuld", description="CLI for tracking and operating systemd services")
    p.add_argument(
        "--no-env-sudo",
        action="store_true",
        help="Disable SKULD_SUDO_PASSWORD from env/.env and use regular sudo behavior",
    )
    p.add_argument("--ascii", action="store_true", help="Force ASCII table borders")
    p.add_argument("--unicode", action="store_true", help="Force Unicode table borders")
    p.add_argument("--sort", choices=SORT_CHOICES, default="name", help="Sort service views by name, id, cpu, or memory")
    sub = p.add_subparsers(dest="command", required=False)

    l = sub.add_parser("list", help="List services tracked by skuld")
    l.add_argument("--sort", choices=SORT_CHOICES, default="name", help="Sort by name, id, cpu, or memory")
    l.set_defaults(func=list_services)

    ct = sub.add_parser("catalog", help="Show the current systemd discovery catalog")
    ct.add_argument(
        "--scope",
        choices=DISCOVERABLE_SCOPE_CHOICES,
        default="all",
        help="Filter catalog entries by scope: all, system, or user",
    )
    ct.set_defaults(func=catalog)

    tr = sub.add_parser("track", help="Track systemd services from the current catalog or by service name")
    tr.add_argument(
        "targets",
        nargs="+",
        help="Catalog ids or service names (example: 1 4 nginx sshd.service user:syncthing)",
    )
    tr.add_argument("--alias", help="Friendly name shown by skuld")
    tr.set_defaults(func=track)

    rn = sub.add_parser("rename", help="Change the display name of a tracked service")
    rn.add_argument("name", nargs="?")
    rn.add_argument("new_name")
    rn.add_argument("--name", dest="name_flag")
    rn.add_argument("--id", dest="id_flag", type=int)
    rn.set_defaults(func=rename)

    ut = sub.add_parser("untrack", help="Remove a service from the skuld registry without touching systemd")
    ut.add_argument("name", nargs="?")
    ut.add_argument("--name", dest="name_flag")
    ut.add_argument("--id", dest="id_flag", type=int)
    ut.set_defaults(func=untrack)

    e = sub.add_parser("exec", help="Execute a service immediately")
    e.add_argument("name", nargs="?")
    e.add_argument("--name", dest="name_flag")
    e.add_argument("--id", dest="id_flag", type=int)
    e.set_defaults(func=exec_now)

    s = sub.add_parser("start", help="Start one or more services")
    s.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    s.add_argument("--name", dest="name_flag")
    s.add_argument("--id", dest="id_flag", type=int)
    s.set_defaults(func=lambda a: start_stop(a, "start"))

    st = sub.add_parser("stop", help="Stop one or more services")
    st.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    st.add_argument("--name", dest="name_flag")
    st.add_argument("--id", dest="id_flag", type=int)
    st.set_defaults(func=lambda a: start_stop(a, "stop"))

    rs = sub.add_parser("restart", help="Restart one or more services")
    rs.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    rs.add_argument("--name", dest="name_flag")
    rs.add_argument("--id", dest="id_flag", type=int)
    rs.set_defaults(func=restart)

    ps = sub.add_parser("status", help="Service/timer status")
    ps.add_argument("name", nargs="?")
    ps.add_argument("--name", dest="name_flag")
    ps.add_argument("--id", dest="id_flag", type=int)
    ps.set_defaults(func=status)

    lg = sub.add_parser("logs", help="Show logs from journalctl")
    lg.add_argument("name", nargs="?")
    lg.add_argument("lines_pos", nargs="?", type=int)
    lg.add_argument("--name", dest="name_flag")
    lg.add_argument("--id", dest="id_flag", type=int)
    lg.add_argument("--lines", type=int, default=None)
    lg.add_argument("--follow", action="store_true", help="Follow logs in real time")
    lg.add_argument("--folow", dest="follow", action="store_true", help=argparse.SUPPRESS)
    lg.add_argument("--since", help="journalctl time filter (example: '1 hour ago')")
    lg.add_argument("--timer", action="store_true", help="Read .timer logs instead of .service")
    lg.add_argument("--output", default="short", help="journalctl output mode (e.g. short, short-iso, cat, json)")
    lg.add_argument("--plain", action="store_true", help="Shortcut for --output cat (message only)")
    lg.set_defaults(func=logs)

    stt = sub.add_parser("stats", help="Show execution/restart counters for a tracked service")
    stt.add_argument("name", nargs="?")
    stt.add_argument("--name", dest="name_flag")
    stt.add_argument("--id", dest="id_flag", type=int)
    stt.add_argument("--since", help="journalctl time filter (example: '24 hours ago')")
    stt.add_argument("--boot", action="store_true", help="Count entries from current boot only")
    stt.set_defaults(func=stats)

    dr = sub.add_parser("doctor", help="Check registry/systemd inconsistencies")
    dr.set_defaults(func=doctor)

    ds = sub.add_parser("describe", help="Show details for a tracked service")
    ds.add_argument("name", nargs="?")
    ds.add_argument("--name", dest="name_flag")
    ds.add_argument("--id", dest="id_flag", type=int)
    ds.set_defaults(func=describe)

    sy = sub.add_parser("sync", help="Backfill missing registry fields from systemd")
    sy.add_argument("name", nargs="?", help="Sync only one managed service")
    sy.add_argument("--name", dest="name_flag", help="Sync only one managed service")
    sy.add_argument("--id", dest="id_flag", type=int, help="Sync only one managed service by id")
    sy.set_defaults(func=sync)

    v = sub.add_parser("version", help="Show version")
    v.set_defaults(func=lambda _a: print(VERSION))

    sd = sub.add_parser("sudo", help="Helpers for one-off sudo usage")
    sd_sub = sd.add_subparsers(dest="sudo_command", required=True)

    sd_check = sd_sub.add_parser("check", help="Check whether sudo can run non-interactively")
    sd_check.set_defaults(func=sudo_check)

    sd_run = sd_sub.add_parser("run", help="Run one command through sudo")
    sd_run.add_argument("command", nargs=argparse.REMAINDER)
    sd_run.set_defaults(func=sudo_run_command)

    return p


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
