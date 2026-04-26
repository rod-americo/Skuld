## Purpose

What problem does this PR solve?

## Changes

- 

## Validation

Commands/tests run:

```bash
python3 -m py_compile ./skuld ./skuld_entrypoint.py ./skuld_cli.py ./skuld_common.py ./skuld_linux_systemd.py ./skuld_linux_stats.py ./skuld_linux_timers.py ./skuld_macos_launchd.py ./skuld_macos_processes.py ./skuld_macos_schedules.py ./skuld_observability.py ./skuld_registry.py ./skuld_linux.py ./skuld_macos.py ./scripts/skuld_journal_stats_collector.py ./scripts/check_project_gate.py ./scripts/project_doctor.py tests/*.py
python3 -m unittest discover -s tests
./skuld --help
python3 scripts/check_project_gate.py
python3 scripts/project_doctor.py --strict
```

Additional checks:

- [ ] CLI behavior verified
- [ ] Packaged console command verified when packaging changed
- [ ] Live smoke run when host operation changed
- [ ] README updated (if command/UX changed)

## Risk / Impact

- [ ] Low
- [ ] Medium
- [ ] High

Notes:
