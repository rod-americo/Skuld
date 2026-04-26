#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKULD="$ROOT/skuld"
LABEL="io.skuld.smoke.$(date +%s).$$"
ALIAS="skuld-smoke-macos"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/skuld-smoke-macos.XXXXXX")"
LOG_FILE="$STATE_DIR/process.log"

wait_until_unloaded() {
  attempt=0
  while [[ "$attempt" -lt 20 ]]; do
    if ! launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
    attempt=$((attempt + 1))
  done
  return 1
}

cleanup_and_audit() {
  original_status="$1"
  cleanup_status=0

  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 \
    || launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 \
    || true
  wait_until_unloaded || true
  rm -f "$PLIST"
  rm -rf "$STATE_DIR"

  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "[error] disposable launchd label is still loaded: $DOMAIN/$LABEL" >&2
    cleanup_status=1
  fi
  if [[ -e "$PLIST" ]]; then
    echo "[error] disposable launchd plist remains: $PLIST" >&2
    cleanup_status=1
  fi
  if [[ -e "$STATE_DIR" ]]; then
    echo "[error] disposable smoke temp dir remains: $STATE_DIR" >&2
    cleanup_status=1
  fi
  if launchctl print-disabled "$DOMAIN" 2>/dev/null | grep -Fq "$LABEL"; then
    echo "[error] disposable label remains in launchd disabled overrides: $LABEL" >&2
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

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$ROOT/scripts/smoke_process.sh</string>
    <string>$LABEL</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$STATE_DIR/process.err</string>
</dict>
</plist>
EOF

launchctl bootstrap "$DOMAIN" "$PLIST"
sleep 1

SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" track "$LABEL" --alias "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" status "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" doctor
SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" restart "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" exec "$ALIAS"
SKULD_HOME="$STATE_DIR/skuld-home" "$SKULD" untrack "$ALIAS" >/dev/null
echo "[ok] untracked $ALIAS"

echo "macOS launchd smoke passed for $LABEL"
