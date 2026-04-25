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

If the change touches host operations, also read:

- `scripts/install_runtime_stats_timer.sh`
- `scripts/skuld_journal_stats_collector.py`
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
python3 -m py_compile ./skuld ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --audit-config
```

For new or changed CLI commands, also run:

```bash
./skuld <subcommand> --help
```

If `systemd` is unavailable, state that clearly instead of treating live Linux
backend validation as complete.

## Hotspots

- `skuld_linux.py` and `skuld_macos.py` duplicate many responsibilities.
- `load_registry()` normalizes and writes the registry as a side effect.
- `start`, `stop`, `restart`, and `exec` can mutate host service state.
- Linux journal and port inspection can require permissions that vary by host.
- macOS logs are only reliable for jobs with compatible Skuld-managed log paths.
- `SKULD_SUDO_PASSWORD` support is convenient but sensitive.
- Legacy macOS plist/wrapper helpers remain in code but are not exposed as
  public create/edit commands.

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
