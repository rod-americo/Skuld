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

cleanup() {
  systemctl --user stop "$UNIT_NAME.service" >/dev/null 2>&1 || true
  rm -f "$UNIT_FILE"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user reset-failed "$UNIT_NAME.service" >/dev/null 2>&1 || true
  rm -rf "$STATE_DIR"
}
trap cleanup EXIT

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
  cleanup_remote_repo() {
    ssh "$HOST" "rm -rf '$REMOTE_DIR'" >/dev/null 2>&1 || true
  }
  trap cleanup_remote_repo EXIT
  COPYFILE_DISABLE=1 tar --no-xattrs -C "$ROOT" -czf - \
    skuld \
    skuld_entrypoint.py \
    skuld_cli.py \
    skuld_common.py \
    skuld_linux.py \
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
