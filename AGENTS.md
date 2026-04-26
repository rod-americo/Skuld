# AGENTS.md

This file defines collaboration and coding behavior for contributors and AI
agents working on Skuld.

## Project Personality

- Be direct, practical, and technical.
- Prefer clear implementation over abstract discussion.
- Keep communication concise and actionable.
- Explain tradeoffs when proposing changes.

## Minimum Reading Order

Before significant changes, read these files in order:

1. `README.md`
2. `PROJECT_GATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/CONTRACTS.md`
5. `docs/OPERATIONS.md`
6. `docs/DECISIONS.md`
7. The touched backend file: `skuld_linux.py`, `skuld_macos.py`, or `./skuld`
8. Shared helpers when relevant: `skuld_cli.py`, `skuld_common.py`,
   `skuld_linux_systemd.py`, `skuld_linux_stats.py`, `skuld_linux_timers.py`,
   `skuld_macos_launchd.py`, `skuld_macos_schedules.py`,
   `skuld_observability.py`, and `skuld_registry.py`

If the change touches host operations, also read:

- `scripts/install_runtime_stats_timer.sh`
- `scripts/skuld_journal_stats_collector.py`
- `scripts/smoke_macos_launchd.sh`
- `scripts/smoke_linux_systemd_user.sh`
- `scripts/run_live_smokes.sh`
- `scripts/smoke_process.sh`
- `scripts/smoke_trigger.sh`

## What Skuld Is

- A local CLI for tracking and operating explicitly registered services.
- A registry boundary around `systemd` and `launchd`.
- A root-level Python codebase with real users and real runtime behavior.

## What Skuld Must Not Become Accidentally

- A service definition generator.
- A deployment framework.
- A fleet manager.
- A metrics platform.
- A greenfield starter-shaped package that hides current behavior behind
  cosmetic directory moves.

## Layer Rules

The current repository does not have physical `domain / application /
infrastructure / interfaces` directories. Treat the layers as responsibilities
inside the existing files until a tested extraction is justified.

- Domain model:
  - `ManagedService`
  - `DiscoverableService`
  - registry identity rules
  - name, scope, display name, and ID invariants
- Application orchestration:
  - `build_parser()`
  - `main()`
  - command handlers such as `track`, `sync`, `doctor`, `start_stop`,
    `exec_now`, `logs`, and `stats`
- Infrastructure adapters:
  - `systemctl`, `journalctl`, `launchctl`, `sudo`, `/proc`, `ss`, `lsof`,
    filesystem reads and writes
- Shared support:
  - `skuld_cli.py` owns common backend main-loop behavior after a backend has
    built its parser.
  - `skuld_linux_systemd.py` owns Linux `systemd` command construction,
    `systemctl`/`journalctl` scope handling, and low-level systemd command
    execution.
  - `skuld_linux_stats.py` owns Linux host overview, unit usage, process/PID
    inspection, GPU memory parsing, and listening-port inspection.
  - `skuld_linux_timers.py` owns Linux systemd timer directive parsing,
    duration formatting, and schedule humanization.
  - `skuld_macos_launchd.py` owns macOS `launchd` command construction,
    domain/target formatting, launchctl parsing, and low-level launchctl
    execution.
  - `skuld_macos_schedules.py` owns macOS schedule parsing, display
    humanization, and next-run calculation.
  - `skuld_common.py` owns IO-agnostic CLI helpers, formatting, table fitting,
    subprocess wrappers, and sudo env lookup.
  - `skuld_observability.py` owns opt-in redacted debug output.
  - `skuld_registry.py` owns generic registry load/save/upsert/remove mechanics.
- Interface:
  - CLI arguments, help text, stdout/stderr output, table rendering

Keep new code close to the smallest existing responsibility that can own it.
Do not add an abstraction unless it removes real duplication or creates a clear
testing seam for behavior already present.

## Engineering Principles

- Favor standard library solutions unless an external dependency is clearly
  justified.
- Keep the CLI stable and backward-compatible when possible.
- Treat `systemd` and `launchd` operations as high-impact. Prefer explicit
  commands and clear errors.
- Preserve the rule: Skuld only operates services in its registry.
- Do not remove existing units, launchd plists, or registry entries unless the
  user explicitly requests that behavior.
- Do not log secrets.

## Code Style

Use English for:

- Function names
- Variable names
- CLI argument names
- Help text and user-facing messages
- Comments and documentation

Keep functions focused and small when touching nearby code. The existing backend
files are large; avoid making them larger through unrelated refactors.

## Documentation Rules

- Human documentation is in en-US.
- Technical identifiers are in en-US.
- Update `README.md` when commands, domain boundary, or user-visible behavior
  change.
- Update `docs/ARCHITECTURE.md` when flow, module responsibility, runtime paths,
  or dependencies change.
- Update `docs/CONTRACTS.md` when registry fields, identifiers, command inputs,
  outputs, or integration guarantees change.
- Update `docs/OPERATIONS.md` when setup, validation, logs, restart, runtime
  state, or troubleshooting changes.
- Update `docs/DECISIONS.md` when a change affects how the repository should
  evolve.
- Do not document planned behavior as current behavior.

## Runtime and Secrets

- Do not version `.env`, runtime state, generated logs, pycache, service
  registries, local stats files, dumps, or local config overrides.
- Warn users when `.env` or `SKULD_SUDO_PASSWORD` sudo support is involved.
- Prefer portable documentation paths such as `./skuld`, `$HOME`, and `$(pwd)`.
- Avoid machine-specific absolute paths unless a user explicitly asks for them.

## Minimum Validation

Run this before finalizing repository-wide structural or operational changes:

```bash
python3 -m py_compile ./skuld ./skuld_cli.py ./skuld_common.py ./skuld_linux_systemd.py ./skuld_linux_stats.py ./skuld_linux_timers.py ./skuld_macos_launchd.py ./skuld_macos_schedules.py ./skuld_observability.py ./skuld_registry.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --strict
python3 scripts/project_doctor.py --audit-config
bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh scripts/run_live_smokes.sh
```

For new or changed CLI commands, also run:

```bash
./skuld <subcommand> --help
```

If `systemd` is unavailable, state that clearly instead of treating live Linux
backend validation as complete.

Live smoke scripts mutate only disposable services, but still touch
`launchctl` or `systemctl --user`. Run them only when the operator explicitly
authorizes live host validation:

```bash
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
scripts/run_live_smokes.sh --macos --linux-host <ssh-host>
```

When a real Linux environment is needed for backend validation, `vidar` is an
available SSH host for `systemd --user` smoke checks:

```bash
scripts/smoke_linux_systemd_user.sh --host vidar
scripts/run_live_smokes.sh --macos --linux-host vidar
```

`vidar` also has a Skuld checkout at `~/.local/src/skuld/`. For iterative
validation, it is acceptable to update that checkout with `git pull` and run
tests from there when that is more practical than copying the local tree over
SSH.

## Hotspots

- `skuld_linux.py` and `skuld_macos.py` still carry large backend-specific
  command flows, though Linux service-manager, stats, and timer helpers have
  been extracted.
- Registry loads normalize in memory by default. Use explicit writes through
  `track`, `rename`, `untrack`, `sync`, `save_registry()`, `upsert_registry()`,
  or `RegistryStore.load(write_back=True)` when canonicalization should be
  persisted.
- `start`, `stop`, `restart`, and `exec` can mutate host service state.
- Linux journal and port inspection can require permissions that vary by host.
- macOS logs are only reliable for jobs with compatible Skuld-managed log paths
  or launchd plists that declare `StandardOutPath`/`StandardErrorPath`.
- `SKULD_SUDO_PASSWORD` support is convenient but sensitive.
- The unit suite fakes service-manager commands; live backend smokes still need
  disposable services and explicit operator intent.

## Git Workflow

- Work directly on `main` for this repository.
- Do not create `codex/*` branches unless the user explicitly asks for a branch
  workflow.
- When the user asks to commit and push, default to `git push origin main`.
- Commit messages are in English, imperative mood, and preferably
  `type(scope): summary`.

## Architecture Guardrails

- Do not perform a mass directory refactor without tests that prove behavior is
  preserved.
- Do not reintroduce service definition creation/editing without updating
  contracts, operations docs, and safety checks.
- Do not broaden Skuld to arbitrary host services outside the registry.
- Do not add dependencies for formatting, tables, config, or process execution
  unless the standard library path is demonstrably insufficient.
- Do not hide current weak spots by moving them into docs-only claims.
