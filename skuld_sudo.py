from typing import Callable, Optional


SUDO_ENV_WARNING = (
    "Warning: using SKULD_SUDO_PASSWORD from env/.env. "
    "Keep this for short-lived local use only."
)


def warn_env_sudo_usage(
    *,
    get_sudo_password: Callable[[], Optional[str]],
    info: Callable[[str], None],
) -> None:
    if get_sudo_password():
        info(SUDO_ENV_WARNING)


def sudo_check(
    *,
    get_sudo_password: Callable[[], Optional[str]],
    run: Callable[..., object],
    info: Callable[[str], None],
    ok: Callable[[str], None],
) -> None:
    warn_env_sudo_usage(get_sudo_password=get_sudo_password, info=info)
    password = get_sudo_password()
    if password:
        proc = run(
            ["sudo", "-S", "-k", "-p", "", "true"],
            check=False,
            capture=True,
            input_text=password + "\n",
        )
    else:
        proc = run(["sudo", "-n", "true"], check=False, capture=True)
    if proc.returncode == 0:
        ok("sudo is available.")
        return
    details = (proc.stderr or proc.stdout or "").strip()
    raise RuntimeError(f"sudo is not available non-interactively. {details}".strip())


def sudo_run_command(
    args: object,
    *,
    get_sudo_password: Callable[[], Optional[str]],
    run_sudo: Callable[..., object],
    info: Callable[[str], None],
) -> None:
    command = list(getattr(args, "command", None) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise RuntimeError("Use: skuld sudo run -- <command> [args...]")
    warn_env_sudo_usage(get_sudo_password=get_sudo_password, info=info)
    proc = run_sudo(command, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"sudo command failed with exit code {proc.returncode}.")
