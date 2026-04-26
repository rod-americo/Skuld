from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import skuld_common as common


def run_launchctl(
    scope: str,
    args: List[str],
    *,
    sudo_password: Optional[str] = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    cmd = ["launchctl"] + args
    if scope == "daemon":
        return common.run_sudo_command(cmd, sudo_password=sudo_password, check=check, capture=capture)
    return common.run_command(cmd, check=check, capture=capture)


def domain_target(scope: str, *, uid: Optional[int] = None) -> str:
    if scope == "agent":
        return f"gui/{os.getuid() if uid is None else uid}"
    return "system"


def service_target(scope: str, label: str) -> str:
    return f"{domain_target(scope)}/{label}"


def print_service_raw(label: str, *, uid: Optional[int] = None) -> str:
    target = f"gui/{os.getuid() if uid is None else uid}/{label}"
    proc = common.run_command(["launchctl", "print", target], check=False, capture=True)
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def extract_value(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)} = (.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_kv(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r'"?([A-Za-z0-9_]+)"?\s*=\s*("?)(.*?)\2;?$', line)
        if not match:
            continue
        result[match.group(1)] = match.group(3)
    return result


def service_info(scope: str, label: str, *, sudo_password: Optional[str] = None) -> Dict[str, str]:
    proc = run_launchctl(scope, ["list", label], sudo_password=sudo_password, check=False, capture=True)
    if proc.returncode != 0:
        return {}
    return parse_kv(proc.stdout or "")


def service_loaded(scope: str, label: str, *, sudo_password: Optional[str] = None) -> bool:
    proc = run_launchctl(scope, ["list", label], sudo_password=sudo_password, check=False, capture=True)
    return proc.returncode == 0


def is_disabled_bootstrap_error(text: str) -> bool:
    return "disabled" in text.lower()


def bootstrap_service(
    scope: str,
    label: str,
    plist_path: Path,
    *,
    sudo_password: Optional[str] = None,
) -> subprocess.CompletedProcess:
    if service_loaded(scope, label, sudo_password=sudo_password):
        return subprocess.CompletedProcess(args=["launchctl"], returncode=0, stdout="", stderr="")
    proc = run_launchctl(
        scope,
        ["bootstrap", domain_target(scope), str(plist_path)],
        sudo_password=sudo_password,
        check=False,
        capture=True,
    )
    details = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    if proc.returncode != 0 and is_disabled_bootstrap_error(details):
        run_launchctl(
            scope,
            ["enable", service_target(scope, label)],
            sudo_password=sudo_password,
            check=False,
        )
        return run_launchctl(
            scope,
            ["bootstrap", domain_target(scope), str(plist_path)],
            sudo_password=sudo_password,
            check=False,
            capture=True,
        )
    return proc


def bootout_service(
    scope: str,
    label: str,
    *,
    sudo_password: Optional[str] = None,
) -> subprocess.CompletedProcess:
    return run_launchctl(
        scope,
        ["bootout", service_target(scope, label)],
        sudo_password=sudo_password,
        check=False,
    )


def kickstart_service(
    scope: str,
    label: str,
    *,
    sudo_password: Optional[str] = None,
    kill_existing: bool = False,
) -> subprocess.CompletedProcess:
    args = ["kickstart"]
    if kill_existing:
        args.append("-k")
    args.append(service_target(scope, label))
    return run_launchctl(scope, args, sudo_password=sudo_password, check=False, capture=True)
