# Skuld

Skuld is a local Python CLI for tracking and operating explicitly registered
services on a single host.

It is a registry boundary around the host service manager:

- Linux: `systemd`, `systemctl`, `journalctl`, `/proc`, and optional `sudo`.
- macOS: `launchd`, `launchctl`, file logs, `lsof`, and optional `sudo`.

Skuld only operates services that are already in its own registry. Service
definition files remain owned by `systemd` or `launchd`.

## What This Repository Is

- A standard-library Python CLI for local service visibility and control.
- A root-level codebase with real runtime behavior in `./skuld`,
  `skuld_linux.py`, and `skuld_macos.py`.
- A registry-based operator tool for listing, tracking, starting, stopping,
  restarting, executing, inspecting, and reading logs for selected services.
- A structurally recovered existing repository with tests, docs, gates, doctor
  checks, and explicit live smoke scripts.

## What This Repository Is Not

- Not a service definition generator.
- Not a process supervisor.
- Not a deployment framework, package manager, scheduler authoring tool, fleet
  manager, metrics platform, or log aggregation system.
- Not a packaged `src/` Python distribution today.
- Not authorized to operate arbitrary host services outside the Skuld registry.

## Current Maturity

| Area | State |
| --- | --- |
| CLI | Real local CLI with Linux and macOS backends. |
| Registry | Versioned JSON contract, normalized in memory on reads and written by explicit mutating commands. |
| Tests | `unittest` suite with faked `systemd`, `journalctl`, and `launchd` interactions. |
| Live validation | Disposable macOS and Linux smoke scripts, including remote Linux over SSH. |
| CI | Non-mutating Ubuntu/macOS matrix for syntax, tests, docs, doctor, shell checks, and packaging. |
| Operations | Single-host local operation is documented. |
| Packaging | `pyproject.toml` exposes an installable console command; direct checkout use remains supported. |
| Remote/fleet use | Out of scope except for the Linux smoke helper's SSH mode. |

## Domain Boundary

The registry is the safety boundary. Commands that operate or inspect a service
resolve their target from the registry first:

```text
exec, start, stop, restart, status, logs, describe, stats, rename, sync, untrack
```

`catalog` discovers candidates from the host service manager. `track` adds an
existing backend service to the registry. `untrack` removes only the Skuld
registry entry; it does not remove a systemd unit or launchd plist.

Skuld may inspect service definitions, but the current public CLI does not
create or edit them.

## Entrypoint And Module Map

The public entrypoint is:

```bash
./skuld
```

`./skuld` is the composition root. It selects the backend from `sys.platform`:

- `darwin` -> `skuld_macos.main()`
- other platforms -> `skuld_linux.main()`

Internal modules:

| Module | Responsibility |
| --- | --- |
| `skuld_cli.py` | Shared backend main loop, command dispatch, and post-mutation table refresh. |
| `skuld_common.py` | Formatting, table rendering, subprocess helpers, env lookup, and sudo helpers. |
| `skuld_registry.py` | Generic registry load/save/upsert/remove mechanics. |
| `skuld_observability.py` | Opt-in redacted debug output through `SKULD_DEBUG`. |
| `skuld_linux.py` | Linux parser, registry schema, command handlers, target resolution, stats, and table state. |
| `skuld_linux_runtime.py` | Linux runtime stats JSON reads, journald execution counting, restart counts, and journal permission hints. |
| `skuld_linux_systemd.py` | Low-level systemd command construction and execution helpers. |
| `skuld_linux_stats.py` | Linux host overview, unit usage, process/PID inspection, GPU parsing, and listening-port inspection. |
| `skuld_linux_timers.py` | Linux timer parsing and display formatting. |
| `skuld_macos.py` | macOS parser, registry schema, command handlers, target resolution, stats, logs, and table state. |
| `skuld_macos_launchd.py` | Low-level launchd command construction and execution helpers. |
| `skuld_macos_processes.py` | macOS process tree, termination, host overview, CPU/memory, and port inspection helpers. |
| `skuld_macos_runtime.py` | macOS event stats, runtime stats file updates, recent-run PID extraction, file-log paths, and tail helpers. |
| `skuld_macos_schedules.py` | macOS schedule parsing, trigger formatting, and next-run display. |
| `skuld_tables.py` | Shared service-table column policy, fitting, sorting, and host-panel helpers. |

## Quick Start

### 1. Clone

```bash
git clone git@github.com:rod-americo/skuld.git
cd skuld
```

### 2. Prepare

```bash
chmod +x ./skuld
```

### 3. Configure

Most workflows need no repository-local configuration. Runtime state lives
outside the worktree by default. See [Configuration](#configuration) for the
supported environment variables.

### 4. Run

```bash
./skuld
```

For a non-mutating interface check:

```bash
./skuld --help
```

No external Python packages are required for normal CLI use.

For user-level installation from a checkout:

```bash
pipx install .
skuld --help
```

See `docs/INSTALL.md` for install and uninstall details.

## Configuration

Most workflows need no repository-local configuration. Runtime state lives
outside the worktree by default.

| Name | Required | Purpose |
| --- | --- | --- |
| `SKULD_HOME` | no | Override the registry/runtime home directory. |
| `SKULD_ENV_FILE` | no | Override the `.env` path used for sudo password lookup. |
| `SKULD_SUDO_PASSWORD` | no | Allow non-interactive sudo for short-lived local use. |
| `SKULD_RUNTIME_STATS_FILE` | Linux only | Override the Linux journal stats JSON path. |
| `SKULD_DEBUG` | no | Emit redacted debug lines to stderr. |

`SKULD_SUDO_PASSWORD` and `.env` sudo support are convenience mechanisms for
short-lived local operation. They are not production credential management.

## Commands

```bash
./skuld
./skuld list
./skuld catalog
./skuld track ...
./skuld rename ...
./skuld untrack ...
./skuld exec ...
./skuld start ...
./skuld stop ...
./skuld restart ...
./skuld status ...
./skuld logs ...
./skuld stats ...
./skuld describe ...
./skuld doctor
./skuld sync
./skuld version
./skuld sudo check
./skuld sudo run -- <command>
```

`./skuld` and `./skuld list` show the same compact table:

```text
id | name | service | timer | triggers | cpu | memory | ports
```

Supported sort examples:

```bash
./skuld --sort id
./skuld list --sort cpu
./skuld list --sort memory
```

Use command help for the exact current parser contract:

```bash
./skuld <subcommand> --help
```

## Registry

Default registry paths:

| Platform | Path |
| --- | --- |
| Linux | `~/.local/share/skuld/services.json` |
| macOS | `~/Library/Application Support/skuld/services.json` |

The registry is a JSON array. Read-only commands normalize entries in memory
without rewriting the file. Mutating commands such as `track`, `rename`,
`untrack`, and `sync` write canonical JSON with stable ordering, pretty
formatting, a trailing newline, and normalized IDs.

## Linux Notes

Skuld supports `system` and `user` systemd scopes.

Examples:

```bash
./skuld catalog
./skuld catalog --scope user
./skuld track nginx
./skuld track system:nginx --alias edge-proxy
./skuld track user:syncthing --alias sync-home
./skuld track 1 4 22
```

Use `./skuld catalog --scope user` when you want to inspect only `systemd --user`
units while keeping the same catalog IDs used by `track`.

For scheduled jobs, `start`, `stop`, and `restart` act on the `.timer` when the
registry has schedule metadata and the timer exists. Otherwise they act on the
`.service`. `exec` starts the `.service` for an immediate run.

Optional Linux runtime counters are installed outside the registry and require
explicit host-level setup:

```bash
./scripts/install_runtime_stats_timer.sh --dry-run --registry "$HOME/.local/share/skuld/services.json"
./scripts/install_runtime_stats_timer.sh --registry "$HOME/.local/share/skuld/services.json"
./scripts/install_runtime_stats_timer.sh --status
./scripts/install_runtime_stats_timer.sh --verify
./scripts/install_runtime_stats_timer.sh --uninstall
```

## macOS Notes

On macOS, `track` discovers visible launchd jobs from `launchctl list` and
stores the label plus inspected metadata.

Examples:

```bash
./skuld catalog
./skuld track 1 4 22
./skuld track com.apple.Finder --alias finder
```

`skuld logs` is file-based on macOS. It can read compatible Skuld-managed log
paths and externally tracked launchd jobs whose plist declares
`StandardOutPath` or `StandardErrorPath`. Jobs that rely only on unified logging
or application-specific logs may not expose logs through Skuld.

## Validation

Minimum repository validation:

```bash
python3 -m py_compile ./skuld ./skuld_entrypoint.py ./skuld_cli.py ./skuld_common.py ./skuld_linux_runtime.py ./skuld_linux_systemd.py ./skuld_linux_stats.py ./skuld_linux_timers.py ./skuld_macos_launchd.py ./skuld_macos_processes.py ./skuld_macos_runtime.py ./skuld_macos_schedules.py ./skuld_observability.py ./skuld_registry.py ./skuld_tables.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --strict
python3 scripts/project_doctor.py --audit-config
bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh scripts/run_live_smokes.sh
```

Live smoke scripts create disposable services, exercise real service-manager
paths, and remove their test service definitions:

```bash
scripts/run_live_smokes.sh --macos --linux-host <ssh-host>
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
```

Run live smokes only with explicit operator intent because they mutate
`launchctl` or `systemctl --user` state while they run.

## Project Docs

- `AGENTS.md`: collaboration protocol, reading order, validation, and hotspots.
- `PROJECT_GATE.md`: repository existence, boundaries, maintenance cost, and
  exit condition.
- `START_CHECKLIST.md`: recovery checklist for this existing repository.
- `docs/ARCHITECTURE.md`: real system map, flow, persistence, and hotspots.
- `docs/CONTRACTS.md`: canonical inputs, outputs, identifiers, and invariants.
- `docs/OPERATIONS.md`: setup, runtime, logs, restart, troubleshooting, and
  smoke checks.
- `docs/INSTALL.md`: checkout, `pipx`, virtualenv install, and uninstall
  behavior.
- `docs/RELEASE.md`: release validation, wheel build check, and rollback.
- `docs/DECISIONS.md`: architectural and operational decisions.
- `CHANGELOG.md`: notable repository changes.

## Known Weak Spots

- `skuld_linux.py` and `skuld_macos.py` are still large backend files even after
  Linux runtime/adapter/stats/timer and macOS adapter/process/runtime/schedule
  extractions.
- Linux and macOS stats depend on host-specific service-manager permissions,
  journal retention, process visibility, and compatible log paths.
- Unit tests prove behavior with faked backend commands; live smokes prove
  disposable host paths, not every service definition an operator may track.
- Skuld has CI-backed non-mutating validation, but no automated live
  service-manager compatibility matrix and no published package channel yet.

## License

This project is licensed under the MIT License. See `LICENSE`.
