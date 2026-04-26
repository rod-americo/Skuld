# Start Checklist

This checklist is for structural recovery of the existing Skuld repository. It
is not a greenfield scaffold checklist.

## 0. Existence Decision

- [x] The repository has a real CLI entrypoint: `./skuld`.
- [x] The repository has real backend implementations: `skuld_linux.py` and
  `skuld_macos.py`.
- [x] The scope is narrow enough to justify a repository: registry-based local
  service operation.
- [x] The repository should not be collapsed into dotfiles because it has a
  registry contract, backend adapters, docs, and validation scripts.

## 1. Baseline Added Or Recovered

- [x] `README.md` describes identity, scope, non-scope, commands, entrypoints,
  maturity, and weak spots.
- [x] `AGENTS.md` describes reading order, layer rules, validation, hotspots,
  and architecture guardrails.
- [x] `PROJECT_GATE.md` documents repository existence and boundaries.
- [x] `CHANGELOG.md` is present and now tracks the structural recovery.
- [x] `docs/ARCHITECTURE.md` documents the real current architecture.
- [x] `docs/CONTRACTS.md` documents registry and CLI contracts.
- [x] `docs/OPERATIONS.md` documents setup, run, validation, logs, restart, and
  troubleshooting.
- [x] `docs/INSTALL.md` documents checkout, `pipx`, virtualenv install, and
  uninstall behavior.
- [x] `docs/RELEASE.md` documents release validation, wheel build checks, and
  rollback.
- [x] `docs/DECISIONS.md` records current decisions and tradeoffs.

## 2. Operational Guardrails

- [x] `config/doctor.json` exists for structural doctor policy.
- [x] `scripts/check_project_gate.py` validates `PROJECT_GATE.md`.
- [x] `scripts/project_doctor.py` validates baseline docs and consistency.
- [x] `.githooks/pre-commit` exists as an opt-in local hook.
- [x] `scripts/install_git_hooks.sh` can opt into the local hook.
- [x] `.gitignore` covers local runtime, logs, caches, and secrets.
- [x] A behavior-focused `unittest` suite exists under `tests/`.
- [x] `pyproject.toml` exposes an installable console command without removing
  direct checkout execution through `./skuld`.
- [x] GitHub Actions runs non-mutating validation on Ubuntu and macOS.

## 3. What Is Intentionally Not Done Yet

- [ ] No mass move into `src/` was done.
- [ ] No artificial `domain / application / infrastructure / interfaces`
  directory tree was created.
- [x] Live host service smoke is documented as an explicit disposable-target
  operation, not a hidden validation step.
- [ ] No service authoring command was reintroduced.
- [ ] No operational readiness claim was added for fleets, remote hosts, or
  deployment automation.

## 4. Next Safe Work

- [x] Add focused tests around registry normalization and target resolution.
- [x] Add tests for command routing: timer-backed services versus direct
  services on Linux.
- [x] Remove unused legacy macOS wrapper/plist creation helpers that were not
  exposed by the CLI.
- [x] Extract shared table rendering and registry helpers after tests exist.
- [x] Extract shared service-table column policy, fitting, sorting, and
  host-panel helpers into `skuld_tables.py`.
- [x] Extract common backend main-loop behavior into `skuld_cli.py`.
- [x] Add redacted opt-in debug diagnostics through `SKULD_DEBUG`.
- [x] Add smoke documentation and scripts for a disposable user service on
  Linux and a disposable LaunchAgent on macOS.
- [x] Add `--dry-run` and `--uninstall` paths for the Linux stats timer
  installer.
- [x] Add `--status` and `--verify` paths for the Linux stats timer installer.
- [x] Add one-command live smoke orchestration through
  `scripts/run_live_smokes.sh`.
- [x] Allow macOS logs for external launchd jobs when plist log paths are
  available.
- [x] Move registry canonicalization behind explicit write paths instead of
  default read side effects.
- [x] Extract Linux runtime stats JSON reads, journald execution counting,
  restart count formatting, and journal permission hints into
  `skuld_linux_runtime.py`.
- [x] Extract Linux `systemd` low-level adapter behavior into
  `skuld_linux_systemd.py`.
- [x] Extract Linux host/unit stats and port inspection into
  `skuld_linux_stats.py`.
- [x] Extract Linux systemd timer formatting into `skuld_linux_timers.py`.
- [x] Extract Linux target-resolution rules into `skuld_linux_targets.py`.
- [x] Extract Linux service-table row assembly into `skuld_linux_view.py`.
- [x] Extract Linux detail-view formatting into `skuld_linux_presenters.py`.
- [x] Extract Linux registry and detail command helpers into
  `skuld_linux_commands.py`.
- [x] Extract Linux host-mutating lifecycle and exec orchestration into
  `skuld_linux_actions.py`.
- [x] Extract Linux service dataclasses and registry normalization into
  `skuld_linux_model.py`.
- [x] Extract Linux registry sync backfill into `skuld_linux_sync.py`.
- [x] Extract macOS `launchd` low-level adapter behavior into
  `skuld_macos_launchd.py`.
- [x] Extract macOS process-tree, host overview, CPU/memory, and port helpers
  into `skuld_macos_processes.py`.
- [x] Extract macOS event stats, runtime stats updates, recent-run PID
  extraction, file-log paths, and tail helpers into `skuld_macos_runtime.py`.
- [x] Extract macOS schedule parsing and display formatting into
  `skuld_macos_schedules.py`.
- [x] Extract macOS target-resolution rules into `skuld_macos_targets.py`.
- [x] Extract macOS service-table row assembly into `skuld_macos_view.py`.
- [x] Extract macOS detail-view formatting into `skuld_macos_presenters.py`.
- [x] Extract macOS registry and detail command helpers into
  `skuld_macos_commands.py`.
- [x] Extract macOS host-mutating lifecycle and exec orchestration into
  `skuld_macos_actions.py`.
- [x] Extract macOS service dataclasses and registry normalization into
  `skuld_macos_model.py`.
- [x] Extract macOS registry sync backfill into `skuld_macos_sync.py`.
- [x] Add installable package metadata and an importable CLI entrypoint.
- [x] Add CI for syntax, unit tests, gate, doctor, shell checks, and packaging.
- [ ] Continue backend splitting around command handlers, rendering, and
  target-resolution responsibilities where tests justify it.

## 5. Do Not Do In The Next Round

- [ ] Do not restructure files to resemble the starter kit without behavior
  tests.
- [ ] Do not expand Skuld into deployment, provisioning, package management, or
  remote fleet operation.
- [ ] Do not store real registries, logs, stats, sudo secrets, or host-local
  config in git.
- [ ] Do not document planned commands as current commands.
- [ ] Do not treat `sudo` password support as production-safe credential
  management.
