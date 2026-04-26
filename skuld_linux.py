#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import skuld_common as common
import skuld_cli
import skuld_linux_actions as linux_actions
import skuld_linux_catalog as linux_catalog
import skuld_linux_commands as linux_commands
import skuld_linux_parser as linux_parser
import skuld_linux_registry as linux_registry
from skuld_linux_model import (
    DiscoverableService,
    ManagedService,
    format_scoped_name,
    managed_service_key,
    managed_sort_key,
    normalize_target_token,
    suggest_display_name,
    validate_name,
)
import skuld_linux_runtime as linux_runtime
import skuld_linux_stats as linux_stats
import skuld_linux_systemd as systemd
import skuld_linux_sync as linux_sync
import skuld_linux_targets as linux_targets
import skuld_linux_timers as timers
import skuld_linux_view as linux_view
import skuld_sudo
import skuld_tables as tables

VERSION = "0.3.0"
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
    linux_registry.ensure_storage(SKULD_HOME, REGISTRY_FILE)


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


def load_registry(*, write_back: bool = False) -> List[ManagedService]:
    return linux_registry.load_registry(
        SKULD_HOME,
        REGISTRY_FILE,
        write_back=write_back,
    )


def save_registry(services: List[ManagedService]) -> None:
    linux_registry.save_registry(SKULD_HOME, REGISTRY_FILE, services)


def upsert_registry(service: ManagedService) -> None:
    linux_registry.upsert_registry(SKULD_HOME, REGISTRY_FILE, service)


def remove_registry(name: str, scope: str) -> None:
    linux_registry.remove_registry(SKULD_HOME, REGISTRY_FILE, name, scope)


def find_managed_by_name(name: str) -> List[ManagedService]:
    return linux_registry.find_managed_by_name(name, load_registry=load_registry)


def get_managed(name: str, scope: Optional[str] = None) -> Optional[ManagedService]:
    return linux_registry.get_managed(
        name,
        scope=scope,
        load_registry=load_registry,
    )


def get_managed_by_display_name(display_name: str) -> Optional[ManagedService]:
    return linux_registry.get_managed_by_display_name(
        display_name,
        load_registry=load_registry,
    )


def get_managed_by_id(service_id: int) -> Optional[ManagedService]:
    return linux_registry.get_managed_by_id(
        service_id,
        load_registry=load_registry,
    )


def require_managed(name: str, scope: Optional[str] = None) -> ManagedService:
    return linux_registry.require_managed(
        name,
        scope=scope,
        get_managed=get_managed,
    )


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


def ensure_display_name_available(display_name: str, current_id: Optional[int] = None) -> None:
    linux_targets.ensure_display_name_available(
        display_name,
        current_id=current_id,
        validate_name=validate_name,
        load_registry=load_registry,
    )


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
    return common.resolve_lines_arg(args, default=default)


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
    skuld_sudo.warn_env_sudo_usage(get_sudo_password=get_sudo_password, info=info)


def sudo_check(_args: argparse.Namespace) -> None:
    skuld_sudo.sudo_check(
        get_sudo_password=get_sudo_password,
        run=run,
        info=info,
        ok=ok,
    )


def sudo_run_command(args: argparse.Namespace) -> None:
    skuld_sudo.sudo_run_command(
        args,
        get_sudo_password=get_sudo_password,
        run_sudo=run_sudo,
        info=info,
    )


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
    return timers.timer_triggers_for_display(
        svc,
        max_width=max_width,
        unit_exists=unit_exists,
        systemctl_cat=systemctl_cat,
        schedule_for_display=schedule_for_display,
        clip_text=clip_text,
    )


def read_timer_schedule(name: str, scope: str = "system") -> str:
    return timers.read_timer_schedule(
        name,
        scope=scope,
        systemctl_show=systemctl_show,
        systemctl_cat=systemctl_cat,
    )


def read_timer_persistent(name: str, scope: str = "system", default: bool = True) -> bool:
    return timers.read_timer_persistent(
        name,
        scope=scope,
        default=default,
        unit_exists=unit_exists,
        systemctl_show=systemctl_show,
        systemctl_cat=systemctl_cat,
        parse_bool=parse_bool,
    )


def read_timer_next_run(name: str, scope: str = "system") -> str:
    return timers.read_timer_next_run(
        name,
        scope=scope,
        systemctl_show=systemctl_show,
    )


def read_timer_last_run(name: str, scope: str = "system") -> str:
    return timers.read_timer_last_run(
        name,
        scope=scope,
        systemctl_show=systemctl_show,
    )


def schedule_for_display(svc: ManagedService) -> str:
    return timers.schedule_for_display(svc, read_timer_schedule=read_timer_schedule)


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
    return linux_catalog.list_discoverable_services_for_scope(
        scope,
        run=run,
        systemctl_command=systemctl_command,
        systemd_scope_env=systemd_scope_env,
    )


def normalize_discoverable_scope(value: Optional[str]) -> str:
    return linux_catalog.normalize_discoverable_scope(value)


def list_discoverable_services(scope_filter: str = "all") -> List[DiscoverableService]:
    return linux_catalog.list_discoverable_services(
        scope_filter,
        require_systemctl=require_systemctl,
        list_scope=list_discoverable_services_for_scope,
    )


def render_discoverable_services_hint(empty_registry_note: bool = True, scope_filter: str = "all") -> None:
    linux_catalog.render_discoverable_services_hint(
        empty_registry_note=empty_registry_note,
        scope_filter=scope_filter,
        list_discoverable_services=list_discoverable_services,
    )


def resolve_discoverable_target_by_name(name: str, scope: Optional[str], entries: List[DiscoverableService]) -> DiscoverableService:
    return linux_catalog.resolve_discoverable_target_by_name(
        name,
        scope,
        entries,
        unit_exists=unit_exists,
    )


def resolve_discoverable_targets(targets: List[str]) -> List[DiscoverableService]:
    return linux_catalog.resolve_discoverable_targets(
        targets,
        list_discoverable_services=list_discoverable_services,
        normalize_target_token=normalize_target_token,
        unit_exists=unit_exists,
    )


def parse_unit_directives(unit_text: str) -> Dict[str, str]:
    return linux_catalog.parse_unit_directives(unit_text)


def parse_bool(value: str, default: bool = True) -> bool:
    return common.parse_bool(value, default=default)


def _render_services_table(compact: bool, sort_by: str = "name") -> None:
    linux_view.render_services_table(
        compact=compact,
        sort_by=sort_by,
        require_systemctl=require_systemctl,
        load_registry=load_registry,
        render_discoverable_services_hint=render_discoverable_services_hint,
        read_gpu_memory_by_pid=read_gpu_memory_by_pid,
        render_host_panel=render_host_panel,
        unit_exists=unit_exists,
        unit_active=unit_active,
        display_unit_state=display_unit_state,
        colorize=colorize,
        read_unit_usage=read_unit_usage,
        timer_triggers_for_display=timer_triggers_for_display,
        read_unit_ports=read_unit_ports,
        sort_service_rows=tables.sort_service_rows,
        fit_service_table=fit_service_table,
        render_table=render_table,
    )


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
    linux_catalog.track_services(
        list(args.targets or []),
        alias=args.alias,
        resolve_discoverable_targets=resolve_discoverable_targets,
        suggest_display_name=suggest_display_name,
        prompt_display_name=prompt_display_name,
        ensure_display_name_available=ensure_display_name_available,
        get_managed=get_managed,
        systemctl_cat=systemctl_cat,
        systemctl_show=systemctl_show,
        unit_exists=unit_exists,
        parse_bool=parse_bool,
        service_factory=ManagedService,
        upsert_registry=upsert_registry,
        ok=ok,
    )


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
    return linux_parser.build_parser(
        sort_choices=SORT_CHOICES,
        discoverable_scope_choices=DISCOVERABLE_SCOPE_CHOICES,
        version=VERSION,
        list_services=list_services,
        catalog=catalog,
        track=track,
        rename=rename,
        untrack=untrack,
        exec_now=exec_now,
        start_stop=start_stop,
        restart=restart,
        status=status,
        logs=logs,
        stats=stats,
        doctor=doctor,
        describe=describe,
        sync=sync,
        sudo_check=sudo_check,
        sudo_run_command=sudo_run_command,
    )


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
