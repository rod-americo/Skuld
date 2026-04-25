# Skuld

Skuld is a small Python CLI for tracking existing local services under a
human-friendly registry and operating only the services that are explicitly in
that registry.

The current system is not a service authoring framework. It is an operator
tool around `systemd` on Linux and `launchd` on macOS.

## What This Repository Is

- A standard-library Python CLI for local service visibility and control.
- A registry-based control layer for existing `systemd` units and visible
  `launchd` jobs.
- A narrow operational tool for listing, tracking, starting, stopping,
  restarting, executing, inspecting, and reading logs for registered services.
- A repository with real runtime behavior in the root scripts, not a greenfield
  layered package.

## What This Repository Is Not

- It is not a general-purpose process supervisor.
- It is not the canonical place to create, edit, or remove service definitions.
- It is not a deployment system, scheduler authoring tool, metrics platform, or
  fleet manager.
- It must not operate arbitrary host services unless they are present in the
  Skuld registry.
- It should not be reshaped into a `src/` package only to look like a starter
  scaffold.

## Current State

- Phase: existing CLI with structural recovery in progress.
- Runtime: Python 3.9+ and operating-system service managers.
- Primary platform integrations:
  - Linux: `systemd`, `systemctl`, `journalctl`, `/proc`, and optional `sudo`.
  - macOS: `launchd`, `launchctl`, `tail`, `lsof`, and optional `sudo`.
- Test maturity: behavior-focused `unittest` suite is versioned with faked
  service-manager interactions.
- Validation maturity: syntax checks, unit tests, CLI help checks, project gate
  checks, and a structural project doctor are available.
- Operational maturity: local single-host operation is documented; there is no
  remote deployment, fleet rollout, or backup automation.

## Domain Boundary

Skuld manages a local registry of services. The registry is the trust boundary:
commands such as `exec`, `start`, `stop`, `restart`, `status`, `logs`,
`describe`, `stats`, `rename`, `sync`, and `untrack` resolve their targets from
that registry.

Service definitions themselves belong to the host service manager:

- Linux service and timer unit files belong to `systemd`.
- macOS plists and labels belong to `launchd`.
- Skuld may inspect those definitions, but the current public CLI does not
  create or edit them.

## Entrypoints

Primary entrypoints:

- `./skuld`
- `skuld_cli.py`
- `skuld_linux.py`
- `skuld_macos.py`
- `skuld_common.py`
- `skuld_linux_systemd.py`
- `skuld_observability.py`
- `skuld_registry.py`
- `scripts/skuld_journal_stats_collector.py`
- `scripts/check_project_gate.py`
- `scripts/project_doctor.py`

`./skuld` is the composition root. It selects the backend from `sys.platform`:

- `darwin` imports `skuld_macos.py`
- every other platform imports `skuld_linux.py`

Each backend contains its own CLI parser, backend-specific model, command
adapters, command handlers, and runtime statistics helpers. Shared backend
runner behavior lives in `skuld_cli.py`. Linux `systemd` command construction
and low-level command execution live in `skuld_linux_systemd.py`. Shared
formatting, subprocess, table, sudo env, debug output, and registry storage
mechanics live in `skuld_common.py`, `skuld_observability.py`, and
`skuld_registry.py`.

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

No external Python packages are required for the CLI.

### 3. Configure

Most workflows need no repository-local configuration. Runtime state lives
outside the worktree by default.

Optional environment variables:

| Name | Required | Purpose |
| --- | --- | --- |
| `SKULD_HOME` | no | Override the registry/runtime home directory. |
| `SKULD_ENV_FILE` | no | Override the `.env` path used for sudo password lookup. |
| `SKULD_SUDO_PASSWORD` | no | Allow non-interactive sudo for short-lived local use. |
| `SKULD_RUNTIME_STATS_FILE` | Linux only | Override the Linux journal stats JSON path. |
| `SKULD_DEBUG` | no | Emit redacted debug lines to stderr for CLI subprocess and registry writes. |

Using `.env` sudo password support is discouraged for production systems.
Skuld warns when it uses `SKULD_SUDO_PASSWORD`.

### 4. Run

```bash
./skuld
```

For a non-mutating interface check:

```bash
./skuld --help
```

## Core Commands

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

`./skuld` and `./skuld list` show the same operational table:

```text
id | name | service | timer | triggers | cpu | memory | ports
```

Both accept:

```bash
./skuld --sort id
./skuld list --sort cpu
./skuld list --sort memory
```

## Registry

Linux registry path:

```text
~/.local/share/skuld/services.json
```

macOS registry path:

```text
~/Library/Application Support/skuld/services.json
```

The registry is a JSON array. Skuld normalizes registry entries in memory when
reading them. Read-only commands such as `list`, `status`, `logs`, `stats`,
`describe`, and `doctor` do not rewrite an existing registry just to canonicalize
formatting or fill defaults. Mutating commands such as `track`, `rename`,
`untrack`, and `sync` write canonical JSON with stable ordering, pretty JSON, a
trailing newline, and unique numeric IDs.

Only registry entries can be operated by Skuld. `untrack` removes an item from
the registry without removing the backend service definition.

## Linux Behavior

Skuld supports both `system` and `user` `systemd` scopes.

Prefer `systemd --user` for per-user daemons and timers:

```bash
loginctl enable-linger "$USER"
```

Use `system` scope for machine-wide services, boot-time startup before login, or
workloads that genuinely need elevated access.

Track examples:

```bash
./skuld track nginx
./skuld track system:nginx --alias edge-proxy
./skuld track user:syncthing --alias sync-home
./skuld catalog
./skuld track 1 4 22
```

On Linux, `track` inspects the existing `.service` and optional same-name
`.timer`, then stores the real backend target, scope, display name, command,
description, schedule metadata, and stable registry ID.

For scheduled jobs, `start`, `stop`, and `restart` act on `.timer` when the
registry has a schedule and the timer exists. Otherwise they act on `.service`.
`exec` always starts the `.service` for an immediate run.

Optional Linux runtime execution counters can be collected with:

```bash
./scripts/install_runtime_stats_timer.sh --dry-run --registry "$HOME/.local/share/skuld/services.json"
./scripts/install_runtime_stats_timer.sh --registry "$HOME/.local/share/skuld/services.json"
```

That installer uses `sudo` and writes a system service and timer outside the
Skuld registry. Treat it as host-level operational setup. It also supports
previewing or removing the installed timer:

```bash
./scripts/install_runtime_stats_timer.sh --dry-run --uninstall
./scripts/install_runtime_stats_timer.sh --uninstall
```

## macOS Behavior

On macOS, `track` discovers visible `launchd` jobs from `launchctl list` and
stores the label plus inspected metadata.

Examples:

```bash
./skuld
./skuld catalog
./skuld track 1 4 22
./skuld track com.apple.Finder --alias finder
```

Current macOS logs are file-based only for jobs that Skuld itself marks as
managed by Skuld. Jobs tracked from `launchctl list` may not have log files
available through `skuld logs`.

The macOS backend can inspect compatible Skuld-managed log/event paths when a
registry entry points at them, but the current public parser does not create or
edit launchd jobs.

## Validation

Minimum validation for this repository:

```bash
python3 -m py_compile ./skuld ./skuld_cli.py ./skuld_common.py ./skuld_linux_systemd.py ./skuld_observability.py ./skuld_registry.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --strict
python3 scripts/project_doctor.py --audit-config
bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh
```

The unit suite uses faked `systemd`, `journalctl`, and `launchd` interactions to
prove registry normalization, target resolution, command routing, log fallback,
stats output, doctor findings, and entrypoint dispatch without mutating the
host service manager.

Live smoke scripts create disposable services and then remove them:

```bash
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
```

## Project Docs

- `AGENTS.md`: collaboration protocol, reading order, validation, and hotspots.
- `PROJECT_GATE.md`: existence, boundaries, maintenance cost, and exit
  condition.
- `START_CHECKLIST.md`: recovery checklist for this existing repository.
- `docs/ARCHITECTURE.md`: real system map, flow, persistence, and hotspots.
- `docs/CONTRACTS.md`: canonical inputs, outputs, identifiers, and invariants.
- `docs/OPERATIONS.md`: setup, runtime, logs, restart, troubleshooting, and
  smoke checks.
- `docs/DECISIONS.md`: architectural and operational decisions.
- `CHANGELOG.md`: notable repository changes.

## Known Weak Spots

- The Linux and macOS backends still contain large backend-specific command
  flows, even though common CLI runner and shared helpers now reduce
  duplication.
- Operational stats are useful but partial: Linux depends on journald/systemd
  availability, while macOS uses local event/log files only for compatible
  registry entries.
- The root-level Python files are the real architecture today; splitting them
  should continue to be behavior-preserving and test-backed, not cosmetic.

## License

This project is licensed under the MIT License. See `LICENSE`.
