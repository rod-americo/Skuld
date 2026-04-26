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

cleanup() {
  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 \
    || launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 \
    || true
  rm -f "$PLIST"
  rm -rf "$STATE_DIR"
}
trap cleanup EXIT

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
