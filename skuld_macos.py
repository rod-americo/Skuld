#!/usr/bin/env python3
from __future__ import annotations

import argparse

import skuld_cli
import skuld_macos_parser as macos_parser
from skuld_macos_context import MacOSBackendContext, SORT_CHOICES
from skuld_macos_handlers import MacOSCommandHandlers
from skuld_macos_model import DiscoverableService, ManagedService

VERSION = "0.3.0"

CONTEXT = MacOSBackendContext()
HANDLERS = MacOSCommandHandlers(CONTEXT)


def build_parser() -> argparse.ArgumentParser:
    return macos_parser.build_parser(
        sort_choices=SORT_CHOICES,
        version=VERSION,
        list_services=HANDLERS.list_services,
        catalog=HANDLERS.catalog,
        track=HANDLERS.track,
        rename=HANDLERS.rename,
        untrack=HANDLERS.untrack,
        exec_now=HANDLERS.exec_now,
        start_stop=HANDLERS.start_stop,
        restart=HANDLERS.restart,
        status=HANDLERS.status,
        logs=HANDLERS.logs,
        stats=HANDLERS.stats,
        doctor=HANDLERS.doctor,
        describe=HANDLERS.describe,
        sync=HANDLERS.sync,
        sudo_check=CONTEXT.sudo_check,
        sudo_run_command=CONTEXT.sudo_run_command,
    )


def configure_cli_globals(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    CONTEXT.configure_cli_globals(args, parser)


def main() -> int:
    return skuld_cli.run_current_process_backend(
        parser=build_parser(),
        configure_globals=configure_cli_globals,
        load_registry=CONTEXT.load_registry,
        list_services_compact=HANDLERS.list_services_compact,
        resolve_sort_arg=CONTEXT.resolve_sort_arg,
        err=CONTEXT.err,
    )


__all__ = [
    "CONTEXT",
    "DiscoverableService",
    "HANDLERS",
    "MacOSBackendContext",
    "MacOSCommandHandlers",
    "ManagedService",
    "SORT_CHOICES",
    "VERSION",
    "build_parser",
    "configure_cli_globals",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
