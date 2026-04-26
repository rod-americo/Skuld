# Decisions

This file records lightweight architectural and operational decisions. Keep new
entries factual: context, decision, impact, tradeoff, and rejected alternatives.

## 2026-04-26 - Prefer Native Sudo Timestamps And Configurable Table Columns

**Context**

Skuld supported `SKULD_SUDO_PASSWORD` and `.env` lookup for non-interactive
sudo. That solved automation but encouraged local password storage. The compact
service table also had a fixed column policy, so users with different terminal
sizes or operational priorities could not choose the visible columns.

**Decision**

Add `skuld sudo auth` to run the native `sudo -v` prompt and refresh the host
sudo timestamp, and add `skuld sudo forget` to invalidate it. When no explicit
password is configured, Skuld now runs sudo operations with `sudo -n` so it
uses only an already-active native timestamp and does not prompt unexpectedly.

Add `--columns` and `SKULD_COLUMNS` for service-table selection. Explicit
selection preserves the requested order and disables automatic column hiding for
those selected columns; the default layout keeps the existing responsive
auto-hide behavior.

**Impact**

- Users no longer need to store a sudo password for normal local operation.
- Sudo failures are clearer: authenticate with `skuld sudo auth` or adjust host
  sudo policy intentionally.
- `skuld` and `skuld list` can show only the columns an operator cares about.

**Tradeoff**

- Native sudo timestamp behavior depends on host sudo policy and timeout.
- Explicit column selection can produce wider tables if the user selects more
  columns than the terminal can comfortably render.
- `SKULD_SUDO_PASSWORD` remains as a compatibility path, so docs and warnings
  must continue to treat it as sensitive.

**Alternatives rejected**

- Removing `SKULD_SUDO_PASSWORD` immediately, which would be a sharper
  compatibility break than needed for this step.
- Prompting implicitly inside every sudo operation, which is brittle for
  captured commands and non-interactive calls.

## 2026-04-26 - Store User Table Preferences Beside The Registry

**Context**

Operators wanted column selection to be remembered without mixing user
preferences into `services.json`. The service registry is a JSON array and is
the operational safety boundary; changing it into a mixed-purpose object would
be a registry contract break for little gain. The service table also displayed
integer IDs with uneven width once the registry reached two or three digits.

**Decision**

Add `$SKULD_HOME/config.json` as a sibling JSON object for user preferences and
persist table columns through `skuld config columns ...`. Keep `services.json`
as the service registry array. Resolve table columns in this order:
`--columns`, then `$SKULD_HOME/config.json`, then `SKULD_COLUMNS`, then the
automatic default.

Expose `skuld --columns`, `skuld list --columns`, and `skuld config columns`
without arguments as numbered column catalogs. Accept catalog-style selection
with IDs, such as `skuld config columns 1 2 3`, while still accepting
canonical column names and comma-separated values.

Render numeric service IDs with zero padding to the widest visible ID in the
current service table. This changes display only; registry IDs remain positive
integers.

Keep the default compact layout stable, but allow optional columns for direct
registry metadata and best-effort runtime metadata: `target`, `scope`,
`backend`, `pid`, `user`, `restart`, `runs`, `last`, and `next`.

**Impact**

- Users can save column preferences without exporting `SKULD_COLUMNS`.
- Users can choose table columns through the same numbered-selection mental
  model used by `catalog` and `track`.
- The registry contract remains focused on tracked services.
- Long-running registries keep aligned ID output as they pass `9` and `99`
  entries.
- Operators can build deeper local views without forcing every terminal into a
  wider default table.

**Tradeoff**

- There is one more runtime file to document, validate, and exclude from git.
- `SKULD_COLUMNS` remains as an environment fallback for temporary shells and
  automation.

**Alternatives rejected**

- Storing column preferences in `services.json`, which would couple UI
  preferences to the operational registry contract.
- Creating a broader settings system before there are more real settings to
  justify it.

## 2026-04-26 - Keep Stack Providers As Read-Only Wishlist

**Context**

Docker, nginx, and Caddy can explain runtime and route exposure that
`systemd`/`launchd` cannot. Adding them directly as operational backends would
blur Skuld's current safety boundary and create new mutation contracts before
the read-only value is proven.

**Decision**

Document Docker, nginx, and Caddy discovery as wishlist providers. The desired
first step is read-only correlation for `catalog`, `describe`, and optional
table columns. Do not add container operation, proxy config editing, reloads,
certificate handling, or route creation as current behavior.

**Impact**

- The future direction is visible without claiming support that does not exist.
- Skuld can evolve toward better runtime visibility while preserving the
  registry-first service-operation boundary.

**Tradeoff**

- Users still need native Docker/nginx/Caddy tools today.
- Route/container correlation remains a future design problem rather than an
  implied current contract.

**Alternatives rejected**

- Treating Docker as a service-manager backend immediately.
- Editing nginx or Caddy configuration from Skuld before read-only discovery
  has a tested contract.

## 2026-04-26 - Make Backend Entrypoints Thin Composition Roots

**Context**

The Linux and macOS backend files had already lost many low-level
responsibilities, but they still mixed runtime path binding, service-manager
callback wiring, command handlers, parser wiring, and CLI main-loop entry.

**Decision**

Add `skuld_linux_context.py` and `skuld_macos_context.py` for backend
dependency wiring. Add `skuld_linux_handlers.py` and `skuld_macos_handlers.py`
for CLI command-handler orchestration. Keep `skuld_linux.py` and
`skuld_macos.py` as thin composition roots that build the parser, bind one
context to one handler set, and call the shared CLI main loop.

**Impact**

- Backend entrypoints no longer carry large command flows.
- Tests exercise behavior through context and handler boundaries instead of
  backend wrapper patch points.
- Packaging, CI compile checks, and Linux remote smoke payloads explicitly
  include the new modules.

**Tradeoff**

- The context modules are now high-leverage wiring surfaces and must not become
  dumping grounds for low-level adapter or presentation behavior.
- Some backward-compatible direct imports of old backend wrapper functions are
  intentionally no longer preserved as design constraints.

**Alternatives rejected**

- Keeping backend wrapper functions only to preserve old internal patch points.
- Moving all remaining code into one new backend module, which would have made
  the entrypoint thinner without paying down the real dependency boundary.
- Introducing a package-directory refactor in the same step.

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

## 2026-04-26 - Extract Linux Stats And Port Inspection

**Context**

`skuld_linux.py` still mixed command handlers with host overview, unit CPU and
memory usage, cgroup/PID inspection, GPU parsing, and listening-port discovery.
That made the backend harder to reason about and harder to test without
patching large command flows.

**Decision**

Move Linux host overview, unit usage, PID/cgroup inspection, GPU memory parsing,
and port discovery into `skuld_linux_stats.py`. Keep wrapper functions in
`skuld_linux.py` so existing handlers and tests retain stable patch points.

**Impact**

- `skuld_linux.py` is smaller without changing CLI behavior.
- Stats and port parsing now have focused unit tests.
- The Linux smoke payload explicitly includes the new module for remote
  validation.

**Tradeoff**

- `skuld_linux.py` still owns command handlers, target resolution, registry
  schema, table rendering, and journald command-level stats.
- The new module receives low-level command callbacks instead of importing the
  backend, avoiding a circular dependency.

**Alternatives rejected**

- Moving Linux command handlers and table rendering in the same change.
- Letting the stats module import `skuld_linux.py` directly.

## 2026-04-26 - Extract Linux Runtime Helpers

**Context**

`skuld_linux.py` still owned runtime stats JSON parsing, journald execution
counting, restart count display, and journal permission-hint handling. These
responsibilities are operational runtime helpers rather than parser or command
handler logic.

**Decision**

Move Linux runtime stats reads, journald execution counting, restart-count
helpers, and journal permission-hint detection into `skuld_linux_runtime.py`.
Keep wrappers in `skuld_linux.py` so existing handlers and tests retain stable
patch points.

**Impact**

- `skuld_linux.py` is smaller without changing CLI behavior.
- Journald counting and runtime stats parsing have focused unit tests.
- The Linux smoke payload explicitly includes the new module for remote
  validation.

**Tradeoff**

- `skuld_linux.py` still owns the `logs` and `stats` command handlers.
- The runtime module receives command callbacks instead of importing the
  backend directly.

**Alternatives rejected**

- Moving the full `logs` handler in the same change.
- Letting the runtime module import `skuld_linux.py` directly.

## 2026-04-26 - Extract Shared Service Table Policy

**Context**

The Linux and macOS backends duplicated service-table column definitions,
shrink/hide order, table fitting wrappers, row sorting, and host-panel rendering
glue. That duplication made UI policy changes easy to drift across backends.

**Decision**

Move shared service-table column policy, fitting, sorting, and host-panel
helpers into `skuld_tables.py`. Keep backend row assembly local because each
backend still reads different operational state.

**Impact**

- Table width and column policy now live in one module.
- Both backends continue to own backend-specific row data.
- Shared table behavior has focused unit tests.

**Tradeoff**

- Command handlers still call backend-local `_render_services_table()`.
- Row assembly remains backend-specific until more behavior is extracted.

**Alternatives rejected**

- Moving all table row assembly in the same change.
- Keeping duplicated table constants in both backends.

## 2026-04-26 - Extract Linux Service Table Row Assembly

**Context**

The Linux backend still assembled service-table rows inline, mixing command
handler flow with display-state mapping, usage lookup, trigger formatting, and
port lookup.

**Decision**

Move Linux service-table row assembly and state display mapping into
`skuld_linux_view.py`. Keep backend-specific operational reads as callbacks so
the view module does not import `skuld_linux.py`.

**Impact**

- `skuld_linux.py` is smaller.
- Linux row assembly behavior has focused unit tests.
- The Linux smoke payload includes the new view module for remote validation.

**Tradeoff**

- The backend still owns when to render the table and how to handle empty
  registry state.
- macOS row assembly remains backend-local until a separate extraction.

**Alternatives rejected**

- Moving Linux and macOS row assembly together in one change.
- Letting `skuld_linux_view.py` import the backend module directly.

## 2026-04-26 - Extract Linux Target Resolution

**Context**

Linux target resolution still lived inline in `skuld_linux.py`, mixing backend
command flow with display-name lookup, numeric ID lookup, scoped unit-name
lookup, ambiguity errors, and multi-target de-duplication.

**Decision**

Move Linux target-resolution rules into `skuld_linux_targets.py`. Keep actual
registry reads and Linux-specific normalization in `skuld_linux.py` and pass
them into the target module as callbacks.

**Impact**

- Linux target resolution has focused unit tests.
- `skuld_linux.py` is smaller and delegates selection rules to a named module.
- Remote Linux smoke packaging includes the new target module.

**Tradeoff**

- `skuld_linux.py` still exposes wrapper functions so existing command handlers
  do not need a broad rewrite.
- macOS target resolution remains backend-local until a separate extraction.

**Alternatives rejected**

- Creating a cross-platform target module now. Linux and macOS identifiers have
  different scope semantics, so a shared abstraction would add risk before both
  sides have independent tests.

## 2026-04-26 - Extract Detail View Presenters

**Context**

Linux and macOS command handlers still mixed operational reads with
line-oriented stdout formatting for detail views such as `status`, `stats`, and
`describe`.

**Decision**

Move selected line construction into `skuld_linux_presenters.py` and
`skuld_macos_presenters.py`. Keep host reads, registry resolution, and command
side effects in the backend modules.

**Impact**

- Detail-view formatting has focused unit tests.
- Backend command handlers are smaller and easier to inspect.
- The packaged console entrypoint includes the presenter modules.

**Tradeoff**

- This is not a full command-handler extraction. Operational flows such as
  `track`, `sync`, `doctor`, `logs`, and start/stop/restart remain in the
  backend modules.

**Alternatives rejected**

- Moving every command handler at once. That would mix presentation cleanup,
  host mutation paths, and registry writes in one high-risk change.

## 2026-04-26 - Extract Registry And Detail Command Helpers

**Context**

`rename` and `untrack` are registry-only command paths, `doctor` is a read-only
operational check, `logs` is a read-only operational output flow, and
`status`/`stats`/`describe` are detail-view flows over service-manager and
runtime reads. Their object reconstruction, registry removal, diagnostic
orchestration, log command flow, and detail command orchestration still lived
inline in the backend files next to service-manager operations.

**Decision**

Move Linux and macOS registry-only command helpers plus `doctor`, `logs`,
`status`, `stats`, and `describe` orchestration into
`skuld_linux_commands.py` and `skuld_macos_commands.py`. Keep argument parsing,
target resolution, and user-visible command registration in the backend
modules.

**Impact**

- Registry mutation behavior has focused unit tests.
- Detail command orchestration has focused unit tests on both backends.
- The backend command handlers for `rename`, `untrack`, `doctor`, `logs`,
  `status`, `stats`, and `describe` are smaller.
- The packaged console entrypoint and Linux remote smoke payload include the new
  command modules.

**Tradeoff**

- Service-manager mutating commands such as start, stop, restart, exec, track,
  and sync remain backend-local because they need narrower extraction and
  live-smoke coverage.

**Alternatives rejected**

- Moving every command handler into command modules in one step.
- Creating a single cross-platform command module while Linux and macOS service
  dataclasses still have different fields.

## 2026-04-26 - Extract Host-Mutating Service Actions

**Context**

`start`, `stop`, `restart`, and `exec` mutate host service-manager state. They
still lived inline in the backend files after read-only command flows had been
extracted, which kept high-risk operational behavior mixed with parser and
registry code.

**Decision**

Move Linux lifecycle and exec orchestration into `skuld_linux_actions.py`, and
move macOS launchd lifecycle and exec orchestration into
`skuld_macos_actions.py`. Keep target resolution and backend adapter functions
in the backend modules.

**Impact**

- Timer-versus-service routing on Linux has focused unit tests.
- macOS bootstrap, bootout, process cleanup, kickstart, and failure behavior
  have focused unit tests.
- Backend command handlers for host-mutating actions now resolve targets and
  inject backend callbacks instead of owning the action flow.

**Tradeoff**

- The action modules still use object-shaped services because backend-specific
  dataclasses remain in the backend files.
- Live behavior still requires explicit disposable smokes because unit tests
  intentionally fake `systemctl` and `launchctl`.

**Alternatives rejected**

- Folding action behavior into `skuld_linux_commands.py` and
  `skuld_macos_commands.py`, which would make those modules the next broad
  buckets.
- Creating a cross-platform action abstraction before Linux timers and macOS
  launchd schedules have compatible semantics.

## 2026-04-26 - Extract Backend-Specific Service Models

**Context**

Helper modules were forced to use object-shaped services partly because the
backend-specific dataclasses and registry normalization lived inside the large
backend orchestration files.

**Decision**

Move Linux service dataclasses, registry normalization, and identifier helpers
into `skuld_linux_model.py`. Move macOS service dataclasses and registry
normalization into `skuld_macos_model.py`, while keeping macOS runtime path
resolution injected from `skuld_macos.py` because it depends on patched
host-local paths in tests and operation.

**Impact**

- Backend model contracts are importable without importing parser and command
  orchestration.
- Registry normalization tests continue to exercise the same backend public
  functions through thin wrappers.
- Future helper modules can type against backend-specific service models rather
  than accepting opaque objects.

**Tradeoff**

- macOS still keeps a small `normalize_service()` wrapper in `skuld_macos.py`
  to pass host-local path callbacks into the model normalizer.
- Linux and macOS models remain separate because their registry fields and
  identity rules differ.

**Alternatives rejected**

- Creating one cross-platform service dataclass and flattening real backend
  differences.
- Moving macOS runtime path roots into the model module and breaking isolated
  state patching.

## 2026-04-26 - Extract Registry Sync Backfill

**Context**

`sync` reads live service-manager metadata and may rewrite the registry. Keeping
that backfill logic inside the backend files mixed persistence decisions with
parser wiring and command dispatch.

**Decision**

Move Linux systemd metadata backfill into `skuld_linux_sync.py` and macOS
launchd plist metadata backfill into `skuld_macos_sync.py`. Keep backend
wrappers responsible for injecting registry, path, and service-manager
callbacks.

**Impact**

- Sync behavior has focused unit tests for targeted updates and no-change
  write avoidance.
- Backends keep the public `sync_registry_from_*` functions for existing tests
  and command wiring.
- Remote Linux smoke payload and package metadata now include the sync modules.

**Tradeoff**

- The sync modules still depend on backend-specific service models.
- `track` and catalog discovery remain backend-local and are the next larger
  extraction target.

**Alternatives rejected**

- Treating sync as a generic registry update operation across both backends.
- Moving runtime path ownership into sync modules.

## 2026-04-26 - Extract Catalog And Track Orchestration

**Context**

Catalog discovery and `track` were still backend-heavy. Linux mixed systemd
catalog parsing, scoped target resolution, service/timer metadata reads, and
registry entry construction. macOS mixed launchd catalog parsing, hint
rendering, launchd metadata reads, and registry entry construction.

**Decision**

Move Linux catalog and track behavior into `skuld_linux_catalog.py`, and move
macOS catalog and track behavior into `skuld_macos_catalog.py`. Keep backend
wrappers for public function names and host adapter injection.

**Impact**

- Discovery parsing and `track` metadata capture have focused unit tests.
- Backends retain compatibility for existing tests that patch wrapper
  functions such as `list_discoverable_services()` and
  `discover_launchd_services()`.
- Package metadata, CI compile lists, and the Linux remote smoke payload now
  include the catalog modules.

**Tradeoff**

- The backend files still own thin wrapper functions for compatibility and
  callback injection.
- `DiscoverableService` remains in backend-specific model modules instead of
  catalog modules so callers use one backend contract import.

**Alternatives rejected**

- Moving parser subcommand registration together with catalog behavior before
  parser-specific tests existed.
- Creating one cross-platform catalog module despite different systemd and
  launchd discovery semantics.

## 2026-04-26 - Extract Backend Parser Wiring

**Context**

The Linux and macOS backends still carried large `argparse` construction blocks
after command, model, sync, action, and catalog behavior had been extracted.
That made the backend files harder to audit and left CLI option contracts mixed
with host-runtime callbacks.

**Decision**

Move Linux parser construction into `skuld_linux_parser.py` and macOS parser
construction into `skuld_macos_parser.py`. Keep handler functions injected by
the backend modules so parser modules do not import runtime state, registries,
or service-manager adapters.

**Impact**

- CLI flags and compatibility aliases have focused unit tests.
- Backend files now expose a thin `build_parser()` delegation instead of owning
  the full subcommand tree.
- Package metadata, CI compile lists, documented validation commands, and the
  Linux remote smoke payload include the parser modules.

**Tradeoff**

- Parser modules still duplicate common subcommands where backend help text and
  behavior differ.
- Backend modules still own many thin wrappers to preserve existing patch
  points and avoid a behavior-changing extraction.

**Alternatives rejected**

- Creating one cross-platform parser that hides systemd and launchd option
  differences.
- Letting parser modules import backend modules directly, which would create
  circular dependencies and make the parser harder to test.

## 2026-04-26 - Move Linux Timer Metadata Reads Into Timer Module

**Context**

Linux timer display still lived in `skuld_linux.py` after the parser and most
command flows had been extracted. The backend mixed compact table trigger
rendering with live `systemctl show` reads, timer unit fallback parsing, and
registry schedule fallback behavior.

**Decision**

Move Linux timer metadata reads and trigger-display construction into
`skuld_linux_timers.py`. Keep backend wrappers that inject `systemctl`,
unit-existence, schedule, and text-clipping callbacks.

**Impact**

- Timer behavior has focused tests outside the backend module.
- `skuld_linux.py` keeps the public function names used by existing tests and
  command wiring while no longer owning the timer decision tree.
- Timer parsing and live metadata reads now live in one responsibility module.

**Tradeoff**

- The timer module uses object-shaped services for display because the Linux
  service dataclass remains backend-specific.
- Backend wrappers remain necessary until public patch points are intentionally
  narrowed.

**Alternatives rejected**

- Moving timer display into the table-view module, which would mix service-table
  assembly with systemd timer semantics.
- Removing backend wrappers and breaking tests that patch existing function
  names directly.

## 2026-04-26 - Move macOS Path Derivation Into Path Module

**Context**

The macOS backend still owned launchd label formatting, plist path resolution,
and Skuld runtime path derivation for jobs, logs, events, and wrapper scripts.
Those rules are core operational paths but do not require host command access.

**Decision**

Move macOS label and path derivation into `skuld_macos_paths.py`. Keep backend
wrappers that inject the current `SKULD_HOME` and current user home so existing
tests can continue isolating runtime state by patching backend constants.

**Impact**

- macOS path rules have focused unit tests.
- Backend code no longer owns pure path construction.
- Package metadata, CI compile lists, and documented validation commands
  include the new module.

**Tradeoff**

- Backend wrappers remain because they are the compatibility surface used by
  existing tests and callback injection.
- Daemon paths still point under `/Library/Application Support/skuld`; the
  module documents current behavior, not a new configuration system.

**Alternatives rejected**

- Moving path rules into `skuld_macos_runtime.py`, which already owns event and
  log file parsing rather than label/path construction.
- Removing backend constants and forcing all tests to patch the new module.

## 2026-04-26 - Share Sudo Command Orchestration

**Context**

Linux and macOS duplicated the `sudo check` and `sudo run` CLI flows. The
duplication was not service-manager-specific; it only checked whether sudo can
run non-interactively, warned about `SKULD_SUDO_PASSWORD`, and executed one
operator-provided command through the existing backend sudo wrapper.

**Decision**

Move the shared CLI orchestration into `skuld_sudo.py`. Keep backend wrappers
for parser handler registration, password lookup, stdout messaging, and
backend-specific `run_sudo` functions.

**Impact**

- The sudo command behavior has focused unit tests.
- Linux and macOS backends no longer duplicate the same sudo command flow.
- The Linux remote smoke payload includes the shared sudo module because the
  Linux backend imports it.

**Tradeoff**

- Service-manager-specific sudo decisions remain in `skuld_linux_systemd.py`
  and `skuld_macos_launchd.py`.
- `SKULD_SUDO_PASSWORD` remains a short-lived local convenience, not production
  credential management.

**Alternatives rejected**

- Moving all sudo behavior into `skuld_common.py`, which would mix subprocess
  primitives with CLI command orchestration.
- Removing backend wrappers and changing parser handler registration.

## 2026-04-26 - Keep Linux Name Rules In The Model

**Context**

Linux service-name normalization and display-name suggestion rules still lived
in `skuld_linux.py` after the Linux dataclasses and registry validation had
moved into `skuld_linux_model.py`. Those functions define identity-adjacent
behavior and do not need runtime host access.

**Decision**

Move `normalize_service_name()`, `normalize_target_token()`, and
`suggest_display_name()` into `skuld_linux_model.py`. Keep the same names
available to the backend by importing them from the model.

**Impact**

- Linux name normalization has focused model tests.
- The backend no longer owns regex validation or name-suggestion logic.
- Existing backend call sites and patch points continue to resolve the same
  public names.

**Tradeoff**

- Interactive prompting remains in the backend because it is CLI I/O, not a
  pure model rule.
- Linux and macOS name suggestion still differ because the backend service
  identifiers differ.

**Alternatives rejected**

- Moving name rules into target resolution, which would mix identity
  normalization with registry lookup.
- Creating one cross-platform naming helper before Linux systemd units and
  macOS launchd labels share enough semantics.

## 2026-04-26 - Keep macOS Display-Name Suggestions In The Model

**Context**

The macOS backend still owned display-name suggestion rules for launchd labels.
That logic is pure label normalization and validation; it does not require
launchctl, filesystem access, or registry state.

**Decision**

Move `suggest_display_name()` into `skuld_macos_model.py` and import the same
public name into the backend.

**Impact**

- macOS display-name suggestion behavior has focused model tests.
- The backend no longer owns launchd-label token heuristics.
- Existing `track` wiring still calls `suggest_display_name` through the
  backend namespace.

**Tradeoff**

- Interactive prompting remains in the backend because it depends on stdin.
- Linux and macOS suggestion rules remain separate because systemd unit names
  and launchd labels differ.

**Alternatives rejected**

- Combining Linux and macOS naming rules into one helper before their behavior
  is actually common.
- Moving suggestions into catalog tracking, which would mix metadata capture
  with naming policy.

## 2026-04-26 - Move Backend Registry Wiring Into Registry Modules

**Context**

Both backend files still constructed `RegistryStore` directly and owned registry
lookup helpers. macOS also initialized the runtime stats JSON from the backend.
That kept persistence wiring mixed into files that already coordinate parser,
command, adapter, and table callbacks.

**Decision**

Move Linux registry storage and lookup helpers into `skuld_linux_registry.py`.
Move macOS registry storage, runtime stats file initialization, and lookup
helpers into `skuld_macos_registry.py`. Keep backend wrappers so existing tests
and callback injection continue to patch backend-level functions.

**Impact**

- Registry wiring now has focused backend-specific unit tests.
- Backend files no longer construct `RegistryStore` directly.
- Package metadata, CI compile lists, documented validation commands, and the
  Linux remote smoke payload include the new registry modules.

**Tradeoff**

- Backend wrappers remain to preserve compatibility and host-local constants
  such as `SKULD_HOME`, `REGISTRY_FILE`, and `RUNTIME_STATS_FILE`.
- macOS registry normalization still receives a callback for path derivation,
  because runtime paths are intentionally patchable through backend wrappers.

**Alternatives rejected**

- Moving backend-specific registry behavior into the generic
  `skuld_registry.py`, which would erase real Linux/macOS schema differences.
- Removing backend wrappers and requiring callers to patch the new modules
  directly.

## 2026-04-26 - Move Service Table Flow Into View Modules

**Context**

Linux and macOS row assembly already lived in `skuld_linux_view.py` and
`skuld_macos_view.py`, but the backend files still owned the table rendering
flow: empty-registry hinting, host panel rendering, row sorting, table fitting,
and final table output.

**Decision**

Move service-table rendering flow into the existing backend-specific view
modules. Keep backend wrappers that inject registry, host, service-manager, and
table callbacks.

**Impact**

- Table flow has focused tests for both empty registries and populated
  registries.
- Backend files no longer own compact table orchestration.
- View modules now own both row assembly and the table pipeline they feed.

**Tradeoff**

- The view modules still receive many callbacks because host operations remain
  backend-specific and patchable.
- The `compact` flag remains accepted by the flow even though current table
  rendering does not branch on it.

**Alternatives rejected**

- Moving table flow into `skuld_tables.py`, which would mix generic table
  fitting with backend-specific service state reads.
- Removing backend wrappers and changing `list_services_compact()` callers.

## 2026-04-26 - Share Log Line Argument Resolution

**Context**

Linux and macOS duplicated the same CLI rule for log line counts: prefer
`--lines`, then positional `lines_pos`, then a default.

**Decision**

Move that rule into `skuld_common.resolve_lines_arg()` while keeping backend
wrappers for existing call sites.

**Impact**

- The shared rule has a focused unit test.
- Linux and macOS log commands resolve line counts through one implementation.

**Tradeoff**

- Backends still expose `resolve_lines_arg()` wrappers because existing command
  code and tests patch backend-level helpers.

**Alternatives rejected**

- Leaving the duplication in place after other shared CLI helper behavior had
  already moved to `skuld_common.py`.

## 2026-04-26 - Extract macOS Service Table Row Assembly

**Context**

The macOS backend still assembled service-table rows inline, mixing command
handler flow with display-state mapping, event stats reads, PID lookup, usage
lookup, schedule display, and port lookup.

**Decision**

Move macOS service-table row assembly and state display mapping into
`skuld_macos_view.py`. Keep backend-specific operational reads as callbacks so
the view module does not import `skuld_macos.py`.

**Impact**

- `skuld_macos.py` is smaller.
- macOS row assembly behavior has focused unit tests.
- The packaged console entrypoint includes the new view module.

**Tradeoff**

- The backend still owns when to render the table and how to handle empty
  registry state.
- `read_event_stats(service)` remains part of row assembly because the prior
  backend loop called it while building the table.

**Alternatives rejected**

- Removing the event stats read as apparently unused. That could silently alter
  runtime side effects.
- Letting `skuld_macos_view.py` import the backend module directly.

## 2026-04-26 - Extract macOS Target Resolution

**Context**

macOS target resolution still lived inline in `skuld_macos.py`, mixing backend
command flow with launchd label lookup, display-name lookup, numeric ID lookup,
discoverable catalog lookup, and multi-target de-duplication.

**Decision**

Move macOS target-resolution rules into `skuld_macos_targets.py`. Keep actual
registry reads, launchd catalog discovery, and validation in `skuld_macos.py`
and pass them into the target module as callbacks.

**Impact**

- macOS target resolution has focused unit tests.
- `skuld_macos.py` is smaller and delegates selection rules to a named module.
- The packaged console entrypoint includes the new target module.

**Tradeoff**

- `skuld_macos.py` still exposes wrapper functions so existing command handlers
  do not need a broad rewrite.
- Linux and macOS target modules remain separate because their identifier and
  scope semantics differ.

**Alternatives rejected**

- Creating a shared cross-platform target module now. That would obscure the
  real differences between systemd scoped unit names and launchd labels.

## 2026-04-26 - Boot Out macOS Smoke By Service Target

**Context**

`scripts/smoke_macos_launchd.sh` cleaned up the disposable LaunchAgent by plist
path. Live validation showed that this unloads the job and removes files, but
can leave `io.skuld.smoke.* => enabled` entries in `launchctl print-disabled`.

**Decision**

Clean up macOS smoke jobs with `launchctl bootout gui/<uid>/<label>` first,
then fall back to `launchctl bootout gui/<uid> <plist>` if the service-target
bootout is unavailable. Also avoid calling `launchctl enable` after a
successful bootstrap; only enable and retry when the bootstrap error indicates
the service is disabled.

**Impact**

- New macOS smoke runs avoid adding persistent launchd override entries.
- The fallback keeps compatibility with hosts where path-based bootout is still
  needed.
- Disabled launchd jobs can still be re-enabled when the bootstrap failure
  actually indicates disabled state.

**Tradeoff**

- Existing historical smoke override entries may remain in launchd's persistent
  view because `launchctl remove` does not clear them after the jobs are already
  unloaded and their plists are gone.

**Alternatives rejected**

- Editing launchd override storage directly. That is too invasive for a smoke
  cleanup path.

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

## 2026-04-26 - Extract macOS Process Helpers

**Context**

`skuld_macos.py` still mixed command handlers with process-tree discovery,
process termination, CPU/memory display, host overview, and listening-port
inspection. Those responsibilities are operationally important but separable
from parser and registry behavior.

**Decision**

Move macOS process-tree, termination, host overview, CPU/memory, and port
helpers into `skuld_macos_processes.py`. Keep wrappers in `skuld_macos.py` so
existing command handlers and tests retain stable patch points.

**Impact**

- `skuld_macos.py` is smaller without changing CLI behavior.
- macOS process and host-inspection behavior has focused unit tests.
- Launchd adapter, schedule helpers, and process helpers now have separate
  modules.

**Tradeoff**

- `skuld_macos.py` still owns command handlers, registry schema, event stats,
  log path resolution, and CLI table rendering.
- The process module receives command callbacks instead of importing the
  backend directly.

**Alternatives rejected**

- Moving macOS logs and event stats in the same change.
- Letting the process module import `skuld_macos.py` directly.

## 2026-04-26 - Extract macOS Runtime Helpers

**Context**

`skuld_macos.py` still owned event JSONL parsing, runtime stats JSON updates,
recent-run PID extraction, file-log path resolution, and `tail` invocation.
Those responsibilities are tied to runtime files rather than parser or launchd
adapter behavior.

**Decision**

Move macOS event stats, runtime stats updates, recent-run PID extraction,
file-log path resolution, and tail helpers into `skuld_macos_runtime.py`. Keep
the `logs` command handler in `skuld_macos.py` because it still coordinates CLI
arguments, stdout labels, and follow-mode threads.

**Impact**

- `skuld_macos.py` is smaller without changing CLI behavior.
- Runtime file parsing and log path resolution have focused unit tests.
- macOS process, launchd, runtime, and schedule responsibilities now have
  separate modules.

**Tradeoff**

- `skuld_macos.py` still owns command handlers, target resolution, registry
  schema, and table rendering.
- The runtime module receives paths and callbacks instead of importing the
  backend directly.

**Alternatives rejected**

- Moving the entire `logs` command handler in the same change.
- Letting the runtime module import `ManagedService` or `skuld_macos.py`
  directly.

## 2026-04-26 - Add Standard Python Packaging Metadata

**Context**

Skuld could run from a checkout with `./skuld`, but there was no installable
console command or release validation path. That limited product/distribution
maturity and made package-level rollback impossible to document.

**Decision**

Add `pyproject.toml` with setuptools metadata, expose the console script
`skuld = "skuld_entrypoint:main"`, and move backend selection into the importable
`skuld_entrypoint.py` module. Keep `./skuld` as a thin development wrapper
around the same entrypoint.

**Impact**

- `pipx install .` and wheel-based installation are supported from the checkout.
- Direct `./skuld` execution continues to work.
- Install, uninstall, release validation, and rollback are documented.

**Tradeoff**

- The project remains root-module based instead of a `src/` package.
- Version still exists in `pyproject.toml` and backend constants until a single
  generated version source is introduced.

**Alternatives rejected**

- Moving the whole repository into `src/skuld/` during the packaging change.
- Removing `./skuld` before existing checkout workflows have migrated.

## 2026-04-26 - Add Non-Mutating CI Matrix

**Context**

Local validation and live smokes existed, but routine validation was not
enforced by CI. Running live service-manager smokes automatically would mutate
host state and require environment-specific permissions.

**Decision**

Add GitHub Actions CI for Ubuntu and macOS across Python 3.9 and 3.12. The
workflow runs syntax checks, unit tests, gate/doctor validation, shell syntax,
checkout CLI checks, wheel build, and packaged console command checks.

**Impact**

- Pull requests and pushes can prove the non-mutating validation baseline.
- Package metadata is continuously exercised on Linux and macOS runners.
- Live smokes remain explicit manual operations.

**Tradeoff**

- CI does not prove real `systemctl --user` or `launchctl` mutation paths.
- OS-version and distro compatibility beyond hosted runners remains a manual
  validation concern.

**Alternatives rejected**

- Running live smoke scripts automatically in CI.
- Keeping packaging validation as a release-only manual step.

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
