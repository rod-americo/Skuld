from __future__ import annotations

import argparse

import skuld_common as common
import skuld_linux_actions as linux_actions
import skuld_linux_catalog as linux_catalog
import skuld_linux_commands as linux_commands
import skuld_linux_nginx as linux_nginx
import skuld_linux_view as linux_view
import skuld_tables as tables
from skuld_linux_context import LinuxBackendContext
from skuld_linux_model import ManagedService, format_scoped_name, suggest_display_name


class LinuxCommandHandlers:
    def __init__(self, context: LinuxBackendContext) -> None:
        self.context = context

    def _render_services_table(self, compact: bool, sort_by: str = "name") -> None:
        ctx = self.context
        linux_view.render_services_table(
            compact=compact,
            sort_by=sort_by,
            service_table_columns=ctx.service_table_columns,
            require_systemctl=ctx.require_systemctl,
            load_registry=ctx.load_registry,
            render_discoverable_services_hint=ctx.render_discoverable_services_hint,
            read_gpu_memory_by_pid=ctx.read_gpu_memory_by_pid,
            render_host_panel=ctx.render_host_panel,
            unit_exists=ctx.unit_exists,
            unit_active=ctx.unit_active,
            display_unit_state=ctx.display_unit_state,
            colorize=ctx.colorize,
            read_unit_usage=ctx.read_unit_usage,
            timer_triggers_for_display=ctx.timer_triggers_for_display,
            read_unit_pids=ctx.read_unit_pids,
            read_unit_ports=ctx.read_unit_ports,
            load_runtime_stats=ctx.load_runtime_stats,
            format_restarts_exec=ctx.format_restarts_exec,
            read_timer_next_run=ctx.read_timer_next_run,
            read_timer_last_run=ctx.read_timer_last_run,
            render_extra_sections=lambda services: self.render_extra_sections(services),
            sort_service_rows=tables.sort_service_rows,
            fit_service_table=ctx.fit_service_table,
            render_table=ctx.render_table,
        )

    def render_extra_sections(self, services: list[ManagedService]) -> None:
        ctx = self.context
        if not ctx.nginx_monitoring_enabled():
            return
        linux_nginx.render_routes_table(
            ctx.discover_nginx_routes(),
            services=services,
            read_unit_ports=ctx.read_unit_ports,
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
        self.context.render_discoverable_services_hint(
            empty_registry_note=False,
            scope_filter=getattr(args, "scope", "all"),
        )

    def exec_now(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        ctx.require_systemctl()
        linux_actions.execute_now(
            service,
            run_systemctl_action=ctx.run_systemctl_action,
            ok=ctx.ok,
        )

    def start_stop(self, args: argparse.Namespace, action: str) -> None:
        ctx = self.context
        services = ctx.resolve_managed_many_arg(args)
        ctx.require_systemctl()
        linux_actions.apply_lifecycle_action_to_services(
            services,
            action,
            unit_exists=ctx.unit_exists,
            run_systemctl_action=ctx.run_systemctl_action,
            ok=ctx.ok,
        )

    def restart(self, args: argparse.Namespace) -> None:
        self.start_stop(args, "restart")

    def status(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        ctx.require_systemctl()
        linux_commands.show_status(
            service,
            format_scoped_name=format_scoped_name,
            systemd_scope_env=ctx.systemd_scope_env,
            systemctl_command=ctx.systemctl_command,
            run=ctx.run,
        )

    def logs(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        lines = common.resolve_lines_arg(args, default=100)
        ctx.require_systemctl()
        linux_commands.show_logs(
            service,
            timer=args.timer,
            since=args.since,
            follow=args.follow,
            plain=args.plain,
            output=args.output,
            lines=lines,
            journalctl_command=ctx.journalctl_command,
            systemd_scope_env=ctx.systemd_scope_env,
            run=ctx.run,
            run_sudo=ctx.run_sudo,
            journal_permission_hint=ctx.journal_permission_hint,
        )

    def stats(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        ctx.require_systemctl()
        linux_commands.show_stats(
            service,
            since=args.since,
            boot=args.boot,
            sync_registry_from_systemd=ctx.sync_registry_from_systemd,
            count_unit_starts=ctx.count_unit_starts,
            read_restart_count=ctx.read_restart_count,
            format_scoped_name=format_scoped_name,
        )

    def track(self, args: argparse.Namespace) -> None:
        ctx = self.context
        provider = getattr(args, "provider", None)
        targets = list(args.targets or [])
        if provider or (len(targets) == 1 and linux_nginx.is_provider_target(targets[0])):
            if provider and targets:
                raise RuntimeError("Use either service targets or --provider, not both.")
            if args.alias:
                raise RuntimeError("--alias is not supported when enabling a monitoring provider.")
            provider_name = provider or linux_nginx.NGINX_PROVIDER
            if provider_name != linux_nginx.NGINX_PROVIDER:
                raise RuntimeError(f"Unsupported provider '{provider_name}'.")
            ctx.set_nginx_monitoring_enabled(True)
            ctx.ok("Enabled nginx monitoring.")
            return
        if not targets:
            raise RuntimeError("Use: skuld track <id ...> or skuld track <service ...>")
        ctx.require_systemctl()
        linux_catalog.track_services(
            targets,
            alias=args.alias,
            resolve_discoverable_targets=ctx.resolve_discoverable_targets,
            suggest_display_name=suggest_display_name,
            prompt_display_name=ctx.prompt_display_name,
            ensure_display_name_available=ctx.ensure_display_name_available,
            get_managed=ctx.get_managed,
            systemctl_cat=ctx.systemctl_cat,
            systemctl_show=ctx.systemctl_show,
            unit_exists=ctx.unit_exists,
            parse_bool=ctx.parse_bool,
            service_factory=ManagedService,
            upsert_registry=ctx.upsert_registry,
            ok=ctx.ok,
        )

    def rename(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args)
        linux_commands.rename_service(
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
        provider = getattr(args, "provider", None)
        targets = list(getattr(args, "targets", []) or [])
        if provider or (len(targets) == 1 and linux_nginx.is_provider_target(targets[0])):
            if provider and targets:
                raise RuntimeError("Use either service targets or --provider, not both.")
            provider_name = provider or linux_nginx.NGINX_PROVIDER
            if provider_name != linux_nginx.NGINX_PROVIDER:
                raise RuntimeError(f"Unsupported provider '{provider_name}'.")
            ctx.set_nginx_monitoring_enabled(False)
            ctx.ok("Disabled nginx monitoring.")
            return
        for service in ctx.resolve_managed_many_arg(args):
            linux_commands.untrack_service(
                service,
                remove_registry=ctx.remove_registry,
                ok=ctx.ok,
            )

    def doctor(self, _args: argparse.Namespace) -> None:
        ctx = self.context
        ctx.require_systemctl()
        services = ctx.load_registry()
        if not services:
            print("No services tracked by skuld.")
            return
        linux_commands.doctor_services(
            services,
            unit_exists=ctx.unit_exists,
            unit_active=ctx.unit_active,
            display_unit_state=ctx.display_unit_state,
            read_timer_schedule=ctx.read_timer_schedule,
            systemctl_cat=ctx.systemctl_cat,
            parse_unit_directives=ctx.parse_unit_directives,
            format_scoped_name=format_scoped_name,
            ok=ctx.ok,
            err=ctx.err,
        )

    def describe(self, args: argparse.Namespace) -> None:
        ctx = self.context
        target = ctx.resolve_managed_arg(args)
        ctx.require_systemctl()
        linux_commands.describe_service(
            target,
            require_managed=ctx.require_managed,
            unit_exists=ctx.unit_exists,
            systemctl_show=ctx.systemctl_show,
            format_scoped_name=format_scoped_name,
        )
        if ctx.nginx_monitoring_enabled():
            for line in linux_nginx.describe_route_lines(
                target,
                routes=ctx.discover_nginx_routes(),
                read_unit_ports=ctx.read_unit_ports,
            ):
                print(line)

    def sync(self, args: argparse.Namespace) -> None:
        ctx = self.context
        service = ctx.resolve_managed_arg(args, required=False)
        ctx.require_systemctl()
        changed = ctx.sync_registry_from_systemd(service)
        if changed == 0:
            ctx.ok("Registry is already up to date.")
        else:
            ctx.ok(f"Registry updated for {changed} service(s).")
