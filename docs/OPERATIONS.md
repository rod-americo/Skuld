# Operations

## 1. Purpose

This document explains how to run, validate, diagnose, and safely operate Skuld
as it exists today.

## 2. Environments

| Environment | Purpose | Runtime | Notes |
| --- | --- | --- | --- |
| local development | Edit and validate the CLI | Python 3.9+ | No external Python dependencies. |
| Linux host | Operate tracked services | Python plus `systemd` | Needs `systemctl`; some logs/actions may need `sudo`. |
| macOS host | Operate tracked launchd jobs | Python plus `launchd` | Uses `launchctl`; log support is partial for externally tracked jobs. |
| CI or non-service shell | Syntax and docs validation | Python only | Live backend checks may be unavailable. |

There is no documented production fleet mode.

## 3. How To Run

### Local Setup

```bash
chmod +x ./skuld
```

### Primary Run

```bash
./skuld
```

### Non-Mutating Interface Check

```bash
./skuld --help
./skuld version
```

## 4. Operational Configuration

Versioned configuration:

- `config/doctor.json` controls project-doctor warning policy only.

Runtime configuration:

| Name | Required | Scope | Purpose |
| --- | --- | --- | --- |
| `SKULD_HOME` | no | Linux and macOS | Override registry/runtime home. |
| `SKULD_ENV_FILE` | no | Linux and macOS | Override env file lookup for sudo password support. |
| `SKULD_SUDO_PASSWORD` | no | Linux and macOS | Non-interactive sudo password for short-lived local use. |
| `SKULD_RUNTIME_STATS_FILE` | no | Linux | Override journal stats JSON path. |
| `SKULD_DEBUG` | no | Linux and macOS | Emit redacted debug diagnostics to stderr. |

Default runtime state:

- Linux registry: `~/.local/share/skuld/services.json`
- Linux stats: `/var/lib/skuld/journal_stats.json`
- macOS registry: `~/Library/Application Support/skuld/services.json`
- macOS stats: `~/Library/Application Support/skuld/runtime_stats.json`

Never commit real registry files, logs, stats, `.env`, or local config
overrides.

## 5. Minimum Validation

```bash
python3 -m py_compile ./skuld ./skuld_cli.py ./skuld_common.py ./skuld_observability.py ./skuld_registry.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --strict
python3 scripts/project_doctor.py --audit-config
bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh
```

For a changed subcommand, also run:

```bash
./skuld <subcommand> --help
```

For live backend validation, run only when the host service manager is available
and the registry points at disposable or intentionally managed services:

```bash
./skuld doctor
```

The automated test suite proves command behavior with faked backend command
responses. Live service-manager behavior is covered by the disposable smoke
scripts in the next section when those scripts are run on real hosts.

## 6. Smoke Checks

Non-mutating smoke:

```bash
./skuld --help
./skuld version
./skuld list --help
```

Linux live smoke can create a disposable `systemd --user` service locally or
on an SSH host:

```bash
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
```

macOS live smoke creates a disposable LaunchAgent:

```bash
scripts/smoke_macos_launchd.sh
```

The smoke scripts use temporary `SKULD_HOME` directories, track the disposable
service, exercise `status`, `doctor`, `restart`, `exec`, and `untrack`, then
remove the service definition they created. They still mutate the local service
manager, so run them only with explicit operator intent.

The helper scripts `scripts/smoke_process.sh` and `scripts/smoke_trigger.sh`
remain payloads for disposable smoke units.

## 7. Logs And Diagnostics

Linux logs:

```bash
./skuld logs <name> --lines 200
./skuld logs <name> --follow
./skuld logs <name> --timer --since "1 hour ago"
```

Linux uses `journalctl`. System-scope logs can require sudo depending on host
permissions.

macOS logs:

```bash
./skuld logs <name> --lines 200
./skuld logs <name> --follow
```

macOS logs are file-based and currently reliable only for compatible
Skuld-managed entries. Externally tracked `launchctl list` jobs may not expose
logs through Skuld.

Diagnostic commands:

```bash
./skuld doctor
./skuld describe <name-or-id>
./skuld status <name-or-id>
./skuld stats <name-or-id>
```

Redacted debug output:

```bash
SKULD_DEBUG=1 ./skuld status <name-or-id>
```

Debug output is intended for local diagnosis only and is not a stable machine
API.

## 8. Restart Policy

Skuld itself is a CLI. Code changes take effect the next time the command is
run. There is no long-running Skuld daemon to restart.

Operational impact by change type:

| Change | Restart impact |
| --- | --- |
| `./skuld`, `skuld_linux.py`, `skuld_macos.py` | Rerun the CLI. Existing backend services are not automatically restarted. |
| `scripts/skuld_journal_stats_collector.py` | Reinstall or update the collector where the Linux timer was installed. |
| `scripts/install_runtime_stats_timer.sh` | Rerun installer intentionally; it mutates systemd files with sudo. |
| `config/doctor.json` | Rerun `python3 scripts/project_doctor.py --audit-config`. |
| Documentation only | No runtime restart. |

## 9. Persistence, Backup, And Cleanup

Primary Skuld-owned state:

- Registry JSON.

Derived or optional state:

- Linux journal stats JSON.
- macOS runtime stats, event files, and compatible file logs.
- Python caches.

Backup:

- Back up the registry JSON if aliases and tracked service selection matter.
- No backup automation is provided.

Safe cleanup:

- Python caches and local `runtime/` scratch directories can be removed.
- Do not delete registry files unless the operator intentionally wants to lose
  Skuld's tracked service list.
- Do not delete backend unit files or launchd plists as part of Skuld cleanup
  unless that is a separate, explicit service-manager operation.

## 10. Troubleshooting

Invalid registry JSON:

- Symptom: command fails with `Invalid registry JSON`.
- Action: inspect the registry path and restore valid JSON array syntax.

Missing required registry fields:

- Symptom: command reports fields `name`, `exec_cmd`, or `description` are
  required.
- Action: use `sync` if possible or repair the registry entry.

Registry formatting or default fields are stale:

- Symptom: read-only commands work, but the registry file still has older
  ordering, omitted default fields, or non-canonical formatting.
- Action: run `./skuld sync` intentionally. Read-only commands do not rewrite an
  existing registry just to canonicalize it.

Ambiguous Linux target:

- Symptom: service exists in multiple scopes.
- Action: use `system:<name>`, `user:<name>`, or the registry ID.

Permission-limited Linux logs:

- Symptom: journal output warns about not seeing messages or permission denied.
- Action: use appropriate group membership or intentional sudo workflow.

macOS log unavailable:

- Symptom: `Logs are only available for jobs created by skuld on macOS`.
- Action: inspect logs through the owning launchd job or document a compatible
  log path before relying on `skuld logs`.

Sudo password support:

- Symptom: Skuld warns about `SKULD_SUDO_PASSWORD`.
- Action: prefer interactive sudo or short-lived local env usage. Never commit
  `.env`.

Runtime stats timer preview or removal:

- Preview install:
  `./scripts/install_runtime_stats_timer.sh --dry-run --registry "$HOME/.local/share/skuld/services.json"`
- Preview removal: `./scripts/install_runtime_stats_timer.sh --dry-run --uninstall`
- Remove installed timer: `./scripts/install_runtime_stats_timer.sh --uninstall`
- Removal deletes installed unit files and collector copy, then leaves the stats
  output JSON in place for operator review or manual cleanup.

## 11. Critical Operations

These commands can change host service state:

```bash
./skuld exec <name-or-id>
./skuld start <name-or-id>
./skuld stop <name-or-id>
./skuld restart <name-or-id>
./skuld sudo run -- <command>
./scripts/install_runtime_stats_timer.sh
```

Before running them, confirm:

- The target resolves to the intended registry entry.
- The backend scope is correct.
- The host service is safe to mutate.
- The command does not depend on a stale registry entry.

## 12. Changes That Require Updating This Document

- New entrypoint.
- New runtime state path.
- New backend dependency.
- New service-manager mutation behavior.
- New sudo behavior.
- New smoke or recovery procedure.
