#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import skuld_common as common
import skuld_cli
import skuld_macos_actions as macos_actions
import skuld_macos_catalog as macos_catalog
import skuld_macos_commands as macos_commands
import skuld_macos_launchd as launchd
import skuld_macos_paths as macos_paths
import skuld_macos_parser as macos_parser
import skuld_macos_registry as macos_registry
from skuld_macos_model import (
    DiscoverableService,
    ManagedService,
    normalize_service as normalize_model_service,
    resolve_scope,
    suggest_display_name,
    validate_name,
)
import skuld_macos_processes as processes
import skuld_macos_runtime as runtime
import skuld_macos_schedules as schedules
import skuld_macos_sync as macos_sync
import skuld_macos_targets as macos_targets
import skuld_macos_view as macos_view
import skuld_sudo
import skuld_tables as tables

VERSION = "0.3.0"
DEFAULT_ENV_FILE = Path(".env")
SKULD_HOME = Path(os.environ.get("SKULD_HOME", Path.home() / "Library/Application Support/skuld"))
REGISTRY_FILE = SKULD_HOME / "services.json"
RUNTIME_STATS_FILE = SKULD_HOME / "runtime_stats.json"
USE_ENV_SUDO = True
FORCE_TABLE_ASCII = False
FORCE_TABLE_UNICODE = False
SORT_CHOICES = ("id", "name", "cpu", "memory")


def ensure_storage() -> None:
    macos_registry.ensure_storage(SKULD_HOME, REGISTRY_FILE, RUNTIME_STATS_FILE)


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


def parse_int(value: str) -> int:
    return common.parse_int(value)


def ensure_display_name_available(display_name: str, current_name: Optional[str] = None) -> None:
    macos_targets.ensure_display_name_available(
        display_name,
        current_name=current_name,
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
    return macos_targets.resolve_name_arg(args, required=required)


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


def format_bytes_from_kib(kib: int) -> str:
    return processes.format_bytes_from_kib(kib)


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
    return tables.shrink_service_table_widths(columns, widths, max_width)


def fit_service_table(rows: List[Dict[str, object]], max_width: Optional[int] = None) -> Tuple[List[str], List[List[str]]]:
    return tables.fit_service_table(rows, max_width=max_width)


def current_user_home() -> Path:
    return macos_paths.current_user_home()


def service_label(name: str) -> str:
    return macos_paths.service_label(name)


def launchd_label_for_service(service: ManagedService) -> str:
    return macos_paths.launchd_label_for_service(service)


def plist_path_for_service(service: ManagedService) -> Path:
    return macos_paths.plist_path_for_service(service, user_home=current_user_home())


def jobs_root_for_scope(scope: str) -> Path:
    return macos_paths.jobs_root_for_scope(scope, skuld_home=SKULD_HOME)


def logs_root_for_scope(scope: str) -> Path:
    return macos_paths.logs_root_for_scope(scope, skuld_home=SKULD_HOME)


def events_root_for_scope(scope: str) -> Path:
    return macos_paths.events_root_for_scope(scope, skuld_home=SKULD_HOME)


def log_dir_for_service(name: str, scope: str) -> Path:
    return macos_paths.log_dir_for_service(name, scope, skuld_home=SKULD_HOME)


def event_file_for_service(name: str, scope: str) -> Path:
    return macos_paths.event_file_for_service(name, scope, skuld_home=SKULD_HOME)


def wrapper_script_for_service(name: str, scope: str) -> Path:
    return macos_paths.wrapper_script_for_service(name, scope, skuld_home=SKULD_HOME)


def normalize_service(item: Dict[str, object]) -> ManagedService:
    return normalize_model_service(
        item,
        log_dir_for_service=log_dir_for_service,
        service_label=service_label,
    )


def load_registry(*, write_back: bool = False) -> List[ManagedService]:
    return macos_registry.load_registry(
        SKULD_HOME,
        REGISTRY_FILE,
        RUNTIME_STATS_FILE,
        normalize_item=normalize_service,
        write_back=write_back,
    )


def save_registry(services: List[ManagedService]) -> None:
    macos_registry.save_registry(
        SKULD_HOME,
        REGISTRY_FILE,
        RUNTIME_STATS_FILE,
        services,
        normalize_item=normalize_service,
    )


def upsert_registry(service: ManagedService) -> None:
    macos_registry.upsert_registry(
        SKULD_HOME,
        REGISTRY_FILE,
        RUNTIME_STATS_FILE,
        service,
        normalize_item=normalize_service,
    )


def remove_registry(name: str) -> None:
    macos_registry.remove_registry(
        SKULD_HOME,
        REGISTRY_FILE,
        RUNTIME_STATS_FILE,
        name,
        normalize_item=normalize_service,
    )


def get_managed(name: str) -> Optional[ManagedService]:
    return macos_registry.get_managed(name, load_registry=load_registry)


def get_managed_by_display_name(display_name: str) -> Optional[ManagedService]:
    return macos_registry.get_managed_by_display_name(
        display_name,
        load_registry=load_registry,
    )


def get_managed_by_id(service_id: int) -> Optional[ManagedService]:
    return macos_registry.get_managed_by_id(
        service_id,
        load_registry=load_registry,
    )


def resolve_managed_from_token(token: str) -> Optional[ManagedService]:
    return macos_targets.resolve_managed_from_token(
        token,
        get_managed=get_managed,
        get_managed_by_display_name=get_managed_by_display_name,
        get_managed_by_id=get_managed_by_id,
    )


def resolve_managed_arg(args: argparse.Namespace, required: bool = True) -> Optional[ManagedService]:
    return macos_targets.resolve_managed_arg(
        args,
        required=required,
        resolve_managed_from_token=resolve_managed_from_token,
        get_managed_by_id=get_managed_by_id,
    )


def resolve_managed_many_arg(args: argparse.Namespace) -> List[ManagedService]:
    return macos_targets.resolve_managed_many_arg(
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


def discover_launchd_services() -> List[DiscoverableService]:
    return macos_catalog.discover_launchd_services(run=run)


def resolve_discoverable_targets(tokens: List[str]) -> List[DiscoverableService]:
    return macos_targets.resolve_discoverable_targets(
        tokens,
        discover_launchd_services=discover_launchd_services,
    )


def launchctl_print_service_raw(label: str) -> str:
    return launchd.print_service_raw(label)


def extract_launchctl_value(text: str, key: str) -> str:
    return launchd.extract_value(text, key)


def render_discoverable_services_hint() -> None:
    macos_catalog.render_discoverable_services_hint(
        discover_launchd_services=discover_launchd_services,
    )


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
    return processes.read_process_tree_pids(root_pid, run)


def terminate_process_tree(root_pid: int, grace_seconds: float = 2.0) -> None:
    processes.terminate_process_tree(root_pid, read_process_tree_pids, grace_seconds=grace_seconds)


def restart_policy_allows_restart(value: str) -> bool:
    return runtime.restart_policy_allows_restart(value)


def format_event_timestamp(value: str) -> str:
    return runtime.format_event_timestamp(value)


def read_event_stats(service: ManagedService) -> Dict[str, object]:
    return runtime.read_event_stats(
        event_file_for_service(service.name, service.scope),
        schedule=service.schedule,
        restart=service.restart,
    )


def update_runtime_stats(service: ManagedService) -> Dict[str, Dict[str, object]]:
    return runtime.update_runtime_stats(
        RUNTIME_STATS_FILE,
        ensure_storage,
        service.name,
        read_event_stats(service),
    )


def read_service_events(service: ManagedService) -> List[Dict[str, object]]:
    return runtime.read_service_events(event_file_for_service(service.name, service.scope))


def read_recent_run_root_pids(service: ManagedService, limit: int = 3) -> List[int]:
    return runtime.read_recent_run_root_pids(read_service_events(service), limit=limit)


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
    return macos_sync.sync_registry_from_launchd(
        name,
        load_registry=load_registry,
        save_registry=save_registry,
        plist_path_for_service=plist_path_for_service,
    )


def track(args: argparse.Namespace) -> None:
    macos_catalog.track_services(
        list(args.targets or []),
        alias=args.alias,
        resolve_discoverable_targets=resolve_discoverable_targets,
        suggest_display_name=suggest_display_name,
        prompt_display_name=prompt_display_name,
        ensure_display_name_available=ensure_display_name_available,
        get_managed=get_managed,
        launchctl_print_service_raw=launchctl_print_service_raw,
        extract_launchctl_value=extract_launchctl_value,
        service_factory=ManagedService,
        upsert_registry=upsert_registry,
        ok=ok,
    )

def start_stop(args: argparse.Namespace, action: str) -> None:
    macos_actions.apply_lifecycle_action_to_services(
        resolve_managed_many_arg(args),
        action,
        bootstrap_service=bootstrap_service,
        bootout_service=bootout_service,
        kickstart_service=kickstart_service,
        read_pid=read_pid,
        read_recent_run_root_pids=read_recent_run_root_pids,
        terminate_process_tree=terminate_process_tree,
        ok=ok,
    )


def restart(args: argparse.Namespace) -> None:
    start_stop(args, "restart")


def exec_now(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    macos_actions.execute_now(
        service,
        bootstrap_service=bootstrap_service,
        kickstart_service=kickstart_service,
        ok=ok,
    )


def status(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    macos_commands.show_status(
        service,
        launchd_label_for_service=launchd_label_for_service,
        domain_target=domain_target,
        launchctl_service_info=launchctl_service_info,
        plist_path_for_service=plist_path_for_service,
    )


def tail_file(path: Path, lines: int, follow: bool) -> None:
    runtime.tail_file(run, path, lines, follow)


def log_paths_for_service(service: ManagedService) -> Tuple[Optional[Path], Optional[Path]]:
    return runtime.log_paths_for_service(
        managed_by_skuld=service.managed_by_skuld,
        log_dir=service.log_dir,
        plist_path=plist_path_for_service(service),
    )


def logs(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    lines = resolve_lines_arg(args, default=100)
    macos_commands.show_logs(
        service,
        since=args.since,
        timer=args.timer,
        follow=args.follow,
        lines=lines,
        log_paths_for_service=log_paths_for_service,
        tail_file=tail_file,
        info=info,
    )


def read_cpu_memory(pid: int) -> Dict[str, str]:
    return processes.read_cpu_memory(pid, run)


def read_ports(pid: int) -> str:
    return processes.read_ports(pid, read_process_tree_pids, run)


def parse_vm_stat_count(value: str) -> int:
    return processes.parse_vm_stat_count(value)


def read_host_overview() -> Dict[str, str]:
    return processes.read_host_overview(run)


def render_host_panel() -> None:
    tables.render_host_panel(read_host_overview(), render_table)


def _render_services_table(compact: bool, sort_by: str = "name") -> None:
    macos_view.render_services_table(
        compact=compact,
        sort_by=sort_by,
        load_registry=load_registry,
        render_discoverable_services_hint=render_discoverable_services_hint,
        render_host_panel=render_host_panel,
        read_event_stats=read_event_stats,
        read_pid=read_pid,
        read_cpu_memory=read_cpu_memory,
        service_loaded=service_loaded,
        colorize=colorize,
        humanize_schedule_for_display=schedules.humanize_schedule_for_display,
        read_ports=read_ports,
        sort_service_rows=tables.sort_service_rows,
        fit_service_table=fit_service_table,
        render_table=render_table,
    )


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
    macos_commands.show_stats(service, update_runtime_stats=update_runtime_stats)

def doctor(_args: argparse.Namespace) -> None:
    services = load_registry()
    if not services:
        render_discoverable_services_hint()
        return
    macos_commands.doctor_services(
        services,
        plist_path_for_service=plist_path_for_service,
        wrapper_script_for_service=wrapper_script_for_service,
        service_loaded=service_loaded,
        ok=ok,
        err=err,
    )

def rename(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    macos_commands.rename_service(
        service,
        args.new_name,
        ensure_display_name_available=ensure_display_name_available,
        service_factory=ManagedService,
        upsert_registry=upsert_registry,
        info=info,
        ok=ok,
    )


def untrack(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    macos_commands.untrack_service(service, remove_registry=remove_registry, ok=ok)


def describe(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args)
    if not service:
        raise RuntimeError("Service target is required.")
    macos_commands.describe_service(
        service,
        launchctl_service_info=launchctl_service_info,
        read_event_stats=read_event_stats,
        compute_next_run=schedules.compute_next_run,
        plist_path_for_service=plist_path_for_service,
    )


def sync(args: argparse.Namespace) -> None:
    service = resolve_managed_arg(args, required=False)
    name = service.name if service else None
    changed = sync_registry_from_launchd(name)
    if changed == 0:
        ok("Registry is already up to date.")
    else:
        ok(f"Registry updated for {changed} service(s).")

def build_parser() -> argparse.ArgumentParser:
    return macos_parser.build_parser(
        sort_choices=SORT_CHOICES,
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
