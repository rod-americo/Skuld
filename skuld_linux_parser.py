import argparse
from typing import Callable, Optional, Sequence


def _add_name_target_args(
    parser: argparse.ArgumentParser,
    *,
    target_help: Optional[str] = None,
    name_help: Optional[str] = None,
    id_help: Optional[str] = None,
) -> None:
    parser.add_argument("name", nargs="?", help=target_help)
    parser.add_argument("--name", dest="name_flag", help=name_help)
    parser.add_argument("--id", dest="id_flag", type=int, help=id_help)


def _add_multi_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("targets", nargs="*", help="Service target(s): managed NAME and/or ID")
    parser.add_argument("--name", dest="name_flag")
    parser.add_argument("--id", dest="id_flag", type=int)


def build_parser(
    *,
    sort_choices: Sequence[str],
    column_choices: Sequence[str],
    discoverable_scope_choices: Sequence[str],
    version: str,
    list_services: Callable[..., None],
    catalog: Callable[..., None],
    track: Callable[..., None],
    rename: Callable[..., None],
    untrack: Callable[..., None],
    exec_now: Callable[..., None],
    start_stop: Callable[..., None],
    restart: Callable[..., None],
    status: Callable[..., None],
    logs: Callable[..., None],
    stats: Callable[..., None],
    doctor: Callable[..., None],
    describe: Callable[..., None],
    sync: Callable[..., None],
    sudo_check: Callable[..., None],
    sudo_auth: Callable[..., None],
    sudo_forget: Callable[..., None],
    sudo_run_command: Callable[..., None],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skuld",
        description="CLI for tracking and operating systemd services",
    )
    parser.add_argument(
        "--no-env-sudo",
        action="store_true",
        help="Disable SKULD_SUDO_PASSWORD from env/.env and use regular sudo behavior",
    )
    parser.add_argument("--ascii", action="store_true", help="Force ASCII table borders")
    parser.add_argument("--unicode", action="store_true", help="Force Unicode table borders")
    parser.add_argument(
        "--sort",
        choices=sort_choices,
        default="name",
        help="Sort service views by name, id, cpu, or memory",
    )
    parser.add_argument(
        "--columns",
        metavar="LIST",
        help=(
            "Comma-separated table columns "
            f"({', '.join(column_choices)}); use default for automatic layout"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    list_parser = subparsers.add_parser("list", help="List services tracked by skuld")
    list_parser.add_argument(
        "--sort",
        choices=sort_choices,
        default="name",
        help="Sort by name, id, cpu, or memory",
    )
    list_parser.add_argument(
        "--columns",
        metavar="LIST",
        default=argparse.SUPPRESS,
        help=(
            "Comma-separated table columns "
            f"({', '.join(column_choices)}); use default for automatic layout"
        ),
    )
    list_parser.set_defaults(func=list_services)

    catalog_parser = subparsers.add_parser(
        "catalog",
        help="Show the current systemd discovery catalog",
    )
    catalog_parser.add_argument(
        "--scope",
        choices=discoverable_scope_choices,
        default="all",
        help="Filter catalog entries by scope: all, system, or user",
    )
    catalog_parser.set_defaults(func=catalog)

    track_parser = subparsers.add_parser(
        "track",
        help="Track systemd services from the current catalog or by service name",
    )
    track_parser.add_argument(
        "targets",
        nargs="+",
        help="Catalog ids or service names (example: 1 4 nginx sshd.service user:syncthing)",
    )
    track_parser.add_argument("--alias", help="Friendly name shown by skuld")
    track_parser.set_defaults(func=track)

    rename_parser = subparsers.add_parser(
        "rename",
        help="Change the display name of a tracked service",
    )
    _add_name_target_args(rename_parser)
    rename_parser.add_argument("new_name")
    rename_parser.set_defaults(func=rename)

    untrack_parser = subparsers.add_parser(
        "untrack",
        help="Remove a service from the skuld registry without touching systemd",
    )
    _add_name_target_args(untrack_parser)
    untrack_parser.set_defaults(func=untrack)

    exec_parser = subparsers.add_parser("exec", help="Execute a service immediately")
    _add_name_target_args(exec_parser)
    exec_parser.set_defaults(func=exec_now)

    start_parser = subparsers.add_parser("start", help="Start one or more services")
    _add_multi_target_args(start_parser)
    start_parser.set_defaults(func=lambda args: start_stop(args, "start"))

    stop_parser = subparsers.add_parser("stop", help="Stop one or more services")
    _add_multi_target_args(stop_parser)
    stop_parser.set_defaults(func=lambda args: start_stop(args, "stop"))

    restart_parser = subparsers.add_parser("restart", help="Restart one or more services")
    _add_multi_target_args(restart_parser)
    restart_parser.set_defaults(func=restart)

    status_parser = subparsers.add_parser("status", help="Service/timer status")
    _add_name_target_args(status_parser)
    status_parser.set_defaults(func=status)

    logs_parser = subparsers.add_parser("logs", help="Show logs from journalctl")
    _add_name_target_args(logs_parser)
    logs_parser.add_argument("lines_pos", nargs="?", type=int)
    logs_parser.add_argument("--lines", type=int, default=None)
    logs_parser.add_argument("--follow", action="store_true", help="Follow logs in real time")
    logs_parser.add_argument("--folow", dest="follow", action="store_true", help=argparse.SUPPRESS)
    logs_parser.add_argument("--since", help="journalctl time filter (example: '1 hour ago')")
    logs_parser.add_argument("--timer", action="store_true", help="Read .timer logs instead of .service")
    logs_parser.add_argument(
        "--output",
        default="short",
        help="journalctl output mode (e.g. short, short-iso, cat, json)",
    )
    logs_parser.add_argument("--plain", action="store_true", help="Shortcut for --output cat (message only)")
    logs_parser.set_defaults(func=logs)

    stats_parser = subparsers.add_parser(
        "stats",
        help="Show execution/restart counters for a tracked service",
    )
    _add_name_target_args(stats_parser)
    stats_parser.add_argument("--since", help="journalctl time filter (example: '24 hours ago')")
    stats_parser.add_argument("--boot", action="store_true", help="Count entries from current boot only")
    stats_parser.set_defaults(func=stats)

    doctor_parser = subparsers.add_parser("doctor", help="Check registry/systemd inconsistencies")
    doctor_parser.set_defaults(func=doctor)

    describe_parser = subparsers.add_parser("describe", help="Show details for a tracked service")
    _add_name_target_args(describe_parser)
    describe_parser.set_defaults(func=describe)

    sync_parser = subparsers.add_parser("sync", help="Backfill missing registry fields from systemd")
    _add_name_target_args(
        sync_parser,
        target_help="Sync only one managed service",
        name_help="Sync only one managed service",
        id_help="Sync only one managed service by id",
    )
    sync_parser.set_defaults(func=sync)

    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=lambda _args: print(version))

    sudo_parser = subparsers.add_parser("sudo", help="Helpers for one-off sudo usage")
    sudo_subparsers = sudo_parser.add_subparsers(dest="sudo_command", required=True)

    sudo_check_parser = sudo_subparsers.add_parser(
        "check",
        help="Check whether sudo can run non-interactively",
    )
    sudo_check_parser.set_defaults(func=sudo_check)

    sudo_auth_parser = sudo_subparsers.add_parser(
        "auth",
        help="Refresh the native sudo timestamp with the system sudo prompt",
    )
    sudo_auth_parser.set_defaults(func=sudo_auth)

    sudo_forget_parser = sudo_subparsers.add_parser(
        "forget",
        help="Invalidate the native sudo timestamp",
    )
    sudo_forget_parser.set_defaults(func=sudo_forget)

    sudo_run_parser = sudo_subparsers.add_parser("run", help="Run one command through sudo")
    sudo_run_parser.add_argument("command", nargs=argparse.REMAINDER)
    sudo_run_parser.set_defaults(func=sudo_run_command)

    return parser
