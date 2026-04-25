from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import skuld_common as common


SCOPE_ALIASES = {
    "system": "system",
    "root": "system",
    "user": "user",
}


def normalize_scope(value: str) -> str:
    scope = (value or "system").strip().lower()
    normalized = SCOPE_ALIASES.get(scope)
    if not normalized:
        raise ValueError(f"Invalid scope '{value}'. Use 'system' or 'user'.")
    return normalized


def scope_env(scope: str) -> Optional[Dict[str, str]]:
    if normalize_scope(scope) != "user":
        return None

    env = dict(os.environ)
    uid = os.getuid()
    runtime_dir = (env.get("XDG_RUNTIME_DIR") or "").strip()
    if not runtime_dir:
        fallback = Path(f"/run/user/{uid}")
        if fallback.exists():
            runtime_dir = str(fallback)
            env["XDG_RUNTIME_DIR"] = runtime_dir

    if runtime_dir:
        bus_path = Path(runtime_dir) / "bus"
        if bus_path.exists() and not (env.get("DBUS_SESSION_BUS_ADDRESS") or "").strip():
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"

    return env


def systemctl_command(scope: str, args: List[str]) -> List[str]:
    cmd = ["systemctl"]
    if normalize_scope(scope) == "user":
        cmd.append("--user")
    return cmd + args


def journalctl_command(scope: str, args: List[str]) -> List[str]:
    cmd = ["journalctl"]
    if normalize_scope(scope) == "user":
        cmd.append("--user")
    return cmd + args


def require_systemctl() -> None:
    try:
        common.run_command(["systemctl", "--version"], check=True, capture=True)
    except Exception as exc:
        raise RuntimeError("systemctl not found. This tool requires Linux with systemd.") from exc


def run_systemctl_action(
    scope: str,
    args: List[str],
    *,
    sudo_password: Optional[str] = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    cmd = systemctl_command(scope, args)
    if normalize_scope(scope) == "system":
        return common.run_sudo_command(cmd, sudo_password=sudo_password, check=check, capture=capture)
    return common.run_command(cmd, check=check, capture=capture, env=scope_env(scope))


def systemctl_show(unit: str, props: List[str], scope: str = "system") -> Dict[str, str]:
    cmd = systemctl_command(scope, ["show", unit, "--no-pager"])
    for prop in props:
        cmd.append(f"--property={prop}")
    proc = common.run_command(cmd, check=False, capture=True, env=scope_env(scope))
    data: Dict[str, str] = {}
    for raw in (proc.stdout or "").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        data[key] = value
    return data


def systemctl_cat(unit: str, scope: str = "system") -> str:
    proc = common.run_command(
        systemctl_command(scope, ["cat", unit, "--no-pager"]),
        check=False,
        capture=True,
        env=scope_env(scope),
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def unit_exists(unit: str, scope: str = "system") -> bool:
    show = systemctl_show(unit, ["LoadState"], scope=scope)
    load_state = (show.get("LoadState", "") or "").strip().lower()
    return bool(load_state and load_state != "not-found")


def unit_active(unit: str, scope: str = "system") -> str:
    proc = common.run_command(
        systemctl_command(scope, ["is-active", unit]),
        check=False,
        capture=True,
        env=scope_env(scope),
    )
    status = (proc.stdout or "").strip()
    return status if status else "inactive"
