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

```bash
git clone git@github.com:rod-americo/skuld.git
cd skuld
chmod +x ./skuld
python3 -m py_compile ./skuld ./skuld_cli.py ./skuld_common.py ./skuld_observability.py ./skuld_registry.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py
python3 scripts/project_doctor.py --strict
python3 scripts/project_doctor.py --audit-config
bash -n .githooks/pre-commit scripts/install_git_hooks.sh scripts/install_runtime_stats_timer.sh scripts/smoke_macos_launchd.sh scripts/smoke_linux_systemd_user.sh
```

Live smoke checks are intentionally separate because they mutate disposable
service-manager state:

```bash
scripts/smoke_macos_launchd.sh
scripts/smoke_linux_systemd_user.sh
scripts/smoke_linux_systemd_user.sh --host <ssh-host>
```

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
