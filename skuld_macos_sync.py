import plistlib
from dataclasses import asdict
from pathlib import Path
from typing import Callable, List, Optional

import skuld_macos_schedules as schedules
from skuld_macos_model import ManagedService


def sync_registry_from_launchd(
    name: Optional[str],
    *,
    load_registry: Callable[..., List[ManagedService]],
    save_registry: Callable[[List[ManagedService]], None],
    plist_path_for_service: Callable[[ManagedService], Path],
) -> int:
    services = load_registry(write_back=True)
    changed = 0
    target_names = {name} if name else None
    updated: List[ManagedService] = []

    for service in services:
        if target_names and service.name not in target_names:
            updated.append(service)
            continue

        new_service = ManagedService(**asdict(service))
        path = plist_path_for_service(service)
        if path.exists():
            with path.open("rb") as handle:
                plist = plistlib.load(handle)
            new_service.working_dir = str(
                plist.get("WorkingDirectory", new_service.working_dir)
            )
            new_service.user = str(plist.get("UserName", new_service.user))
            stdout_path = str(plist.get("StandardOutPath", "")).strip()
            if stdout_path:
                new_service.log_dir = str(Path(stdout_path).parent)
            if not new_service.schedule:
                new_service.schedule = schedules.schedule_from_plist(path)

        if asdict(new_service) != asdict(service):
            changed += 1
            updated.append(new_service)
        else:
            updated.append(service)

    if changed:
        save_registry(updated)
    return changed
