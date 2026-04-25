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
- `skuld_macos_launchd.py` for macOS `launchd` target formatting and
  low-level adapter behavior.
- `skuld_observability.py` for redacted opt-in `SKULD_DEBUG` diagnostics.
- Disposable live smoke scripts for macOS LaunchAgent and Linux
  `systemd --user` validation, including SSH host mode for Linux.
- Dry-run and uninstall modes for the Linux journal stats timer installer.

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
- Moved macOS `launchctl` target formatting, parsing, and low-level execution
  behind a dedicated adapter module while preserving CLI behavior.
- Registry reads now normalize in memory by default. Existing registry files
  are rewritten only by explicit mutating commands or intentional
  `write_back=True` code paths.

### Notes

- No registry schema change was made in this structural recovery.
- The automated suite fakes backend service managers; live smoke tests use
  disposable real services and still require explicit operator intent.
