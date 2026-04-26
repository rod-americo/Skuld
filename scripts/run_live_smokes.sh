#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_MACOS=0
RUN_LINUX=0
LINUX_HOST=""

usage() {
  cat <<EOF
Usage: $0 [--macos] [--linux] [--linux-host HOST]

Runs explicit live smoke checks against disposable services and fails if their
cleanup audits find leftover smoke state.

Options:
  --macos           Run the local macOS LaunchAgent smoke.
  --linux           Run the local Linux systemd --user smoke.
  --linux-host      Run the Linux systemd --user smoke over SSH on HOST.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --macos)
      RUN_MACOS=1
      shift
      ;;
    --linux)
      RUN_LINUX=1
      shift
      ;;
    --linux-host)
      if [[ -z "${2:-}" ]]; then
        echo "--linux-host requires a value." >&2
        exit 1
      fi
      RUN_LINUX=1
      LINUX_HOST="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$RUN_MACOS" -eq 0 && "$RUN_LINUX" -eq 0 ]]; then
  echo "Choose at least one smoke target." >&2
  usage
  exit 1
fi

if [[ "$RUN_MACOS" -eq 1 ]]; then
  echo "==> macOS launchd smoke"
  "$ROOT/scripts/smoke_macos_launchd.sh"
fi

if [[ "$RUN_LINUX" -eq 1 ]]; then
  echo "==> Linux systemd --user smoke"
  if [[ -n "$LINUX_HOST" ]]; then
    "$ROOT/scripts/smoke_linux_systemd_user.sh" --host "$LINUX_HOST"
  else
    "$ROOT/scripts/smoke_linux_systemd_user.sh"
  fi
fi

echo "Live smokes passed."
