# Decisions

This file records lightweight architectural and operational decisions. Keep new
entries factual: context, decision, impact, tradeoff, and rejected alternatives.

## 2026-04-25 - Recover The Existing Repository Instead Of Rescaffolding

**Context**

Skuld already has real root-level Python entrypoints and backend behavior. A
cosmetic move into a starter-shaped `src/` tree would increase risk without
proving behavior.

**Decision**

Keep `./skuld`, `skuld_linux.py`, and `skuld_macos.py` in place for this
recovery round. Add documentation and guardrails around the real structure.

**Impact**

- The repository is more auditable without a behavior-changing refactor.
- The current root-level architecture remains explicit technical debt.

**Tradeoff**

- The code still lacks physical layer separation.
- Future extraction should be test-backed.

**Alternatives rejected**

- Moving files into `src/skuld/` during this round.
- Creating empty layer directories that the code does not use.

## 2026-04-25 - Preserve Registry-Only Service Operation

**Context**

Skuld's safety boundary is that it operates only services explicitly present in
its registry.

**Decision**

Document the registry as the canonical control boundary and keep service
definition authoring outside the current public CLI contract.

**Impact**

- Operations stay narrow and auditable.
- Users must create or edit `systemd` units and `launchd` plists outside Skuld.

**Tradeoff**

- Skuld is less convenient than an all-in-one service generator.
- The boundary is easier to defend operationally.

**Alternatives rejected**

- Reintroducing create/edit behavior without tests and contracts.
- Allowing operations against arbitrary backend services that are not tracked.

## 2026-04-25 - Use `config/doctor.json` For Governance Policy

**Context**

The starter supports a versioned doctor policy. Skuld did not have a governance
tree or versioned runtime config.

**Decision**

Use `config/doctor.json` for project-doctor policy because it matches the
starter baseline and is not confused with Skuld runtime state.

**Impact**

- Structural validation has one versioned policy file.
- Runtime configuration remains environment-based and host-local.

**Tradeoff**

- `config/` is currently governance/tooling config, not Skuld application
  config.

**Alternatives rejected**

- Adding `governance/doctor.json` and another top-level concept.
- Hiding doctor policy inside a script.

## 2026-04-25 - Make Git Hook Installation Opt-In

**Context**

This is an existing repository with a real workflow. Enabling hooks
automatically could disrupt local commits.

**Decision**

Add `.githooks/pre-commit` and `scripts/install_git_hooks.sh`, but do not
activate them automatically.

**Impact**

- Contributors can opt into gate, doctor, and syntax checks.
- The current git workflow is not silently changed.

**Tradeoff**

- Hook enforcement is not guaranteed unless installed locally.

**Alternatives rejected**

- Running `git config core.hooksPath .githooks` automatically.
- Skipping hook files entirely.

## 2026-04-25 - Keep Standard Library As The Default Dependency Policy

**Context**

The CLI currently has no external Python dependency.

**Decision**

Continue to prefer Python standard library implementation for CLI parsing,
filesystem state, subprocess execution, and validation scripts.

**Impact**

- Installation remains simple.
- Behavior remains easier to audit on hosts without package bootstrapping.

**Tradeoff**

- Table rendering, testing, and config validation require more local code.

**Alternatives rejected**

- Adding dependencies before a clear behavior or maintenance need exists.
