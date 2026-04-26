#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST=""

usage() {
  cat <<EOF
Usage: $0 [--host HOST]

Creates a disposable systemd --user service, tracks it with Skuld, exercises
status/doctor/restart/exec/untrack, and removes the unit.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ -z "${2:-}" ]]; then
        echo "--host requires a value." >&2
        exit 1
      fi
      HOST="$2"
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

UNIT_NAME="skuld-smoke-$(date +%s)-$$"
ALIAS="skuld-smoke-linux"

run_payload() {
  bash -s -- "$@"
}

remote_payload() {
  cat <<'REMOTE'
set -euo pipefail

REPO="$1"
UNIT_NAME="$2"
ALIAS="$3"
STATE_DIR="$4"
UNIT_FILE="$HOME/.config/systemd/user/$UNIT_NAME.service"

cleanup_and_audit() {
  original_status="$1"
  cleanup_status=0

  systemctl --user stop "$UNIT_NAME.service" >/dev/null 2>&1 || true
  rm -f "$UNIT_FILE"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user reset-failed "$UNIT_NAME.service" >/dev/null 2>&1 || true
  rm -rf "$STATE_DIR"

  if systemctl --user list-units --full --all --no-legend "$UNIT_NAME.service" 2>/dev/null |
    awk '{print $1}' | grep -Fxq "$UNIT_NAME.service"; then
    echo "[error] disposable systemd user unit remains loaded: $UNIT_NAME.service" >&2
    cleanup_status=1
  fi
  if [[ -e "$UNIT_FILE" ]]; then
    echo "[error] disposable systemd user unit file remains: $UNIT_FILE" >&2
    cleanup_status=1
  fi
  if [[ -e "$STATE_DIR" ]]; then
    echo "[error] disposable smoke temp dir remains: $STATE_DIR" >&2
    cleanup_status=1
  fi

  if [[ "$original_status" -ne 0 ]]; then
    exit "$original_status"
  fi
  if [[ "$cleanup_status" -ne 0 ]]; then
    exit "$cleanup_status"
  fi
}
trap 'cleanup_and_audit "$?"' EXIT

mkdir -p "$HOME/.config/systemd/user" "$STATE_DIR"
cat >"$UNIT_FILE" <<EOF
[Unit]
Description=Skuld disposable smoke service

[Service]
Type=simple
ExecStart=/bin/sh $REPO/scripts/smoke_process.sh $UNIT_NAME

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user start "$UNIT_NAME.service"
sleep 1

SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" track "user:$UNIT_NAME" --alias "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" status "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" doctor
SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" restart "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" exec "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$REPO/skuld" untrack "$ALIAS" >/dev/null
echo "[ok] untracked $ALIAS"

echo "Linux systemd user smoke passed for $UNIT_NAME"
REMOTE
}

if [[ -n "$HOST" ]]; then
  REMOTE_DIR="$(ssh "$HOST" 'mktemp -d /tmp/skuld-smoke-repo.XXXXXX')"
  cleanup_remote_repo_and_audit() {
    original_status="$1"
    cleanup_status=0

    ssh "$HOST" "rm -rf '$REMOTE_DIR'" >/dev/null 2>&1 || true
    if ssh "$HOST" "test ! -e '$REMOTE_DIR'" >/dev/null 2>&1; then
      :
    else
      echo "[error] disposable remote repo temp dir remains on $HOST: $REMOTE_DIR" >&2
      cleanup_status=1
    fi

    if [[ "$original_status" -ne 0 ]]; then
      exit "$original_status"
    fi
    if [[ "$cleanup_status" -ne 0 ]]; then
      exit "$cleanup_status"
    fi
  }
  trap 'cleanup_remote_repo_and_audit "$?"' EXIT
  COPYFILE_DISABLE=1 tar --no-xattrs -C "$ROOT" -czf - \
    skuld \
    skuld_entrypoint.py \
    skuld_cli.py \
    skuld_common.py \
    skuld_linux.py \
    skuld_linux_presenters.py \
    skuld_linux_runtime.py \
    skuld_linux_systemd.py \
    skuld_linux_stats.py \
    skuld_linux_timers.py \
    skuld_linux_targets.py \
    skuld_linux_view.py \
    skuld_macos_launchd.py \
    skuld_observability.py \
    skuld_registry.py \
    skuld_tables.py \
    scripts/smoke_process.sh |
    ssh "$HOST" "tar -xzf - -C '$REMOTE_DIR'"
  ssh "$HOST" "chmod +x '$REMOTE_DIR/skuld' '$REMOTE_DIR/scripts/smoke_process.sh'"
  ssh "$HOST" "bash -s" -- "$REMOTE_DIR" "$UNIT_NAME" "$ALIAS" "/tmp/$UNIT_NAME-state" < <(remote_payload)
else
  run_payload "$ROOT" "$UNIT_NAME" "$ALIAS" "/tmp/$UNIT_NAME-state" < <(remote_payload)
fi
