import json
from pathlib import Path
from typing import Callable, Dict, Optional

import skuld_common as common


SYSTEMD_UNIT_STARTED_MESSAGE_ID = "39f53479d3a045ac8e11786248231fbf"


def journal_permission_hint(stderr_text: str) -> bool:
    lower = stderr_text.lower()
    return (
        "not seeing messages from other users and the system" in lower
        or "permission denied" in lower
    )


def load_runtime_stats(runtime_stats_file: Path) -> Dict[str, Dict[str, int]]:
    try:
        data = json.loads(runtime_stats_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    services = data.get("services")
    if not isinstance(services, dict):
        return {}

    normalized: Dict[str, Dict[str, int]] = {}
    for name, item in services.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            continue
        executions = common.parse_int(str(item.get("executions", 0)))
        restarts = common.parse_int(str(item.get("restarts", 0)))
        normalized[name] = {
            "executions": max(0, executions),
            "restarts": max(0, restarts),
        }
    return normalized


def format_restarts_exec(name: str, runtime_stats: Dict[str, Dict[str, int]]) -> str:
    item = runtime_stats.get(name)
    if not item:
        return "-"
    return f"{item.get('restarts', 0)}/{item.get('executions', 0)}"


def count_unit_starts(
    *,
    unit: str,
    scope: str,
    systemd_scope_env: Callable[[str], Optional[Dict[str, str]]],
    journalctl_command: Callable[[str, list[str]], list[str]],
    run_cmd: Callable[..., object],
    run_sudo_cmd: Callable[..., object],
    since: Optional[str] = None,
    boot: bool = False,
) -> int:
    scope_env = systemd_scope_env(scope)
    cmd = journalctl_command(
        scope,
        [
            "-u",
            unit,
            f"MESSAGE_ID={SYSTEMD_UNIT_STARTED_MESSAGE_ID}",
            "-o",
            "json",
            "--no-pager",
        ],
    )
    if since:
        cmd.extend(["--since", since])
    if boot:
        cmd.append("-b")

    proc = run_cmd(cmd, check=False, capture=True, env=scope_env)
    stderr = (getattr(proc, "stderr", "") or "").strip()
    stdout = getattr(proc, "stdout", "") or ""
    if (scope or "system").strip().lower() == "system" and journal_permission_hint(stderr):
        proc = run_sudo_cmd(cmd, check=False, capture=True)
        stdout = getattr(proc, "stdout", "") or ""

    lines = [line for line in stdout.splitlines() if line.strip()]
    return len(lines)


def read_restart_count(
    *,
    name: str,
    scope: str,
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., Dict[str, str]],
) -> str:
    service_unit = f"{name}.service"
    if not unit_exists(service_unit, scope=scope):
        return "-"
    show = systemctl_show(service_unit, ["NRestarts"], scope=scope)
    raw = (show.get("NRestarts", "") or "").strip()
    return raw if raw else "-"
