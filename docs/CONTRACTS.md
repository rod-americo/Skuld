# Contracts

## 1. Purpose

This document records Skuld's canonical inputs, outputs, identifiers,
invariants, and external integration assumptions.

## 2. Canonical Inputs

| Name | Origin | Format | Required | Notes |
| --- | --- | --- | --- | --- |
| CLI command | Operator | argv parsed by `argparse` | yes | Commands are parsed by backend parser modules and routed through backend handlers. |
| Registry file | Skuld runtime path | JSON array | yes for operations | Created as `[]` if missing. Invalid JSON fails explicitly. |
| Service catalog | `systemd` or `launchd` | command output | yes for discovery | Linux uses `systemctl list-unit-files`; macOS uses `launchctl list`. |
| Service state | `systemd` or `launchd` | command output | yes for operation views | Used by list, status, doctor, describe, and sync. |
| Logs | `journalctl` or files | text stream | command-specific | Linux supports journal filters; macOS reads compatible log files or launchd plist log paths. |
| Sudo timestamp | native `sudo` cache | host-local state | no | Refreshed with `skuld sudo auth`; used through `sudo -n`. |
| Sudo credential | env or `.env` | string | no | Compatibility path only; `SKULD_SUDO_PASSWORD` is sensitive and should be short-lived. |
| Table columns | CLI or env | comma-separated keys | no | `--columns` or `SKULD_COLUMNS`; default keeps automatic layout. |
| Debug switch | env | boolean-like string | no | `SKULD_DEBUG` enables redacted stderr diagnostics. |
| Runtime stats | stats JSON or event files | JSON | no | Used to show execution/restart counters when present. |

## 3. Canonical Outputs

| Name | Destination | Format | Guarantees |
| --- | --- | --- | --- |
| CLI output | stdout/stderr | text tables or key-value lines | Best-effort readable output; not a stable machine API. |
| Registry update | Skuld registry path | canonical JSON array | Written by mutating commands with pretty JSON, stable ordering, trailing newline, and normalized IDs. |
| Backend action | `systemctl` or `launchctl` | service-manager operation | Only targets that resolve from the registry should be operated. |
| Log output | stdout/stderr | text stream | Mirrors backend/file log availability and permissions. |
| Debug output | stderr | redacted text lines | Opt-in only; not a stable machine API. |
| Linux journal stats | configured stats path | JSON object | Collector writes atomically when run. |
| macOS event stats | application support path | JSON or JSONL | Available only for compatible Skuld-managed entries. |

## 4. Identifiers And Keys

| Concept | Canonical field | Notes |
| --- | --- | --- |
| Registry row | `id` | Positive integer normalized by `load_registry()`. User-friendly selection key. |
| Human-facing name | `display_name` | Unique within registry and valid under `NAME_RE`. |
| Linux backend target | `scope` plus `name` | `scope` is `system` or `user`; `name` excludes `.service` and `.timer`. |
| macOS backend target | `launchd_label` or `name` | Labels come from `launchctl`; display names are Skuld-local aliases. |
| Linux service unit | `<name>.service` | Used for immediate execution, status, logs, and stats. |
| Linux timer unit | `<name>.timer` | Used for start/stop/restart only when schedule metadata and timer exist. |
| macOS scope | `agent` or `daemon` | `agent` maps to the current GUI user domain; `daemon` maps to system domain. |

## 5. Registry Schemas

### Linux `ManagedService`

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Backend base name without `.service` or `.timer`. |
| `scope` | yes | `system` or `user`; defaults normalize through `normalize_scope()`. |
| `exec_cmd` | yes | Captured from `ExecStart` or fallback service unit. |
| `description` | yes | Captured from backend metadata or generated tracking description. |
| `display_name` | yes | Operator-facing alias. |
| `schedule` | no | Timer schedule metadata when known. |
| `working_dir` | no | Captured from backend service metadata when available. |
| `user` | no | Captured from backend service metadata when available. |
| `restart` | no | Captured restart policy or `on-failure`. |
| `timer_persistent` | no | Boolean timer metadata, default `true`. |
| `id` | yes after normalization | Positive integer assigned by Skuld. |

### macOS `ManagedService`

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Usually the launchd label for tracked external jobs. |
| `exec_cmd` | yes | Captured program or fallback label. |
| `description` | yes | Captured label and state summary. |
| `display_name` | yes | Operator-facing alias. |
| `launchd_label` | yes after normalization | Launchd label used for `launchctl`. |
| `plist_path_hint` | no | Captured plist path when inspectable. |
| `managed_by_skuld` | yes after normalization | External tracked jobs are currently stored as `false`. |
| `schedule` | no | Legacy/compatible schedule metadata. |
| `working_dir` | no | Working directory when known. |
| `user` | no | Only valid for daemon scope. |
| `restart` | no | Restart policy metadata, default `on-failure`. |
| `timer_persistent` | no | Schedule metadata, default `true`. |
| `id` | yes after normalization | Positive integer assigned by Skuld. |
| `backend` | yes after normalization | Currently `launchd`. |
| `scope` | yes | `agent` or `daemon`. |
| `log_dir` | no | Relevant only for compatible Skuld-managed entries. |

## 6. Events Or Pipeline Steps

| Step | Input | Output | Expected Failures |
| --- | --- | --- | --- |
| Dispatch | `./skuld` invocation | backend `main()` call | Unsupported or missing backend module. |
| Load registry | registry JSON | normalized service list | Missing required fields, invalid JSON, duplicate display names. |
| Discover | service-manager catalog | discoverable entries | Missing `systemctl`, unavailable user manager, launchctl visibility limits. |
| Track | catalog ID or backend name | registry entry | Unknown service, ambiguous Linux scope, duplicate alias. |
| Operate | registry target | backend action | Missing unit/plist, permission failure, service-manager command failure. |
| Sync | registry entry and backend metadata | updated registry | Backend metadata missing or inaccessible. |
| Doctor | registry plus backend state | issues or success text | Backend unavailable, missing service, schedule mismatch, permission issues. |
| Stats | registry target plus logs/events | counters | Journal retention, permission limits, missing event files. |

## 7. Invariants

- Skuld commands must resolve operational targets from the registry.
- `untrack` removes registry state only; it must not remove backend service
  definitions.
- Normal CLI registry loads validate and normalize in memory without rewriting
  an existing registry file.
- Registry canonicalization is persisted by explicit mutating commands or by
  `RegistryStore.load(write_back=True)` in code paths that intentionally write.
- Linux `system:name` and `user:name` are distinct backend identities.
- The same `display_name` cannot refer to two registry entries.
- `SKULD_SUDO_PASSWORD` must never be logged.
- Sudo operations without an explicit password must use the native sudo
  timestamp non-interactively through `sudo -n`.
- Explicit table-column selection must preserve requested column order and must
  reject unknown column names.
- macOS `--since`, `--timer`, `--output`, and `--plain` are compatibility flags
  on logs; some are ignored or rejected as documented by help text and runtime
  behavior.

## 8. Assumptions Not Fully Validated

- Behavior across Linux distributions and systemd versions is not covered by an
  automated compatibility matrix.
- macOS behavior is based on locally visible launchd jobs and may vary by
  domain, permissions, and plist visibility.
- Runtime stats depend on journal retention, event file availability, and host
  permissions.
- Native sudo timestamp availability depends on host sudo policy, TTY
  availability for `skuld sudo auth`, and the sudo timeout configured by the
  host.
- Live smoke scripts prove disposable local service-manager paths on hosts where
  `launchd` or `systemd --user` is available, but they are not a distribution or
  OS-version compatibility matrix.

## 9. Contract Breaks

Record changes here when they require registry migration, integration changes,
restart procedures, or new validation.

- 2026-04-25: Structural documentation baseline added; no runtime registry
  schema change was made.
- 2026-04-25: Added opt-in `SKULD_DEBUG` diagnostics, common CLI runner, and
  no-write registry normalization for audits; no registry schema change was
  made.
- 2026-04-25: Made no-write registry normalization the default for read paths;
  explicit mutating commands still persist canonical JSON.
- 2026-04-26: Added native sudo timestamp commands and configurable
  service-table columns; no registry schema change was made.
