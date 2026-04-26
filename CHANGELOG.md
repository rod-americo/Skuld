# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog and follows semantic versioning
intent.

## [Unreleased]

### Added

- Structural recovery baseline from the project starter, adapted to Skuld's
  existing architecture.
- `PROJECT_GATE.md` with repository purpose, boundaries, and maintenance cost.
- `START_CHECKLIST.md` for existing-repository recovery follow-up.
- `docs/ARCHITECTURE.md` documenting the real composition root, backend flow,
  persistence, and hotspots.
- `docs/CONTRACTS.md` documenting registry fields, identifiers, inputs,
  outputs, and invariants.
- `docs/OPERATIONS.md` documenting setup, validation, logs, restart behavior,
  troubleshooting, and critical operations.
- `docs/DECISIONS.md` documenting structural recovery decisions.
- `config/doctor.json`, `scripts/check_project_gate.py`, and
  `scripts/project_doctor.py` for baseline governance validation.
- Opt-in local git hook files: `.githooks/pre-commit` and
  `scripts/install_git_hooks.sh`.
- Behavior-focused `unittest` suite for registry normalization, target
  resolution, backend command routing, stats/logs behavior, doctor findings,
  and entrypoint dispatch.
- `skuld_cli.py` for shared backend main-loop behavior.
- `skuld_linux_systemd.py` for Linux `systemd` command construction and
  low-level adapter behavior.
- `skuld_linux_timers.py` for Linux systemd timer directive parsing and display
  formatting.
- `skuld_macos_launchd.py` for macOS `launchd` target formatting and
  low-level adapter behavior.
- `skuld_macos_schedules.py` for macOS schedule parsing and display formatting.
- `skuld_observability.py` for redacted opt-in `SKULD_DEBUG` diagnostics.
- Disposable live smoke scripts for macOS LaunchAgent and Linux
  `systemd --user` validation, including SSH host mode for Linux.
- Dry-run and uninstall modes for the Linux journal stats timer installer.
- `scripts/run_live_smokes.sh` to run selected disposable live smokes through
  one explicit command.
- Status and verify modes for the Linux journal stats timer installer.

### Changed

- Reworked `README.md` to distinguish current behavior from non-goals and weak
  spots.
- Reworked `AGENTS.md` to include reading order, layer rules, validation,
  documentation rules, and architecture guardrails.
- Clarified that the current public CLI tracks and operates existing services
  but does not create or edit service definitions.
- Expanded `.gitignore` for local runtime, logs, caches, and local config
  overrides.
- Extracted shared CLI helper and registry storage mechanics into
  `skuld_common.py` and `skuld_registry.py`, reducing backend duplication
  without changing public commands.
- Removed unused macOS plist/wrapper creation helpers that were not reachable
  from the public CLI.
- Moved Linux `systemctl`/`journalctl` command construction and low-level
  systemd execution behind a dedicated adapter module while preserving CLI
  behavior.
- Moved Linux runtime stats JSON reads, journald execution counting, restart
  count formatting, and journal permission hints into `skuld_linux_runtime.py`.
- Moved Linux host overview, unit usage, PID/cgroup inspection, GPU parsing,
  and listening-port discovery into `skuld_linux_stats.py`.
- Moved Linux timer duration/calendar formatting out of the main Linux backend.
- Moved macOS `launchctl` target formatting, parsing, and low-level execution
  behind a dedicated adapter module while preserving CLI behavior.
- Moved macOS process-tree, termination, host overview, CPU/memory, and
  listening-port helpers into `skuld_macos_processes.py`.
- Moved macOS event stats, runtime stats updates, recent-run PID extraction,
  file-log path resolution, and tail helpers into `skuld_macos_runtime.py`.
- Moved macOS launchd schedule parsing and next-run display out of the main
  macOS backend.
- macOS `logs` can now read externally tracked launchd jobs when their plist
  declares `StandardOutPath` or `StandardErrorPath`.
- Linux `catalog` now accepts `--scope all|system|user` to focus discovery on
  one systemd scope without changing the catalog IDs used by `track`.
- Added `pyproject.toml`, `skuld_entrypoint.py`, and install/release docs so
  the CLI can be installed as a standard Python console command while `./skuld`
  remains supported for direct checkout use.
- Added GitHub Actions CI for non-mutating Ubuntu/macOS validation, including
  syntax, unit tests, gate/doctor checks, shell syntax, and package install
  verification.
- Moved shared service-table column policy, fitting, sorting, and host-panel
  helpers into `skuld_tables.py`.
- Moved Linux and macOS backend dependency wiring into `skuld_linux_context.py`
  and `skuld_macos_context.py`.
- Moved Linux and macOS CLI command-handler orchestration into
  `skuld_linux_handlers.py` and `skuld_macos_handlers.py`, leaving backend
  entrypoints as thin composition roots.
- Moved Linux service-table row assembly and state display mapping into
  `skuld_linux_view.py`.
- Moved Linux target-resolution rules into `skuld_linux_targets.py`.
- Moved macOS service-table row assembly and state display mapping into
  `skuld_macos_view.py`.
- Moved macOS target-resolution rules into `skuld_macos_targets.py`.
- Moved selected Linux and macOS detail-view line formatting into
  `skuld_linux_presenters.py` and `skuld_macos_presenters.py`.
- Moved Linux and macOS registry-only `rename`/`untrack` helpers, `doctor`
  orchestration, logs command flow, and `status`/`stats`/`describe` detail
  command flow into `skuld_linux_commands.py` and `skuld_macos_commands.py`.
- Moved Linux and macOS host-mutating `start`/`stop`/`restart`/`exec`
  orchestration into `skuld_linux_actions.py` and `skuld_macos_actions.py`.
- Moved Linux and macOS service dataclasses and registry normalization helpers
  into `skuld_linux_model.py` and `skuld_macos_model.py`.
- Moved Linux and macOS registry sync backfill into `skuld_linux_sync.py` and
  `skuld_macos_sync.py`.
- Moved Linux and macOS catalog discovery and `track` orchestration into
  `skuld_linux_catalog.py` and `skuld_macos_catalog.py`.
- Moved Linux and macOS CLI parser construction into
  `skuld_linux_parser.py` and `skuld_macos_parser.py`.
- Moved Linux live timer metadata reads and trigger display into
  `skuld_linux_timers.py`.
- Moved macOS launchd label, plist path, and runtime path derivation into
  `skuld_macos_paths.py`.
- Moved shared `sudo check` and `sudo run` command orchestration into
  `skuld_sudo.py`.
- Moved Linux service-name normalization and display-name suggestions into
  `skuld_linux_model.py`.
- Moved macOS display-name suggestions into `skuld_macos_model.py`.
- Moved Linux and macOS registry storage wiring and lookup helpers into
  `skuld_linux_registry.py` and `skuld_macos_registry.py`.
- Moved Linux and macOS service-table rendering flow into
  `skuld_linux_view.py` and `skuld_macos_view.py`.
- Moved shared log line-count argument resolution into `skuld_common.py`.
- Added module-inventory tests for package metadata, documented compile
  commands, and the Linux remote smoke payload.
- Changed macOS live smoke cleanup to boot out the disposable LaunchAgent by
  service target before falling back to the plist path.
- Changed macOS launchd bootstrap to avoid persistent `enable` overrides after
  successful bootstraps while still retrying disabled-service failures.
- Registry reads now normalize in memory by default. Existing registry files
  are rewritten only by explicit mutating commands or intentional
  `write_back=True` code paths.
- Live smoke scripts now fail when their cleanup audits find leftover
  disposable launchd/systemd state, temp directories, or remote repo copies.

### Notes

- No registry schema change was made in this structural recovery.
- The automated suite fakes backend service managers; live smoke tests use
  disposable real services and still require explicit operator intent.
- macOS smoke cleanup audits only the label created by the current run; it does
  not remove historical launchd disabled-override residue from older runs.
