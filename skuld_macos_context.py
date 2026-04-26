from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import skuld_common as common
import skuld_config
import skuld_macos_catalog as macos_catalog
import skuld_macos_launchd as launchd
import skuld_macos_paths as macos_paths
import skuld_macos_processes as processes
import skuld_macos_registry as macos_registry
import skuld_macos_runtime as runtime
import skuld_macos_sync as macos_sync
import skuld_macos_targets as macos_targets
import skuld_sudo
import skuld_tables as tables
from skuld_macos_model import (
    DiscoverableService,
    ManagedService,
    normalize_service as normalize_model_service,
    validate_name,
)


SORT_CHOICES = ("id", "name", "cpu", "memory")


def default_skuld_home() -> Path:
    return Path(
        os.environ.get(
            "SKULD_HOME",
            Path.home() / "Library/Application Support/skuld",
        )
    )


@dataclass
class MacOSBackendContext:
    skuld_home: Path = field(default_factory=default_skuld_home)
    registry_file: Optional[Path] = None
    config_file: Optional[Path] = None
    runtime_stats_file: Optional[Path] = None
    default_env_file: Path = Path(".env")
    use_env_sudo: bool = True
    force_table_ascii: bool = False
    force_table_unicode: bool = False
    service_table_columns: Optional[Tuple[str, ...]] = None
    script_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    def __post_init__(self) -> None:
        if self.registry_file is None:
            self.registry_file = self.skuld_home / "services.json"
        if self.config_file is None:
            self.config_file = self.skuld_home / "config.json"
        if self.runtime_stats_file is None:
            self.runtime_stats_file = self.skuld_home / "runtime_stats.json"

    def configure_cli_globals(
        self,
        args: argparse.Namespace,
        parser: argparse.ArgumentParser,
    ) -> None:
        self.use_env_sudo = not args.no_env_sudo
        self.force_table_ascii = bool(args.ascii)
        self.force_table_unicode = bool(args.unicode)
        if self.force_table_ascii and self.force_table_unicode:
            parser.error("choose only one of --ascii or --unicode")
        try:
            config_value = None
            if getattr(args, "command", None) != "config":
                config_value = skuld_config.load_columns_text(self.config_file)
            self.service_table_columns = tables.resolve_service_table_columns(
                getattr(args, "columns", None),
                config_value=config_value,
                env_value=os.environ.get("SKULD_COLUMNS"),
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))

    def ensure_storage(self) -> None:
        macos_registry.ensure_storage(
            self.skuld_home,
            self.registry_file,
            self.runtime_stats_file,
        )

    def get_sudo_password(self) -> Optional[str]:
        return common.find_sudo_password(
            use_env_sudo=self.use_env_sudo,
            env_file_override=os.environ.get("SKULD_ENV_FILE"),
            default_env_file=self.default_env_file,
            script_dir=self.script_dir,
            state_home=self.skuld_home,
        )

    def normalize_service(self, item: Dict[str, object]) -> ManagedService:
        return normalize_model_service(
            item,
            log_dir_for_service=self.log_dir_for_service,
            service_label=macos_paths.service_label,
        )

    def load_registry(self, *, write_back: bool = False) -> List[ManagedService]:
        return macos_registry.load_registry(
            self.skuld_home,
            self.registry_file,
            self.runtime_stats_file,
            normalize_item=self.normalize_service,
            write_back=write_back,
        )

    def save_registry(self, services: List[ManagedService]) -> None:
        macos_registry.save_registry(
            self.skuld_home,
            self.registry_file,
            self.runtime_stats_file,
            services,
            normalize_item=self.normalize_service,
        )

    def upsert_registry(self, service: ManagedService) -> None:
        macos_registry.upsert_registry(
            self.skuld_home,
            self.registry_file,
            self.runtime_stats_file,
            service,
            normalize_item=self.normalize_service,
        )

    def remove_registry(self, name: str) -> None:
        macos_registry.remove_registry(
            self.skuld_home,
            self.registry_file,
            self.runtime_stats_file,
            name,
            normalize_item=self.normalize_service,
        )

    def get_managed(self, name: str) -> Optional[ManagedService]:
        return macos_registry.get_managed(name, load_registry=self.load_registry)

    def get_managed_by_display_name(
        self,
        display_name: str,
    ) -> Optional[ManagedService]:
        return macos_registry.get_managed_by_display_name(
            display_name,
            load_registry=self.load_registry,
        )

    def get_managed_by_id(self, service_id: int) -> Optional[ManagedService]:
        return macos_registry.get_managed_by_id(
            service_id,
            load_registry=self.load_registry,
        )

    def ensure_display_name_available(
        self,
        display_name: str,
        current_name: Optional[str] = None,
    ) -> None:
        macos_targets.ensure_display_name_available(
            display_name,
            current_name=current_name,
            validate_name=validate_name,
            load_registry=self.load_registry,
        )

    def prompt_display_name(self, target: str, suggested: str) -> str:
        if not sys.stdin.isatty():
            return suggested
        value = input(f"Display name for {target} [{suggested}]: ").strip()
        chosen = value or suggested
        validate_name(chosen)
        return chosen

    def resolve_name_arg(
        self,
        args: argparse.Namespace,
        required: bool = True,
    ) -> Optional[str]:
        return macos_targets.resolve_name_arg(args, required=required)

    def resolve_managed_from_token(self, token: str) -> Optional[ManagedService]:
        return macos_targets.resolve_managed_from_token(
            token,
            get_managed=self.get_managed,
            get_managed_by_display_name=self.get_managed_by_display_name,
            get_managed_by_id=self.get_managed_by_id,
        )

    def resolve_managed_arg(
        self,
        args: argparse.Namespace,
        required: bool = True,
    ) -> Optional[ManagedService]:
        return macos_targets.resolve_managed_arg(
            args,
            required=required,
            resolve_managed_from_token=self.resolve_managed_from_token,
            get_managed_by_id=self.get_managed_by_id,
        )

    def resolve_managed_many_arg(
        self,
        args: argparse.Namespace,
    ) -> List[ManagedService]:
        return macos_targets.resolve_managed_many_arg(
            args,
            resolve_managed_from_token=self.resolve_managed_from_token,
        )

    def resolve_discoverable_targets(
        self,
        tokens: List[str],
    ) -> List[DiscoverableService]:
        return macos_targets.resolve_discoverable_targets(
            tokens,
            discover_launchd_services=self.discover_launchd_services,
        )

    def supports_unicode_output(self) -> bool:
        return common.supports_unicode_output(
            force_ascii=self.force_table_ascii,
            force_unicode=self.force_table_unicode,
        )

    def colorize(self, text: str, color: str) -> str:
        return common.colorize(text, color, enabled=common.is_tty())

    def resolve_sort_arg(self, args: Optional[argparse.Namespace]) -> str:
        return common.resolve_sort_arg(args, SORT_CHOICES)

    def info(self, msg: str) -> None:
        print(f"[skuld] {msg}")

    def ok(self, msg: str) -> None:
        print(f"[ok] {msg}")

    def err(self, msg: str) -> None:
        print(f"[error] {msg}", file=sys.stderr)

    def run(
        self,
        cmd: List[str],
        check: bool = True,
        capture: bool = False,
        input_text: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        return common.run_command(
            cmd,
            check=check,
            capture=capture,
            input_text=input_text,
        )

    def run_sudo(
        self,
        cmd: List[str],
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        return common.run_sudo_command(
            cmd,
            sudo_password=self.get_sudo_password(),
            check=check,
            capture=capture,
        )

    def warn_env_sudo_usage(self) -> None:
        skuld_sudo.warn_env_sudo_usage(
            get_sudo_password=self.get_sudo_password,
            info=self.info,
        )

    def sudo_check(self, _args: argparse.Namespace) -> None:
        skuld_sudo.sudo_check(
            get_sudo_password=self.get_sudo_password,
            run=self.run,
            info=self.info,
            ok=self.ok,
        )

    def sudo_auth(self, _args: argparse.Namespace) -> None:
        skuld_sudo.sudo_auth(run=self.run, ok=self.ok)

    def sudo_forget(self, _args: argparse.Namespace) -> None:
        skuld_sudo.sudo_forget(run=self.run, ok=self.ok)

    def sudo_run_command(self, args: argparse.Namespace) -> None:
        skuld_sudo.sudo_run_command(
            args,
            get_sudo_password=self.get_sudo_password,
            run_sudo=self.run_sudo,
            info=self.info,
        )

    def config_show(self, _args: argparse.Namespace) -> None:
        columns = tables.parse_service_table_columns(
            skuld_config.load_columns_text(self.config_file)
        )
        for line in skuld_config.config_lines(
            self.config_file,
            columns,
        ):
            print(line)

    def config_columns(self, args: argparse.Namespace) -> None:
        columns = tables.parse_service_table_columns(args.columns)
        skuld_config.save_columns(self.config_file, columns)
        if columns is None:
            self.service_table_columns = None
            self.ok("Saved default table column layout.")
            return
        self.service_table_columns = columns
        self.ok(f"Saved table columns: {','.join(columns)}")

    def render_table(self, headers: List[str], rows: List[List[str]]) -> None:
        common.render_table(headers, rows, unicode_box=self.supports_unicode_output())

    def fit_service_table(
        self,
        rows: List[Dict[str, object]],
        max_width: Optional[int] = None,
    ) -> Tuple[List[str], List[List[str]]]:
        return tables.fit_service_table(
            rows,
            max_width=max_width,
            columns=self.service_table_columns,
        )

    def current_user_home(self) -> Path:
        return macos_paths.current_user_home()

    def launchd_label_for_service(self, service: ManagedService) -> str:
        return macos_paths.launchd_label_for_service(service)

    def plist_path_for_service(self, service: ManagedService) -> Path:
        return macos_paths.plist_path_for_service(
            service,
            user_home=self.current_user_home(),
        )

    def jobs_root_for_scope(self, scope: str) -> Path:
        return macos_paths.jobs_root_for_scope(scope, skuld_home=self.skuld_home)

    def logs_root_for_scope(self, scope: str) -> Path:
        return macos_paths.logs_root_for_scope(scope, skuld_home=self.skuld_home)

    def events_root_for_scope(self, scope: str) -> Path:
        return macos_paths.events_root_for_scope(scope, skuld_home=self.skuld_home)

    def log_dir_for_service(self, name: str, scope: str) -> Path:
        return macos_paths.log_dir_for_service(
            name,
            scope,
            skuld_home=self.skuld_home,
        )

    def event_file_for_service(self, name: str, scope: str) -> Path:
        return macos_paths.event_file_for_service(
            name,
            scope,
            skuld_home=self.skuld_home,
        )

    def wrapper_script_for_service(self, name: str, scope: str) -> Path:
        return macos_paths.wrapper_script_for_service(
            name,
            scope,
            skuld_home=self.skuld_home,
        )

    def discover_launchd_services(self) -> List[DiscoverableService]:
        return macos_catalog.discover_launchd_services(run=self.run)

    def render_discoverable_services_hint(self) -> None:
        macos_catalog.render_discoverable_services_hint(
            discover_launchd_services=self.discover_launchd_services,
        )

    def launchctl_print_service_raw(self, label: str) -> str:
        return launchd.print_service_raw(label)

    def extract_launchctl_value(self, text: str, key: str) -> str:
        return launchd.extract_value(text, key)

    def launchctl_cmd(
        self,
        scope: str,
        args: List[str],
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        return launchd.run_launchctl(
            scope,
            args,
            sudo_password=self.get_sudo_password(),
            check=check,
            capture=capture,
        )

    def domain_target(self, scope: str) -> str:
        return launchd.domain_target(scope)

    def service_target(self, service: ManagedService) -> str:
        return launchd.service_target(
            service.scope,
            self.launchd_label_for_service(service),
        )

    def service_loaded(self, service: ManagedService) -> bool:
        return launchd.service_loaded(
            service.scope,
            self.launchd_label_for_service(service),
            sudo_password=self.get_sudo_password(),
        )

    def launchctl_service_info(self, service: ManagedService) -> Dict[str, str]:
        return launchd.service_info(
            service.scope,
            self.launchd_label_for_service(service),
            sudo_password=self.get_sudo_password(),
        )

    def read_pid(self, service: ManagedService) -> int:
        return common.parse_int(self.launchctl_service_info(service).get("PID", "0"))

    def read_process_tree_pids(self, root_pid: int) -> List[int]:
        return processes.read_process_tree_pids(root_pid, self.run)

    def terminate_process_tree(
        self,
        root_pid: int,
        grace_seconds: float = 2.0,
    ) -> None:
        processes.terminate_process_tree(
            root_pid,
            self.read_process_tree_pids,
            grace_seconds=grace_seconds,
        )

    def read_event_stats(self, service: ManagedService) -> Dict[str, object]:
        return runtime.read_event_stats(
            self.event_file_for_service(service.name, service.scope),
            schedule=service.schedule,
            restart=service.restart,
        )

    def update_runtime_stats(
        self,
        service: ManagedService,
    ) -> Dict[str, Dict[str, object]]:
        return runtime.update_runtime_stats(
            self.runtime_stats_file,
            self.ensure_storage,
            service.name,
            self.read_event_stats(service),
        )

    def read_service_events(self, service: ManagedService) -> List[Dict[str, object]]:
        return runtime.read_service_events(
            self.event_file_for_service(service.name, service.scope)
        )

    def read_recent_run_root_pids(
        self,
        service: ManagedService,
        limit: int = 3,
    ) -> List[int]:
        return runtime.read_recent_run_root_pids(
            self.read_service_events(service),
            limit=limit,
        )

    def format_restarts_exec(
        self,
        service: ManagedService,
        runtime_stats: Dict[str, Dict[str, object]],
    ) -> str:
        item = runtime_stats.get(service.name)
        if not item:
            return "-"
        return f"{item.get('restarts', 0)}/{item.get('executions', 0)}"

    def bootstrap_service(self, service: ManagedService) -> None:
        proc = launchd.bootstrap_service(
            service.scope,
            self.launchd_label_for_service(service),
            self.plist_path_for_service(service),
            sudo_password=self.get_sudo_password(),
        )
        if proc.returncode != 0:
            details = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Failed to bootstrap {service.name}. {details}".strip())

    def bootout_service(self, service: ManagedService) -> None:
        launchd.bootout_service(
            service.scope,
            self.launchd_label_for_service(service),
            sudo_password=self.get_sudo_password(),
        )

    def kickstart_service(
        self,
        service: ManagedService,
        kill_existing: bool = False,
    ) -> subprocess.CompletedProcess:
        return launchd.kickstart_service(
            service.scope,
            self.launchd_label_for_service(service),
            sudo_password=self.get_sudo_password(),
            kill_existing=kill_existing,
        )

    def sync_registry_from_launchd(self, name: Optional[str] = None) -> int:
        return macos_sync.sync_registry_from_launchd(
            name,
            load_registry=self.load_registry,
            save_registry=self.save_registry,
            plist_path_for_service=self.plist_path_for_service,
        )

    def tail_file(self, path: Path, lines: int, follow: bool) -> None:
        runtime.tail_file(self.run, path, lines, follow)

    def log_paths_for_service(
        self,
        service: ManagedService,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        return runtime.log_paths_for_service(
            managed_by_skuld=service.managed_by_skuld,
            log_dir=service.log_dir,
            plist_path=self.plist_path_for_service(service),
        )

    def read_cpu_memory(self, pid: int) -> Dict[str, str]:
        return processes.read_cpu_memory(pid, self.run)

    def read_ports(self, pid: int) -> str:
        return processes.read_ports(pid, self.read_process_tree_pids, self.run)

    def read_host_overview(self) -> Dict[str, str]:
        return processes.read_host_overview(self.run)

    def render_host_panel(self) -> None:
        tables.render_host_panel(self.read_host_overview(), self.render_table)
