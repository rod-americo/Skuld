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
import skuld_linux_catalog as linux_catalog
import skuld_linux_registry as linux_registry
import skuld_linux_runtime as linux_runtime
import skuld_linux_stats as linux_stats
import skuld_linux_sync as linux_sync
import skuld_linux_systemd as systemd
import skuld_linux_targets as linux_targets
import skuld_linux_timers as timers
import skuld_sudo
import skuld_tables as tables
from skuld_linux_model import (
    ManagedService,
    format_scoped_name,
    managed_service_key,
    managed_sort_key,
    normalize_target_token,
    validate_name,
)


SORT_CHOICES = ("id", "name", "cpu", "memory")


def default_skuld_home() -> Path:
    return Path(os.environ.get("SKULD_HOME", Path.home() / ".local/share/skuld"))


def default_runtime_stats_file() -> Path:
    return Path(
        os.environ.get("SKULD_RUNTIME_STATS_FILE", "/var/lib/skuld/journal_stats.json")
    )


@dataclass
class LinuxBackendContext:
    skuld_home: Path = field(default_factory=default_skuld_home)
    registry_file: Optional[Path] = None
    config_file: Optional[Path] = None
    runtime_stats_file: Path = field(default_factory=default_runtime_stats_file)
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
            command = getattr(args, "command", None)
            cli_columns = None if command == "config" else getattr(args, "columns", None)
            if cli_columns == tables.SERVICE_TABLE_COLUMN_CATALOG_REQUEST:
                self.service_table_columns = None
                return
            config_value = None
            if command != "config":
                config_value = skuld_config.load_columns_text(self.config_file)
            self.service_table_columns = tables.resolve_service_table_columns(
                cli_columns,
                config_value=config_value,
                env_value=os.environ.get("SKULD_COLUMNS"),
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))

    def ensure_storage(self) -> None:
        linux_registry.ensure_storage(self.skuld_home, self.registry_file)

    def get_sudo_password(self) -> Optional[str]:
        return common.find_sudo_password(
            use_env_sudo=self.use_env_sudo,
            env_file_override=os.environ.get("SKULD_ENV_FILE"),
            default_env_file=self.default_env_file,
            script_dir=self.script_dir,
            state_home=self.skuld_home,
        )

    def load_registry(self, *, write_back: bool = False) -> List[ManagedService]:
        return linux_registry.load_registry(
            self.skuld_home,
            self.registry_file,
            write_back=write_back,
        )

    def save_registry(self, services: List[ManagedService]) -> None:
        linux_registry.save_registry(self.skuld_home, self.registry_file, services)

    def upsert_registry(self, service: ManagedService) -> None:
        linux_registry.upsert_registry(self.skuld_home, self.registry_file, service)

    def remove_registry(self, name: str, scope: str) -> None:
        linux_registry.remove_registry(self.skuld_home, self.registry_file, name, scope)

    def find_managed_by_name(self, name: str) -> List[ManagedService]:
        return linux_registry.find_managed_by_name(name, load_registry=self.load_registry)

    def get_managed(
        self,
        name: str,
        scope: Optional[str] = None,
    ) -> Optional[ManagedService]:
        return linux_registry.get_managed(
            name,
            scope=scope,
            load_registry=self.load_registry,
        )

    def get_managed_by_display_name(
        self,
        display_name: str,
    ) -> Optional[ManagedService]:
        return linux_registry.get_managed_by_display_name(
            display_name,
            load_registry=self.load_registry,
        )

    def get_managed_by_id(self, service_id: int) -> Optional[ManagedService]:
        return linux_registry.get_managed_by_id(
            service_id,
            load_registry=self.load_registry,
        )

    def require_managed(
        self,
        name: str,
        scope: Optional[str] = None,
    ) -> ManagedService:
        return linux_registry.require_managed(
            name,
            scope=scope,
            get_managed=self.get_managed,
        )

    def err(self, msg: str) -> None:
        print(f"[error] {msg}", file=sys.stderr)

    def info(self, msg: str) -> None:
        print(f"[skuld] {msg}")

    def ok(self, msg: str) -> None:
        print(f"[ok] {msg}")

    def supports_unicode_output(self) -> bool:
        return common.supports_unicode_output(
            force_ascii=self.force_table_ascii,
            force_unicode=self.force_table_unicode,
        )

    def colorize(self, text: str, color: str) -> str:
        return common.colorize(text, color, enabled=common.is_tty())

    def resolve_sort_arg(self, args: Optional[argparse.Namespace]) -> str:
        return common.resolve_sort_arg(args, SORT_CHOICES)

    def ensure_display_name_available(
        self,
        display_name: str,
        current_id: Optional[int] = None,
    ) -> None:
        linux_targets.ensure_display_name_available(
            display_name,
            current_id=current_id,
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
        return linux_targets.resolve_name_arg(args, required=required)

    def resolve_managed_from_token(self, token: str) -> Optional[ManagedService]:
        return linux_targets.resolve_managed_from_token(
            token,
            get_managed_by_display_name=self.get_managed_by_display_name,
            get_managed_by_id=self.get_managed_by_id,
            normalize_target_token=normalize_target_token,
            get_managed=self.get_managed,
            find_managed_by_name=self.find_managed_by_name,
            format_scoped_name=format_scoped_name,
            managed_sort_key=managed_sort_key,
        )

    def resolve_managed_arg(
        self,
        args: argparse.Namespace,
        required: bool = True,
    ) -> Optional[ManagedService]:
        return linux_targets.resolve_managed_arg(
            args,
            required=required,
            resolve_managed_from_token=self.resolve_managed_from_token,
            get_managed_by_id=self.get_managed_by_id,
        )

    def resolve_managed_many_arg(
        self,
        args: argparse.Namespace,
    ) -> List[ManagedService]:
        return linux_targets.resolve_managed_many_arg(
            args,
            resolve_managed_from_token=self.resolve_managed_from_token,
        )

    def run(
        self,
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

    def show_columns_catalog(self) -> None:
        columns = tables.parse_service_table_columns(
            skuld_config.load_columns_text(self.config_file)
        )
        for line in tables.service_table_column_catalog_lines(columns):
            print(line)

    def config_columns(self, args: argparse.Namespace) -> None:
        if not args.columns:
            self.show_columns_catalog()
            return
        columns = tables.parse_service_table_column_tokens(args.columns)
        skuld_config.save_columns(self.config_file, columns)
        if columns is None:
            self.service_table_columns = None
            self.ok("Saved default table column layout.")
            return
        self.service_table_columns = columns
        self.ok(f"Saved table columns: {','.join(columns)}")

    def require_systemctl(self) -> None:
        systemd.require_systemctl()

    def systemd_scope_env(self, scope: str) -> Optional[Dict[str, str]]:
        return systemd.scope_env(scope)

    def systemctl_command(self, scope: str, args: List[str]) -> List[str]:
        return systemd.systemctl_command(scope, args)

    def journalctl_command(self, scope: str, args: List[str]) -> List[str]:
        return systemd.journalctl_command(scope, args)

    def run_systemctl_action(
        self,
        scope: str,
        args: List[str],
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        return systemd.run_systemctl_action(
            scope,
            args,
            sudo_password=self.get_sudo_password(),
            check=check,
            capture=capture,
        )

    def unit_exists(self, unit: str, scope: str = "system") -> bool:
        return systemd.unit_exists(unit, scope=scope)

    def unit_active(self, unit: str, scope: str = "system") -> str:
        return systemd.unit_active(unit, scope=scope)

    def display_unit_state(self, status: str) -> str:
        if status == "activating":
            return "running"
        return status

    def systemctl_show(
        self,
        unit: str,
        props: List[str],
        scope: str = "system",
    ) -> Dict[str, str]:
        return systemd.systemctl_show(unit, props, scope=scope)

    def systemctl_cat(self, unit: str, scope: str = "system") -> str:
        return systemd.systemctl_cat(unit, scope=scope)

    def read_host_overview(self) -> Dict[str, str]:
        return linux_stats.read_host_overview()

    def read_gpu_memory_by_pid(self) -> Optional[Dict[int, int]]:
        return linux_stats.read_gpu_memory_by_pid(self.run)

    def read_unit_usage(
        self,
        service_unit: str,
        scope: str = "system",
        gpu_memory_by_pid: Optional[Dict[int, int]] = None,
    ) -> Dict[str, str]:
        return linux_stats.read_unit_usage(
            self.unit_exists,
            self.systemctl_show,
            service_unit,
            scope=scope,
            gpu_memory_by_pid=gpu_memory_by_pid,
        )

    def read_unit_pids(self, service_unit: str, scope: str = "system") -> List[int]:
        return linux_stats.read_unit_pids(
            self.unit_exists,
            self.systemctl_show,
            service_unit,
            scope=scope,
        )

    def read_unit_ports(self, service_unit: str, scope: str = "system") -> str:
        return linux_stats.read_unit_ports(
            self.read_unit_pids,
            self.run,
            self.run_sudo,
            service_unit,
            scope=scope,
        )

    def render_table(self, headers: List[str], rows: List[List[str]]) -> None:
        common.render_table(headers, rows, unicode_box=self.supports_unicode_output())

    def fit_service_table(
        self,
        rows: List[Dict[str, object]],
        max_width: Optional[int] = None,
    ) -> tuple[List[str], List[List[str]]]:
        return tables.fit_service_table(
            rows,
            max_width=max_width,
            columns=self.service_table_columns,
        )

    def render_host_panel(self) -> None:
        tables.render_host_panel(self.read_host_overview(), self.render_table)

    def load_runtime_stats(self) -> Dict[str, Dict[str, int]]:
        return linux_runtime.load_runtime_stats(self.runtime_stats_file)

    def journal_permission_hint(self, stderr_text: str) -> bool:
        return linux_runtime.journal_permission_hint(stderr_text)

    def format_restarts_exec(
        self,
        name: str,
        runtime_stats: Dict[str, Dict[str, int]],
    ) -> str:
        return linux_runtime.format_restarts_exec(name, runtime_stats)

    def count_unit_starts(
        self,
        unit: str,
        scope: str = "system",
        since: Optional[str] = None,
        boot: bool = False,
    ) -> int:
        return linux_runtime.count_unit_starts(
            unit=unit,
            scope=scope,
            systemd_scope_env=self.systemd_scope_env,
            journalctl_command=self.journalctl_command,
            run_cmd=self.run,
            run_sudo_cmd=self.run_sudo,
            since=since,
            boot=boot,
        )

    def read_restart_count(self, name: str, scope: str = "system") -> str:
        return linux_runtime.read_restart_count(
            name=name,
            scope=scope,
            unit_exists=self.unit_exists,
            systemctl_show=self.systemctl_show,
        )

    def timer_triggers_for_display(
        self,
        service: ManagedService,
        max_width: int = 48,
    ) -> str:
        return timers.timer_triggers_for_display(
            service,
            max_width=max_width,
            unit_exists=self.unit_exists,
            systemctl_cat=self.systemctl_cat,
            schedule_for_display=self.schedule_for_display,
            clip_text=common.clip_text,
        )

    def read_timer_schedule(self, name: str, scope: str = "system") -> str:
        return timers.read_timer_schedule(
            name,
            scope=scope,
            systemctl_show=self.systemctl_show,
            systemctl_cat=self.systemctl_cat,
        )

    def read_timer_persistent(
        self,
        name: str,
        scope: str = "system",
        default: bool = True,
    ) -> bool:
        return timers.read_timer_persistent(
            name,
            scope=scope,
            default=default,
            unit_exists=self.unit_exists,
            systemctl_show=self.systemctl_show,
            systemctl_cat=self.systemctl_cat,
            parse_bool=common.parse_bool,
        )

    def read_timer_next_run(self, name: str, scope: str = "system") -> str:
        return timers.read_timer_next_run(
            name,
            scope=scope,
            systemctl_show=self.systemctl_show,
        )

    def read_timer_last_run(self, name: str, scope: str = "system") -> str:
        return timers.read_timer_last_run(
            name,
            scope=scope,
            systemctl_show=self.systemctl_show,
        )

    def schedule_for_display(self, service: ManagedService) -> str:
        return timers.schedule_for_display(
            service,
            read_timer_schedule=self.read_timer_schedule,
        )

    def sync_registry_from_systemd(
        self,
        target: Optional[ManagedService] = None,
    ) -> int:
        return linux_sync.sync_registry_from_systemd(
            target,
            load_registry=self.load_registry,
            save_registry=self.save_registry,
            managed_service_key=managed_service_key,
            unit_exists=self.unit_exists,
            systemctl_show=self.systemctl_show,
            read_timer_schedule=self.read_timer_schedule,
            read_timer_persistent=self.read_timer_persistent,
        )

    def list_discoverable_services_for_scope(
        self,
        scope: str,
    ) -> List[linux_catalog.DiscoverableService]:
        return linux_catalog.list_discoverable_services_for_scope(
            scope,
            run=self.run,
            systemctl_command=self.systemctl_command,
            systemd_scope_env=self.systemd_scope_env,
        )

    def list_discoverable_services(
        self,
        scope_filter: str = "all",
    ) -> List[linux_catalog.DiscoverableService]:
        return linux_catalog.list_discoverable_services(
            scope_filter,
            require_systemctl=self.require_systemctl,
            list_scope=self.list_discoverable_services_for_scope,
        )

    def render_discoverable_services_hint(
        self,
        empty_registry_note: bool = True,
        scope_filter: str = "all",
    ) -> None:
        linux_catalog.render_discoverable_services_hint(
            empty_registry_note=empty_registry_note,
            scope_filter=scope_filter,
            list_discoverable_services=self.list_discoverable_services,
        )

    def resolve_discoverable_targets(
        self,
        targets: List[str],
    ) -> List[linux_catalog.DiscoverableService]:
        return linux_catalog.resolve_discoverable_targets(
            targets,
            list_discoverable_services=self.list_discoverable_services,
            normalize_target_token=normalize_target_token,
            unit_exists=self.unit_exists,
        )

    def parse_unit_directives(self, unit_text: str) -> Dict[str, str]:
        return linux_catalog.parse_unit_directives(unit_text)

    def parse_bool(self, value: str, default: bool = True) -> bool:
        return common.parse_bool(value, default=default)
