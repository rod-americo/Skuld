#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTOR_SRC="$SCRIPT_DIR/skuld_journal_stats_collector.py"

REGISTRY_PATH="${HOME}/.local/share/skuld/services.json"
OUTPUT_PATH="/var/lib/skuld/journal_stats.json"
INSTALL_COLLECTOR="/usr/local/lib/skuld/skuld_journal_stats_collector.py"
SERVICE_FILE="/etc/systemd/system/skuld-journal-stats.service"
TIMER_FILE="/etc/systemd/system/skuld-journal-stats.timer"
DRY_RUN=0
MODE="install"

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--uninstall] [--registry PATH] [--output PATH]

Installs or removes a systemd service+timer that collects restart/execution
counters for managed Skuld services every minute.

Options:
  --dry-run      Print planned commands and generated units without changing the host.
  --uninstall    Stop/disable the timer and remove installed unit files.
  --registry     Registry path read by the collector.
  --output       Stats JSON path written by the collector.
EOF
}

require_value() {
  local flag="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    echo "$flag requires a value." >&2
    exit 1
  fi
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

write_unit_file() {
  local target="$1"
  local content="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--- $target"
    printf '%s\n' "$content"
    return 0
  fi
  printf '%s\n' "$content" | sudo tee "$target" >/dev/null
}

service_content() {
  cat <<EOF
[Unit]
Description=Collect Skuld restart/execution stats since last boot
After=systemd-journald.service
Wants=systemd-journald.service

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $INSTALL_COLLECTOR --registry $REGISTRY_PATH --output $OUTPUT_PATH
EOF
}

timer_content() {
  cat <<EOF
[Unit]
Description=Refresh Skuld journal stats every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=15s
Persistent=true
Unit=skuld-journal-stats.service

[Install]
WantedBy=timers.target
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --uninstall)
      MODE="uninstall"
      shift
      ;;
    --registry)
      require_value "$1" "${2:-}"
      REGISTRY_PATH="$2"
      shift 2
      ;;
    --output)
      require_value "$1" "${2:-}"
      OUTPUT_PATH="$2"
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

if [[ "$MODE" == "install" && ! -f "$COLLECTOR_SRC" ]]; then
  echo "Collector script not found: $COLLECTOR_SRC" >&2
  exit 1
fi

if [[ "$MODE" == "uninstall" ]]; then
  echo "Removing Skuld journal stats timer."
  run_cmd sudo systemctl disable --now skuld-journal-stats.timer
  run_cmd sudo rm -f "$SERVICE_FILE" "$TIMER_FILE" "$INSTALL_COLLECTOR"
  run_cmd sudo systemctl daemon-reload
  run_cmd sudo systemctl reset-failed skuld-journal-stats.service skuld-journal-stats.timer
  echo "Uninstall complete. Stats output was left in place: $OUTPUT_PATH"
  exit 0
fi

echo "Installing Skuld journal stats timer."
run_cmd sudo install -d -m 0755 "$(dirname "$INSTALL_COLLECTOR")"
run_cmd sudo install -m 0755 "$COLLECTOR_SRC" "$INSTALL_COLLECTOR"
write_unit_file "$SERVICE_FILE" "$(service_content)"
write_unit_file "$TIMER_FILE" "$(timer_content)"
run_cmd sudo systemctl daemon-reload
run_cmd sudo systemctl enable --now skuld-journal-stats.timer
run_cmd sudo systemctl start skuld-journal-stats.service
run_cmd sudo systemctl status skuld-journal-stats.timer --no-pager

echo
echo "Install complete."
