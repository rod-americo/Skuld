from __future__ import annotations

import argparse

import skuld_common as common
import skuld_macos_actions as macos_actions
import skuld_macos_catalog as macos_catalog
import skuld_macos_commands as macos_commands
import skuld_macos_schedules as schedules
import skuld_macos_view as macos_view
import skuld_tables as tables
from skuld_macos_context import MacOSBackendContext
from skuld_macos_model import ManagedService, suggest_display_name


class MacOSCommandHandlers:
    def __init__(self, context: MacOSBackendContext) -> None:
        self.context = context

    def track(self, args: argparse.Namespace) -> None:
        ctx = self.context
        macos_catalog.track_services(
            list(args.targets or []),
            alias=args.alias,
            resolve_discoverable_targets=ctx.resolve_discoverable_targets,
            suggest_display_name=suggest_display_name,
            prompt_display_name=ctx.prompt_display_name,
            ensure_display_name_available=ctx.ensure_display_name_available,
            get_managed=ctx.get_managed,
            launchctl_print_service_raw=ctx.launchctl_print_service_raw,
            extract_launchctl_value=ctx.extract_launchctl_value,
            service_factory=ManagedService,
            upsert_registry=ctx.upsert_registry,
            ok=ctx.ok,
        )

    def start_stop(self, args: argparse.Namespace, action: str) -> None:
        ctx = self.context
        macos_actions.apply_lifecycle_action_to_services(
            ctx.resolve_managed_many_arg(args),
            action,
            bootstrap_service=ctx.bootstrap_service,
            bootout_service=ctx.bootout_service,
            kickstart_service=ctx.kickstart_service,
            read_pid=ctx.read_pid,
            read_recent_run_root_pids=ctx.read_recent_run_root_pids,
            terminate_process_tree=ctx.terminate_process_tree,
            ok=ctx.ok,
        )

    def restart(self, args: argparse.Namespace) -> None:
        self.start_stop(args, "restart")

    def exec_now(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        macos_actions.execute_now(
            service,
            bootstrap_service=ctx.bootstrap_service,
            kickstart_service=ctx.kickstart_service,
            ok=ctx.ok,
        )

    def status(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        macos_commands.show_status(
            service,
            launchd_label_for_service=ctx.launchd_label_for_service,
            domain_target=ctx.domain_target,
            launchctl_service_info=ctx.launchctl_service_info,
            plist_path_for_service=ctx.plist_path_for_service,
        )

    def logs(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        lines = common.resolve_lines_arg(args, default=100)
        macos_commands.show_logs(
            service,
            since=args.since,
            timer=args.timer,
            follow=args.follow,
            lines=lines,
            log_paths_for_service=ctx.log_paths_for_service,
            tail_file=ctx.tail_file,
            info=ctx.info,
        )

    def _render_services_table(self, compact: bool, sort_by: str = "name") -> None:
        ctx = self.context
        macos_view.render_services_table(
            compact=compact,
            sort_by=sort_by,
            service_table_columns=ctx.service_table_columns,
            load_registry=ctx.load_registry,
            render_discoverable_services_hint=ctx.render_discoverable_services_hint,
            render_host_panel=ctx.render_host_panel,
            read_event_stats=ctx.read_event_stats,
            read_pid=ctx.read_pid,
            read_cpu_memory=ctx.read_cpu_memory,
            service_loaded=ctx.service_loaded,
            colorize=ctx.colorize,
            humanize_schedule_for_display=schedules.humanize_schedule_for_display,
            compute_next_run=schedules.compute_next_run,
            read_ports=ctx.read_ports,
            sort_service_rows=tables.sort_service_rows,
            fit_service_table=ctx.fit_service_table,
            render_table=ctx.render_table,
        )

    def list_services(self, args: argparse.Namespace) -> None:
        self._render_services_table(
            compact=False,
            sort_by=self.context.resolve_sort_arg(args),
        )

    def list_services_compact(self, sort_by: str = "name") -> None:
        self._render_services_table(compact=True, sort_by=sort_by)

    def catalog(self, args: argparse.Namespace) -> None:
        self.context.render_discoverable_services_hint(grep=getattr(args, "grep", "") or "")

    def stats(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        macos_commands.show_stats(service, update_runtime_stats=ctx.update_runtime_stats)

    def doctor(self, _args: argparse.Namespace) -> None:
        ctx = self.context
        services = ctx.load_registry()
        if not services:
            ctx.render_discoverable_services_hint()
            return
        macos_commands.doctor_services(
            services,
            plist_path_for_service=ctx.plist_path_for_service,
            wrapper_script_for_service=ctx.wrapper_script_for_service,
            service_loaded=ctx.service_loaded,
            ok=ctx.ok,
            err=ctx.err,
        )

    def rename(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        macos_commands.rename_service(
            service,
            args.new_name,
            ensure_display_name_available=ctx.ensure_display_name_available,
            service_factory=ManagedService,
            upsert_registry=ctx.upsert_registry,
            info=ctx.info,
            ok=ctx.ok,
        )

    def untrack(self, args: argparse.Namespace) -> None:
        ctx = self.context
        for service in ctx.resolve_managed_many_arg(args):
            macos_commands.untrack_service(
                service,
                remove_registry=ctx.remove_registry,
                ok=ctx.ok,
            )

    def describe(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        if not service:
            raise RuntimeError("Service target is required.")
        macos_commands.describe_service(
            service,
            launchctl_service_info=ctx.launchctl_service_info,
            read_event_stats=ctx.read_event_stats,
            compute_next_run=schedules.compute_next_run,
            plist_path_for_service=ctx.plist_path_for_service,
        )

    def sync(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args, required=False)
        name = service.name if service else None
        changed = ctx.sync_registry_from_launchd(name)
        if changed == 0:
            ctx.ok("Registry is already up to date.")
        else:
            ctx.ok(f"Registry updated for {changed} service(s).")
