import datetime as dt
import json
import plistlib
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import skuld_common as common


def restart_policy_allows_restart(value: str) -> bool:
    policy = (value or "on-failure").strip().lower()
    return policy not in {"no", "never"}


def format_event_timestamp(value: str) -> str:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def read_event_stats(event_path: Path, *, schedule: str = "", restart: str = "on-failure") -> Dict[str, object]:
    executions = 0
    last_run = "-"
    last_exit_status = "-"
    if not event_path.exists():
        return {
            "executions": 0,
            "restarts": 0,
            "last_run": "-",
            "last_exit_status": "-",
        }
    for raw in event_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if item.get("event") == "start":
            executions += 1
            last_run = format_event_timestamp(str(item.get("ts", "-")))
        elif item.get("event") == "end":
            last_exit_status = str(item.get("exit_status", "-"))
    restarts = max(0, executions - 1) if (not schedule and restart_policy_allows_restart(restart)) else 0
    return {
        "executions": executions,
        "restarts": restarts,
        "last_run": last_run,
        "last_exit_status": last_exit_status,
    }


def update_runtime_stats(
    runtime_stats_file: Path,
    ensure_storage: Callable[[], None],
    service_name: str,
    stats: Dict[str, object],
) -> Dict[str, Dict[str, object]]:
    ensure_storage()
    try:
        payload = json.loads(runtime_stats_file.read_text(encoding="utf-8"))
    except Exception:
        payload = {"services": {}}
    if not isinstance(payload, dict):
        payload = {"services": {}}
    services = payload.get("services")
    if not isinstance(services, dict):
        services = {}
        payload["services"] = services
    services[service_name] = stats
    runtime_stats_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return services


def read_service_events(event_path: Path) -> List[Dict[str, object]]:
    if not event_path.exists():
        return []
    events: List[Dict[str, object]] = []
    for raw in event_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def read_recent_run_root_pids(events: List[Dict[str, object]], limit: int = 3) -> List[int]:
    starts = []
    for item in events:
        if str(item.get("event")) != "start":
            continue
        pid = common.parse_int(str(item.get("child_pid", item.get("pid", 0))))
        if pid > 0:
            starts.append(pid)
    if not starts:
        return []
    return list(reversed(starts[-max(1, limit):]))


def tail_file(run_cmd: Callable[..., object], path: Path, lines: int, follow: bool) -> None:
    cmd = ["tail", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(str(path))
    try:
        run_cmd(cmd, check=False)
    except KeyboardInterrupt:
        return


def log_paths_for_service(
    *,
    managed_by_skuld: bool,
    log_dir: str,
    plist_path: Path,
) -> Tuple[Optional[Path], Optional[Path]]:
    if managed_by_skuld or log_dir:
        resolved_log_dir = Path(log_dir)
        return resolved_log_dir / "stdout.log", resolved_log_dir / "stderr.log"

    if not plist_path.exists():
        return None, None

    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except Exception:
        return None, None

    stdout_raw = str(plist.get("StandardOutPath", "")).strip()
    stderr_raw = str(plist.get("StandardErrorPath", "")).strip()
    stdout_path = Path(stdout_raw) if stdout_raw else None
    stderr_path = Path(stderr_raw) if stderr_raw else None
    return stdout_path, stderr_path
