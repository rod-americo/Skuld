# Skuld

[![CI](https://github.com/rod-americo/Skuld/actions/workflows/ci.yml/badge.svg)](https://github.com/rod-americo/Skuld/actions/workflows/ci.yml) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB) ![Platforms](https://img.shields.io/badge/platform-linux%20%7C%20macOS-555555) [![License](https://img.shields.io/github/license/rod-americo/Skuld)](LICENSE)

Local registry-based CLI for safely tracking, inspecting, and operating selected `systemd` and `launchd` services.

Skuld gives a single-host operator a stable view over explicitly registered services. It can list, inspect, start, stop, restart, execute, sync, diagnose, read logs, and create or delete narrowly scoped Skuld-managed user services. Externally defined services remain owned by the host service manager.

## Why It Exists

Local service operation tends to drift into shell aliases, one-off scripts, and implicit host knowledge. Skuld keeps the operational boundary explicit:

- discover existing services from `systemd` or `launchd`
- track only the external services the operator chooses
- create only explicit user-level service definitions marked as Skuld-managed
- resolve future commands through Skuld's local registry
- operate only registered services
- leave arbitrary unit files, arbitrary plist files, deployment, and
provisioning outside the tool

## What This Repository Is

- A standard-library Python CLI for local service visibility and control.
- A registry boundary around selected `systemd` and `launchd` services.
- A package-layout codebase with runtime modules in `skuld/`.
- A single-host operator tool with tests, docs, doctor checks, CI, and explicit
live smoke scripts.

## What This Repository Is Not

- Not an arbitrary service definition generator.
- Not a process supervisor.
- Not a deployment framework, package manager, scheduler authoring tool, fleet
manager, metrics platform, or log aggregation system.
- Not a published package channel or stable Python library API.
- Not authorized to operate arbitrary host services outside the Skuld registry.

## Supported Hosts

| Host | Backend | Main integrations |
| --- | --- | --- |
| Linux | `systemd` | `systemctl`, `journalctl`, `/proc`, optional `sudo`, optional read-only nginx discovery |
| macOS | `launchd` | `launchctl`, file logs, `lsof`, `ps`, optional `sudo` |

Python 3.9 or newer is required. Normal CLI use has no external Python dependencies.

## Safety Model

The registry is the safety boundary. Commands that operate or inspect a service resolve their target from the registry first:

```text exec, start, stop, restart, status, logs, describe, stats, rename, sync, untrack
```

`catalog` discovers candidates from the host service manager. `track` adds an
existing backend service to the registry. `start --name <name> -- <command>`
creates a Skuld-managed user service and registers it.

`untrack` removes only the Skuld registry entry; it does not remove a `systemd`
unit or `launchd` plist. `delete` removes service definitions only when the
registry entry has `managed_by_skuld=true`; external services are refused and
should use `untrack`.

## Quick Start

### 1. Clone

```bash
git clone git@github.com:rod-americo/skuld.git
cd skuld
```

### 2. Prepare

```bash chmod +x bin/skuld
```

### 3. Configure

Most workflows need no repository-local configuration. Runtime state lives
outside the worktree by default.

### 4. Run

```bash
bin/skuld
```

For a non-mutating interface check:

```bash bin/skuld --help
```

For user-level installation from a checkout:

```bash
pipx install .
skuld --help
```

## Entrypoints

- `bin/skuld`: direct checkout wrapper.
- `skuld`: installed console command from `pipx install .` or `pip install .`.
- `python -m skuld`: module execution from a checkout or installed package.

All entrypoints dispatch through `skuld.skuld_entrypoint:main`, which selects `skuld.skuld_macos` on macOS and `skuld.skuld_linux` elsewhere.

## Common Commands

```bash bin/skuld bin/skuld list bin/skuld ls bin/skuld catalog bin/skuld start --name api -- python app.py bin/skuld track <catalog-id-or-backend-name> --alias <name> bin/skuld status <name-or-id> bin/skuld logs <name-or-id> bin/skuld stats <name-or-id> bin/skuld describe <name-or-id> bin/skuld exec <name-or-id> bin/skuld start <name-or-id> bin/skuld stop <name-or-id> bin/skuld restart <name-or-id> bin/skuld sync bin/skuld doctor bin/skuld untrack <name-or-id> bin/skuld delete <name-or-id> bin/skuld info <name-or-id>
```

Use command help for the exact parser contract:

```bash
bin/skuld <subcommand> --help
```

## Configuration

Runtime state is host-local and defaults to user data paths:

| Platform | Registry | User config |
| --- | --- | --- |
| Linux | `~/.local/share/skuld/services.json` | `~/.local/share/skuld/config.json` |
| macOS | `~/Library/Application Support/skuld/services.json` | `~/Library/Application Support/skuld/config.json` |

Supported environment variables:

| Name | Purpose |
| --- | --- |
| `SKULD_HOME` | Override the registry/runtime home directory. |
| `SKULD_ENV_FILE` | Override the `.env` path used for sudo password lookup. |
| `SKULD_SUDO_PASSWORD` | Allow non-interactive sudo for short-lived local use. |
| `SKULD_COLUMNS` | Fallback comma-separated service-table columns. |
| `SKULD_RUNTIME_STATS_FILE` | Linux-only journal stats JSON override. |
| `SKULD_DEBUG` | Emit redacted debug lines to stderr. |

Prefer the native sudo timestamp instead of storing a password:

```bash bin/skuld sudo auth bin/skuld sudo check bin/skuld sudo forget
```

`SKULD_SUDO_PASSWORD` and `.env` sudo support remain compatibility mechanisms
for short-lived local operation. They are not production credential management.

## Service Table

`bin/skuld` and `bin/skuld list` show the same default compact table:

```text
id | name | service | timer | triggers | cpu | memory | ports
```

Columns can be selected per invocation, saved in user config, or supplied by environment fallback:

```bash bin/skuld --columns id,name,service bin/skuld config columns id name service bin/skuld config columns default SKULD_COLUMNS=id,name,service,timer bin/skuld
```

Run `bin/skuld --columns` or `bin/skuld config columns` to show the numbered
column catalog.

## Platform Notes

Linux supports `system` and `user` scopes:

```bash
bin/skuld catalog --scope user
bin/skuld track system:nginx --alias edge-proxy
bin/skuld track user:syncthing --alias sync-home
```

Create a Skuld-managed user service without sudo:

```bash bin/skuld start --name api -- python app.py bin/skuld delete api
```

For scheduled Linux jobs, `start`, `stop`, and `restart` act on the `.timer`
when the registry has schedule metadata and the timer exists. Otherwise they
act on the `.service`. `exec` starts the `.service` for an immediate run.

Linux also has an explicit read-only nginx provider:

```bash
bin/skuld track --provider nginx
bin/skuld untrack --provider nginx
```

The nginx provider renders route visibility and `describe` enrichment. It does not add registry targets, reload nginx, or edit nginx configuration.

macOS discovers visible launchd jobs from `launchctl list`:

```bash bin/skuld catalog --grep finder bin/skuld track com.apple.Finder --alias finder
```

Create a Skuld-managed LaunchAgent without sudo:

```bash
bin/skuld start --name api -- python app.py
bin/skuld delete api
```

macOS logs are file-based. They work for compatible Skuld-managed log paths and externally tracked launchd jobs whose plist declares `StandardOutPath` or `StandardErrorPath`.

## Validation

Minimum non-mutating repository validation:

```bash python3 -m py_compile bin/skuld skuld/*.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py python3 -m unittest discover -s tests bin/skuld --help python3 scripts/check_project_gate.py python3 scripts/project_doctor.py python3 scripts/project_doctor.py --strict python3 scripts/project_doctor.py --audit-config bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh scripts/run_live_smokes.sh
```

Live smoke scripts create disposable services and touch `launchctl` or
`systemctl --user` while they run. Run them only with explicit operator intent:

```bash
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
scripts/run_live_smokes.sh --macos --linux-host <ssh-host>
```

## Project Status

| Area | State |
| --- | --- |
| CLI | Real local CLI with Linux and macOS backends. |
| Registry | Versioned JSON contract, normalized in memory on reads and written by explicit mutating commands. |
| Tests | `unittest` suite with faked `systemd`, `journalctl`, and `launchd` interactions. |
| Live validation | Disposable macOS and Linux smoke scripts, including remote Linux over SSH. |
| Packaging | Checkout, wheel, and `pipx install .` are supported; no package channel is published. |
| Remote/fleet use | Out of scope except for the Linux smoke helper's SSH mode. |

## Known Weak Spots

- Linux and macOS stats depend on host-specific permissions, journal retention,
process visibility, and compatible log paths.
- Unit tests prove behavior with faked backend commands; live smokes prove
disposable host paths, not every service definition an operator may track.
- Skuld has CI-backed non-mutating validation, but no automated live
service-manager compatibility matrix and no published package channel yet.

## Documentation

- `docs/INSTALL.md`: install and uninstall details.
- `docs/ARCHITECTURE.md`: system flow, module responsibilities, persistence,
and hotspots.
- `docs/CONTRACTS.md`: registry schemas, identifiers, inputs, outputs, and
invariants.
- `docs/OPERATIONS.md`: runtime paths, validation, logs, troubleshooting, and
smoke checks.
- `docs/DECISIONS.md`: architectural and operational decisions.
- `docs/RELEASE.md`: release validation, wheel checks, and rollback.
- `docs/WISHLIST.md`: future provider and integration ideas that are not
current behavior.
- `PROJECT_GATE.md`: repository purpose, boundaries, maintenance cost, and
exit condition.
- `AGENTS.md`: contributor and AI-agent collaboration rules.
- `CHANGELOG.md`: notable repository changes.

## License

MIT. See `LICENSE`.
