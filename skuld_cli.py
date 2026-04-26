from __future__ import annotations

import argparse
import sys
from typing import Callable, Sequence


POST_REFRESH_COMMANDS = {"track", "rename", "untrack", "exec", "start", "stop", "restart", "sync"}
REGISTRY_FREE_COMMANDS = {"version", "sudo"}
QUICK_HELP = "Quick help: skuld track <id ...> | skuld <id|name> exec/start/stop/restart/status/logs/stats/describe/rename/untrack"


def run_backend_main(
    *,
    argv: Sequence[str],
    parser: argparse.ArgumentParser,
    configure_globals: Callable[[argparse.Namespace, argparse.ArgumentParser], None],
    load_registry: Callable[[], object],
    list_services_compact: Callable[[str], None],
    resolve_sort_arg: Callable[[argparse.Namespace], str],
    err: Callable[[str], None],
) -> int:
    args = parser.parse_args(list(argv)[1:])
    configure_globals(args, parser)

    try:
        command = getattr(args, "command", None)
        if command not in REGISTRY_FREE_COMMANDS:
            load_registry()
        if not command:
            list_services_compact(resolve_sort_arg(args))
            print(QUICK_HELP)
            print()
            return 0

        args.func(args)
        if command in POST_REFRESH_COMMANDS:
            print()
            list_services_compact(resolve_sort_arg(args))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        err(str(exc))
        return 1


def run_current_process_backend(
    *,
    parser: argparse.ArgumentParser,
    configure_globals: Callable[[argparse.Namespace, argparse.ArgumentParser], None],
    load_registry: Callable[[], object],
    list_services_compact: Callable[[str], None],
    resolve_sort_arg: Callable[[argparse.Namespace], str],
    err: Callable[[str], None],
) -> int:
    return run_backend_main(
        argv=sys.argv,
        parser=parser,
        configure_globals=configure_globals,
        load_registry=load_registry,
        list_services_compact=list_services_compact,
        resolve_sort_arg=resolve_sort_arg,
        err=err,
    )
