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

### Changed

- Reworked `README.md` to distinguish current behavior from non-goals and weak
  spots.
- Reworked `AGENTS.md` to include reading order, layer rules, validation,
  documentation rules, and architecture guardrails.
- Clarified that the current public CLI tracks and operates existing services
  but does not create or edit service definitions.
- Expanded `.gitignore` for local runtime, logs, caches, and local config
  overrides.

### Notes

- No runtime service-management behavior changed in this structural recovery.
- The automated suite fakes backend service managers; live smoke tests still
  require disposable real services and explicit operator intent.
