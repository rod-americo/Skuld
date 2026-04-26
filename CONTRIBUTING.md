# Contributing to Skuld

Skuld exists to reduce friction when managing selected local services through
`systemd` or `launchd`, while keeping operations explicit and auditable.

## Scope and Principles

- Keep the tool practical and host-local.
- Preserve the registry boundary: Skuld operates services it tracks.
- Prefer clear behavior over magical automation.
- Preserve the core routing model:
  - daemon-like services act on `.service` on Linux
  - timer jobs act on `.timer` for start/stop/restart when a real timer exists
  - immediate execution uses `exec` on the service target
- Keep backward compatibility when possible.

## Local Development

The README is the canonical place for the full non-mutating validation command
set. Run the validation block in `README.md` before proposing changes that
touch behavior, packaging, docs, operations, or service-manager integration.

```bash
git clone git@github.com:rod-americo/skuld.git
cd skuld
chmod +x ./skuld
./skuld --help
```

Live smoke checks are intentionally separate because they mutate disposable
service-manager state:

```bash
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
scripts/run_live_smokes.sh --macos --linux-host <ssh-host>
```

For Linux live validation, `vidar` is an available SSH host:

```bash
scripts/smoke_linux_systemd_user.sh --host vidar
scripts/run_live_smokes.sh --macos --linux-host vidar
```

`vidar` also keeps a Skuld checkout at `~/.local/src/skuld/`. When remote
iteration is faster with an in-place checkout than with ad-hoc copy over SSH,
update that repository with `git pull` and validate there.

## Pull Request Expectations

- One logical change per PR.
- Include:
  - purpose
  - key changes
  - exact validation commands used
  - behavior and risk notes, especially for start, stop, restart, exec, sudo,
    registry, and backend integration changes
- Update `README.md` when commands or user-visible behavior change.
- Update `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, or
  `docs/OPERATIONS.md` when architecture, contracts, runtime, or operations
  change.

## Coding Notes

- Python standard library is preferred unless a dependency is clearly justified.
- Keep CLI messages and docs in English.
- Do not introduce machine-specific paths in docs.
- Avoid destructive actions by default.
- Do not reintroduce service definition creation or editing without explicit
  contracts, operations docs, and tests.
