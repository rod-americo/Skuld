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

## 2026-04-25 - Extract Shared Helpers Without Repackaging The CLI

**Context**

After adding behavior tests, the most obvious duplication was in IO-agnostic
helpers and registry storage mechanics shared by both backends.

**Decision**

Create `skuld_common.py` and `skuld_registry.py` while keeping backend-specific
schemas, command handlers, and service-manager adapters in `skuld_linux.py` and
`skuld_macos.py`.

**Impact**

- Registry load/save/upsert/remove behavior now has one storage implementation.
- Table fitting, formatting, subprocess, sudo env lookup, and related helpers
  are shared.
- The public CLI and registry schemas remain unchanged.

**Tradeoff**

- Backends still own orchestration and adapter behavior.
- The repository is not repackaged into `src/`; imports remain root-local.

**Alternatives rejected**

- Moving the whole project into a package layout in the same refactor.
- Forcing backend schemas into a single dataclass.

## 2026-04-25 - Centralize Backend Main-Loop Behavior

**Context**

Linux and macOS still need separate parsers, models, and service-manager
adapters, but their top-level command loop had duplicated behavior.

**Decision**

Add `skuld_cli.py` for backend-neutral parser execution, registry preloading,
post-mutation table refresh, and common exit-code handling.

**Impact**

- Both backends keep their existing public commands.
- Command-loop behavior is easier to test and change in one place.
- Backend-specific command handlers remain local to each backend.

**Tradeoff**

- The repository still uses root-local imports instead of a packaged module.
- Parser construction remains duplicated where options diverge.

**Alternatives rejected**

- Repackaging the whole CLI before paying down behavior risk.
- Forcing one shared parser across different backends.

## 2026-04-25 - Add Redacted Opt-In Debug Output

**Context**

Operational failures can depend on host commands, paths, permissions, and
registry writes, but Skuld should not emit noisy logs or secrets by default.

**Decision**

Add `skuld_observability.py` and enable local debug diagnostics only when
`SKULD_DEBUG` is set.

**Impact**

- Operators can inspect subprocess and registry-write behavior during
  troubleshooting.
- Secret-like field names are redacted before printing.

**Tradeoff**

- Debug output is intentionally text-only and not a structured telemetry
  contract.

**Alternatives rejected**

- Adding a central logging framework before there is a clear operational need.
- Printing command diagnostics unconditionally.

## 2026-04-25 - Formalize Disposable Live Smokes

**Context**

Unit tests fake service-manager interactions. They prove routing and contracts
but cannot prove that real `launchctl` or `systemctl --user` calls work on a
host.

**Decision**

Add disposable live smoke scripts for macOS LaunchAgent and Linux
`systemd --user` operation, including a remote SSH mode for Linux hosts.

**Impact**

- Live validation can exercise `track`, `status`, `doctor`, `restart`, `exec`,
  and `untrack` against services created only for the smoke.
- Smokes are explicit operator actions instead of hidden pre-commit behavior.

**Tradeoff**

- These smokes are host-dependent and not a full OS compatibility matrix.

**Alternatives rejected**

- Claiming live readiness from faked unit tests alone.
- Running live service-manager mutations from the default project doctor.

## 2026-04-25 - Make Linux Stats Timer Safer To Inspect And Remove

**Context**

The journal stats timer mutates system paths with `sudo`, so operators need to
inspect the planned unit files and have a documented removal path.

**Decision**

Add `--dry-run`, `--status`, `--verify`, and `--uninstall` modes to
`scripts/install_runtime_stats_timer.sh`.

**Impact**

- Operators can audit generated units before writing to `/etc/systemd/system`.
- Operators can inspect and verify installed timer state after setup.
- The installed timer, service, and collector copy can be removed without
  deleting stats output.

**Tradeoff**

- The timer remains optional host-level setup outside the Skuld registry.

**Alternatives rejected**

- Installing the timer implicitly from `./skuld`.
- Removing generated stats automatically during uninstall.

## 2026-04-25 - Keep Live Smokes Explicit But Repeatable

**Context**

Disposable live smoke scripts prove real service-manager behavior, but running
them one by one is easy to do inconsistently.

**Decision**

Add `scripts/run_live_smokes.sh` as an explicit orchestrator for selected live
smoke targets.

**Impact**

- Operators can run macOS and Linux smoke checks through one command.
- The default remains non-mutating unless a target flag is provided.

**Tradeoff**

- Live smokes are still host-dependent and remain outside pre-commit.

**Alternatives rejected**

- Running live smokes automatically from the project doctor.
- Hiding service-manager mutations behind default validation commands.

## 2026-04-25 - Make Registry Reads Non-Mutating By Default

**Context**

The registry store could normalize and rewrite `services.json` during read
paths. That made read-only commands such as `list`, `doctor`, and `describe`
less defensible because inspection could also mutate persistent state.

**Decision**

Make `RegistryStore.load()` and backend `load_registry()` normalize in memory by
default. Persist canonical JSON only from explicit write paths such as
`track`, `rename`, `untrack`, `sync`, `save_registry()`, `upsert_registry()`,
or `write_back=True`.

**Impact**

- Read-only CLI commands no longer rewrite an existing registry file just to
  canonicalize formatting, ordering, defaults, or IDs.
- `sync` remains the intentional command for backfilling and persisting registry
  metadata.
- Tests now cover both in-memory normalization and no-write behavior for list
  commands.

**Tradeoff**

- A stale but valid registry can remain non-canonical until an explicit mutating
  command is run.

**Alternatives rejected**

- Keeping canonicalization as a hidden startup side effect.
- Adding a migration framework before there is a versioned registry migration
  need.

## 2026-04-25 - Extract Linux Systemd Adapter First

**Context**

`skuld_linux.py` still mixed command handlers, registry rules, table rendering,
and low-level `systemctl`/`journalctl` mechanics. The clearest backend boundary
was the Linux service-manager adapter.

**Decision**

Add `skuld_linux_systemd.py` for Linux scope normalization, command
construction, user-scope environment setup, and low-level `systemctl`
execution. Keep wrapper functions in `skuld_linux.py` so existing handlers and
tests keep their local patch points.

**Impact**

- Linux service-manager mechanics now have focused unit tests.
- `skuld_linux.py` is smaller without changing CLI behavior.
- Future Linux extraction can proceed around stats and rendering without
  repackaging the project.

**Tradeoff**

- The Linux backend still owns many handlers and runtime/stat functions.
- Wrapper functions remain for compatibility with existing tests and local
  backend readability.

**Alternatives rejected**

- Moving every Linux concern into a package in one step.
- Changing handler call sites broadly before the adapter contract was tested.

## 2026-04-25 - Extract Linux Timer Formatting

**Context**

The Linux backend contained a large block of mostly pure systemd timer parsing
and display formatting. That code is important for operator readability but is
not part of service-manager command execution.

**Decision**

Move systemd duration formatting, `OnCalendar` humanization, repeated directive
parsing, and calendar summary merging into `skuld_linux_timers.py`.

**Impact**

- `skuld_linux.py` is smaller.
- Timer display behavior has focused unit tests.
- Service-manager adapter code remains separate from display formatting.

**Tradeoff**

- `timer_triggers_for_display()` still lives in `skuld_linux.py` because it
  combines registry data with live systemd unit inspection.

**Alternatives rejected**

- Moving all Linux stats and table rendering in the same change.
- Leaving pure formatting code embedded in the Linux backend.

## 2026-04-25 - Extract macOS Launchd Adapter

**Context**

`skuld_macos.py` mixed command handlers, registry rules, process inspection,
and low-level `launchctl` mechanics. After extracting the Linux adapter, the
same boundary was available for macOS.

**Decision**

Add `skuld_macos_launchd.py` for launchd domain/target formatting, low-level
`launchctl` execution, key-value parsing, loaded-state checks, bootstrap,
bootout, and kickstart helpers. Keep wrapper functions in `skuld_macos.py` so
handler code and tests retain stable patch points.

**Impact**

- macOS service-manager mechanics now have focused unit tests.
- `skuld_macos.py` no longer owns low-level launchctl command construction.
- Future macOS work can split process/log/stat concerns separately.

**Tradeoff**

- `skuld_macos.py` still owns local process-tree termination, event files,
  stats, command handlers, and table rendering.
- Wrapper functions remain for compatibility and readability.

**Alternatives rejected**

- Moving all macOS backend code into a package in one pass.
- Changing the public CLI or registry schema during adapter extraction.

## 2026-04-25 - Extract macOS Schedule Helpers

**Context**

The macOS backend contained a self-contained block for parsing Skuld's
documented launchd schedule subset, formatting triggers, and computing next-run
display values.

**Decision**

Move macOS schedule parsing, display formatting, and next-run calculation into
`skuld_macos_schedules.py`.

**Impact**

- `skuld_macos.py` is smaller.
- Schedule behavior has focused unit tests.
- Launchd adapter code remains separate from schedule presentation logic.

**Tradeoff**

- The supported schedule subset is unchanged and still intentionally narrow.

**Alternatives rejected**

- Expanding the launchd schedule grammar during extraction.
- Moving all macOS stats/rendering code in the same change.

## 2026-04-25 - Support macOS External Logs Only When Plist Paths Exist

**Context**

The macOS backend previously rejected logs for all externally tracked launchd
jobs. Some external jobs declare concrete file logs in their plist, which Skuld
can read without owning the job definition.

**Decision**

Allow `skuld logs` for external macOS jobs when the tracked plist declares
`StandardOutPath` or `StandardErrorPath`. Keep the command explicit about
unsupported external jobs with no compatible file paths.

**Impact**

- Skuld can inspect real launchd file logs when the service definition exposes
  them.
- Skuld still does not claim universal macOS log aggregation.

**Tradeoff**

- Jobs using unified logging or application-specific logs remain outside Skuld's
  current log command.

**Alternatives rejected**

- Continuing to reject every external launchd job.
- Claiming support for macOS unified logging before implementing it.
