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
- [x] `docs/DECISIONS.md` records current decisions and tradeoffs.

## 2. Operational Guardrails

- [x] `config/doctor.json` exists for structural doctor policy.
- [x] `scripts/check_project_gate.py` validates `PROJECT_GATE.md`.
- [x] `scripts/project_doctor.py` validates baseline docs and consistency.
- [x] `.githooks/pre-commit` exists as an opt-in local hook.
- [x] `scripts/install_git_hooks.sh` can opt into the local hook.
- [x] `.gitignore` covers local runtime, logs, caches, and secrets.
- [x] A behavior-focused `unittest` suite exists under `tests/`.

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
- [x] Extract common backend main-loop behavior into `skuld_cli.py`.
- [x] Add redacted opt-in debug diagnostics through `SKULD_DEBUG`.
- [x] Add smoke documentation and scripts for a disposable user service on
  Linux and a disposable LaunchAgent on macOS.
- [x] Add `--dry-run` and `--uninstall` paths for the Linux stats timer
  installer.
- [x] Move registry canonicalization behind explicit write paths instead of
  default read side effects.
- [ ] Decide whether further backend splitting is now justified by tests.

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
