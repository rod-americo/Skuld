# Install

Skuld can still be run directly from a checkout:

```bash
chmod +x ./skuld
./skuld --help
```

For user-level installation from a checkout, prefer `pipx`:

```bash
pipx install .
skuld --help
```

For a local virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
skuld --help
```

The package exposes the console command `skuld` through
`skuld_entrypoint:main`. The root `./skuld` script remains for development and
direct checkout operation.

## Runtime State

Installing the package does not move or migrate runtime state.

Default registry paths remain:

- Linux: `~/.local/share/skuld/services.json`
- macOS: `~/Library/Application Support/skuld/services.json`

Back up the registry file before uninstalling or replacing a host if tracked
service aliases matter.

## Uninstall

With `pipx`:

```bash
pipx uninstall skuld-service-cli
```

With `pip` inside the environment where it was installed:

```bash
python3 -m pip uninstall skuld-service-cli
```

Uninstalling the Python package does not delete registry files, launchd plists,
systemd units, logs, stats, or the optional Linux journal stats timer.
