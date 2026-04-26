# PROJECT GATE

This gate documents why Skuld exists as a repository, what boundary keeps it
from growing without discipline, and which operational costs are accepted.

## 1. Why does this project exist?

- real problem: Local operators need one stable CLI view for selected services without granting the tool authority over every service on the host.
- target user or operator: A developer or operator managing personal, lab, or single-host service workloads through `systemd` or `launchd`.
- expected outcome: Registered services can be listed, inspected, started, stopped, restarted, executed, and diagnosed through consistent names and commands.

## 2. Why should this not just be a module?

- candidate repository that could absorb this: General shell scripts or host-specific dotfiles could absorb parts of the workflow.
- why coupling would be inappropriate: Service operation needs its own registry, safety rules, backend adapters, and documentation instead of being hidden inside unrelated automation.
- boundary justifying separate repository: The repository owns the Skuld CLI, registry contract, backend command adapters, operational docs, and validation guardrails.

## 3. What does this project share with the ecosystem?

- configuration: Host-local settings are CLI flags, environment variables, optional `.env` files, and the sibling Skuld user `config.json`, with no committed machine-specific runtime config.
- logging: Skuld reads backend logs from `journalctl` on Linux and compatible file logs on macOS; it does not provide a central logging service.
- runtime: Runtime state lives under `SKULD_HOME`, platform user data directories, or documented system paths such as `/var/lib/skuld`.
- contracts: The main contract is the services registry JSON plus CLI target resolution by display name, ID, backend name, and backend scope.
- authentication or transport: There is no network transport; privilege elevation is local `sudo`, preferably through the native sudo timestamp and optionally through short-lived environment or `.env` password support.

## 4. What must this project not carry?

- out of scope responsibilities: Creating deployment pipelines, owning arbitrary service definitions, managing remote hosts, or replacing service-manager policy.
- integrations owned by another system: Unit file authoring, launchd plist authoring, managed-service package installation, DNS, network routing, and host provisioning belong outside Skuld.
- data that must not live here: Real service registries, user config files, sudo passwords, generated logs, runtime stats, local dumps, and host-specific private configuration.

## 5. What maintenance cost is expected?

- primary host or environment: Single-host local operation on Linux with `systemd` or macOS with `launchd`, using Python 3.9 or newer.
- most fragile external dependency: Backend command behavior and permissions vary across `systemctl`, `journalctl`, `launchctl`, `/proc`, `ss`, and `lsof`.
- restart need: Skuld is a CLI, so code changes require rerunning the command; the optional Linux stats timer requires a systemd daemon reload and timer restart after installer changes.
- backup need: The service registry JSON needs backup if aliases and tracked services matter; the sibling user config needs backup only if local display preferences matter.
- operational risk: Start, stop, restart, exec, sudo helper, and stats timer installation can change host service state or system files if used carelessly.

## 6. Exit condition

This repository remains justified while it keeps a defensible boundary around:

- explicit registry-based service operation
- local `systemd` and `launchd` adapters
- stable CLI identity and target resolution
- auditable operations and documentation
- single-host service visibility without becoming a deployment platform
