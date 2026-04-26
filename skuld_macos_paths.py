from pathlib import Path


def current_user_home() -> Path:
    return Path.home()


def service_label(name: str) -> str:
    return f"io.skuld.{name}"


def launchd_label_for_service(service: object) -> str:
    return service.launchd_label or service_label(service.name)


def plist_path_for_service(service: object, *, user_home: Path) -> Path:
    if service.plist_path_hint:
        return Path(service.plist_path_hint)
    if service.scope == "agent":
        return user_home / "Library/LaunchAgents" / f"{service_label(service.name)}.plist"
    return Path("/Library/LaunchDaemons") / f"{service_label(service.name)}.plist"


def jobs_root_for_scope(scope: str, *, skuld_home: Path) -> Path:
    if scope == "agent":
        return skuld_home / "jobs"
    return Path("/Library/Application Support/skuld/jobs")


def logs_root_for_scope(scope: str, *, skuld_home: Path) -> Path:
    if scope == "agent":
        return skuld_home / "logs"
    return Path("/Library/Application Support/skuld/logs")


def events_root_for_scope(scope: str, *, skuld_home: Path) -> Path:
    if scope == "agent":
        return skuld_home / "events"
    return Path("/Library/Application Support/skuld/events")


def log_dir_for_service(name: str, scope: str, *, skuld_home: Path) -> Path:
    return logs_root_for_scope(scope, skuld_home=skuld_home) / name


def event_file_for_service(name: str, scope: str, *, skuld_home: Path) -> Path:
    return events_root_for_scope(scope, skuld_home=skuld_home) / f"{name}.jsonl"


def wrapper_script_for_service(name: str, scope: str, *, skuld_home: Path) -> Path:
    return jobs_root_for_scope(scope, skuld_home=skuld_home) / f"{name}.sh"
