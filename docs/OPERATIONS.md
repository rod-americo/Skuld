# Operations

## 1. Purpose

This document explains how to run, validate, diagnose, and safely operate Skuld as it exists today.

## 2. Environments

| Environment | Purpose | Runtime | Notes |
| --- | --- | --- | --- |
| local development | Edit and validate the CLI | Python 3.9+ | No external Python dependencies. |
| user install | Run packaged CLI from a checkout or wheel | Python 3.9+ | `pipx install .` is supported. |
| Linux host | Operate tracked services | Python plus `systemd` | Needs `systemctl`; some logs/actions may need `sudo`. |
| macOS host | Operate tracked launchd jobs | Python plus `launchd` | Uses `launchctl`; external log support depends on plist log paths. |
| CI or non-service shell | Syntax and docs validation | Python only | Live backend checks may be unavailable. |

There is no documented production fleet mode. GitHub Actions runs non-mutating validation on Ubuntu and macOS across the supported CI Python matrix. Live smoke scripts remain explicit manual operations because they create disposable service-manager state.

## 3. How To Run

### Local Setup

```bash chmod +x bin/skuld
```

### User Install

```bash
pipx install .
skuld --help
```

See `docs/INSTALL.md` for install and uninstall details.

### Primary Run

```bash bin/skuld
```

### Non-Mutating Interface Check

```bash
bin/skuld --help
bin/skuld version
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
| `SKULD_COLUMNS` | no | Linux and macOS | Fallback comma-separated columns for `skuld` and `skuld list`. |
| `SKULD_RUNTIME_STATS_FILE` | no | Linux | Override journal stats JSON path. |
| `SKULD_DEBUG` | no | Linux and macOS | Emit redacted debug diagnostics to stderr. |

Default runtime state:

- Linux registry: `~/.local/share/skuld/services.json`
- Linux user config: `~/.local/share/skuld/config.json`
- Linux stats: `/var/lib/skuld/journal_stats.json`
- macOS registry: `~/Library/Application Support/skuld/services.json`
- macOS user config: `~/Library/Application Support/skuld/config.json`
- macOS stats: `~/Library/Application Support/skuld/runtime_stats.json`

Table-column precedence is CLI `--columns`, then `$SKULD_HOME/config.json`, then `SKULD_COLUMNS`, then automatic layout. Persist a preference with:

```bash bin/skuld --columns bin/skuld list --columns bin/skuld config columns bin/skuld config columns 1 2 3 bin/skuld config columns id,name,service bin/skuld config columns id name service bin/skuld config show bin/skuld config columns default
```

`skuld --columns`, `skuld list --columns`, and `skuld config columns` without
arguments show a numbered column catalog, like the service `catalog` flow used
by `track`.

Linux-only read-only nginx monitoring is opt-in:

```bash
bin/skuld track --provider nginx
bin/skuld track provider:nginx
bin/skuld untrack --provider nginx
bin/skuld config show
```

When enabled, `list` renders a second `nginx routes` table below the main registry-backed table, and `describe <service>` shows matched nginx routes with their config source file. The provider never adds registry targets and does not reload or edit nginx.

`config.json` is a sibling user preference file. Do not mix it into `services.json`, which remains the service registry array.

Never commit real registry files, logs, stats, `.env`, or local config overrides.

### Managed Service Creation

Skuld can create a current-user service definition when explicitly requested:

```bash bin/skuld start --name api -- python app.py
```

On Linux this writes a user `systemd` service under
`~/.config/systemd/user/`. On macOS this writes a LaunchAgent plist plus a
Skuld wrapper script under the user's Skuld runtime paths. The new registry
entry is marked `managed_by_skuld=true`.

Delete only removes definitions created by Skuld:

```bash
bin/skuld delete api
```

External services added with `track` are not deleted by `delete`; use `bin/skuld untrack <name-or-id>` when the intent is to remove only the registry entry.

## 5. Minimum Validation

```bash python3 -m py_compile bin/skuld skuld/*.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py python3 -m unittest discover -s tests bin/skuld --help python3 scripts/check_project_gate.py python3 scripts/project_doctor.py python3 scripts/project_doctor.py --strict python3 scripts/project_doctor.py --audit-config bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh scripts/run_live_smokes.sh
```

For a changed subcommand, also run:

```bash
bin/skuld <subcommand> --help
```

For live backend validation, run only when the host service manager is available and the registry points at disposable or intentionally managed services:

```bash bin/skuld doctor
```

The automated test suite proves command behavior with faked backend command
responses. Live service-manager behavior is covered by the disposable smoke
scripts in the next section when those scripts are run on real hosts.

## 6. Smoke Checks

Non-mutating smoke:

```bash
bin/skuld --help
bin/skuld version
bin/skuld list --help
bin/skuld sudo --help
bin/skuld config --help
```

Linux live smoke can create a disposable `systemd --user` service locally or on an SSH host:

```bash scripts/smoke_linux_systemd_user.sh scripts/smoke_linux_systemd_user.sh --host <ssh-host>
```

For repository validation, `vidar` is an available Linux SSH host:

```bash
scripts/smoke_linux_systemd_user.sh --host vidar
```

`vidar` also has a repository checkout at `~/.local/src/skuld/`. If the copy-over-SSH workflow is not the most practical option for a validation cycle, update that checkout with `git pull` and run the Linux validation from there instead.

macOS live smoke creates a disposable LaunchAgent:

```bash scripts/smoke_macos_launchd.sh
```

The cleanup path boots out the disposable service by launchd service target
before falling back to the plist path. After cleanup, the script fails if the
new disposable label is still loaded, its plist or temp directory remains, or
that new label appears in launchd's persistent disabled/enabled override view.
It does not try to clean historical launchd override entries from older smoke
runs.

To run selected live smokes through one command:

```bash
scripts/run_live_smokes.sh --macos --linux-host <ssh-host>
scripts/run_live_smokes.sh --macos --linux-host vidar
```

The smoke scripts use temporary `SKULD_HOME` directories, track the disposable service, exercise `status`, `doctor`, `restart`, `exec`, and `untrack`, then remove the service definition they created. Cleanup is self-auditing: macOS checks the new launchd label, plist, temp directory, and disabled override view; Linux checks the disposable user unit, unit file, local state directory, and remote repository copy when SSH mode is used. They still mutate the local service manager, so run them only with explicit operator intent.

The helper scripts `scripts/smoke_process.sh` and `scripts/smoke_trigger.sh` remain payloads for disposable smoke units.

## 7. Logs And Diagnostics

Linux logs:

```bash bin/skuld logs <name> --lines 200 bin/skuld logs <name> --follow bin/skuld logs <name> --timer --since "1 hour ago"
```

Linux uses `journalctl`. System-scope logs can require sudo depending on host
permissions.

macOS logs:

```bash
bin/skuld logs <name> --lines 200
bin/skuld logs <name> --follow
```

macOS logs are file-based. They work for compatible Skuld-managed entries and for externally tracked launchd jobs whose plist declares `StandardOutPath` or `StandardErrorPath`. Externally tracked jobs without plist log paths may not expose logs through Skuld.

Diagnostic commands:

```bash bin/skuld doctor bin/skuld describe <name-or-id> bin/skuld status <name-or-id> bin/skuld stats <name-or-id>
```

Redacted debug output:

```bash
SKULD_DEBUG=1 bin/skuld status <name-or-id>
```

Debug output is intended for local diagnosis only and is not a stable machine API.

## 8. Restart Policy

Skuld itself is a CLI. Code changes take effect the next time the command is run. There is no long-running Skuld daemon to restart.

Operational impact by change type:

| Change | Restart impact |
| --- | --- |
| `bin/skuld`, backend modules, shared helper modules | Rerun the CLI. Existing backend services are not automatically restarted. |
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
- Do not delete backend unit files or launchd plists as part of Skuld cleanup.
Use `bin/skuld delete <name-or-id>` only for entries created by Skuld and marked `managed_by_skuld=true`; otherwise use service-manager tooling.

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
- Action: run `bin/skuld sync` intentionally. Read-only commands do not rewrite an
existing registry just to canonicalize it.

Ambiguous Linux target:

- Symptom: service exists in multiple scopes.
- Action: use `system:<name>`, `user:<name>`, or the registry ID.

Delete refuses an external service:

- Symptom: command reports that the target is externally tracked.
- Action: use `bin/skuld untrack <name-or-id>` for registry-only removal, or
remove the service definition with the owning service-manager workflow.

Permission-limited Linux logs:

- Symptom: journal output warns about not seeing messages or permission denied.
- Action: use appropriate group membership or intentional sudo workflow.

macOS log unavailable:

- Symptom: command reports that logs require a compatible `log_dir` or launchd
plist `StandardOutPath`/`StandardErrorPath`.
- Action: inspect logs through the owning launchd job, add plist log paths in
the service definition, or rely on Skuld-managed compatible log paths.

Sudo password support:

- Symptom: Skuld warns about `SKULD_SUDO_PASSWORD`.
- Action: prefer the native sudo timestamp workflow. Run `bin/skuld sudo auth`
once, then `bin/skuld sudo check`; Skuld sudo calls without a stored password use `sudo -n` and fail if the timestamp is not active. Use `bin/skuld sudo forget` to invalidate the timestamp. Never commit `.env`.

Invalid table columns:

- Symptom: Skuld exits with `Unknown service table column`.
- Action: run `bin/skuld --columns` or `bin/skuld config columns` to see numbered
column IDs. Use IDs such as `1 2 3`, names such as `id name service`, or a comma-separated subset of `id`, `name`, `service`, `timer`, `triggers`, `cpu`, `memory`, `ports`, `target`, `scope`, `backend`, `pid`, `user`, `restart`, `runs`, `last`, and `next`; use `default`, `auto`, or `all` to restore the automatic layout.

Invalid user config:

- Symptom: Skuld exits with `Invalid Skuld config` or `Invalid Skuld config
JSON`.
- Action: inspect `$SKULD_HOME/config.json` and either fix the JSON object or
reset table columns with `bin/skuld config columns default`.

Runtime stats timer preview or removal:

- Preview install:
`./scripts/install_runtime_stats_timer.sh --dry-run --registry "$HOME/.local/share/skuld/services.json"`
- Preview status: `./scripts/install_runtime_stats_timer.sh --dry-run --status`
- Preview verification: `./scripts/install_runtime_stats_timer.sh --dry-run --verify`
- Preview removal: `./scripts/install_runtime_stats_timer.sh --dry-run --uninstall`
- Show installed status: `./scripts/install_runtime_stats_timer.sh --status`
- Verify installed files/timer state: `./scripts/install_runtime_stats_timer.sh --verify`
- Remove installed timer: `./scripts/install_runtime_stats_timer.sh --uninstall`
- Removal deletes installed unit files and collector copy, then leaves the stats
output JSON in place for operator review or manual cleanup.

## 11. Critical Operations

These commands can change host service state:

```bash bin/skuld exec <name-or-id> bin/skuld start --name <name> -- <command> bin/skuld start <name-or-id> bin/skuld stop <name-or-id> bin/skuld restart <name-or-id> bin/skuld delete <name-or-id> bin/skuld sudo run -- <command> ./scripts/install_runtime_stats_timer.sh
```

Before running them, confirm:

- The target resolves to the intended registry entry.
- The backend scope is correct.
- The host service is safe to mutate.
- The command does not depend on a stale registry entry.
- `delete` targets only a Skuld-managed user service or LaunchAgent.

## 12. Changes That Require Updating This Document

- New entrypoint.
- New runtime state path.
- New backend dependency.
- New service-manager mutation behavior.
- New sudo behavior.
- New table-column configuration behavior.
- New smoke or recovery procedure.
