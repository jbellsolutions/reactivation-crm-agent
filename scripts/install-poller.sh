#!/usr/bin/env bash
# Runs `rcm poll --write-builds` every 15 minutes on this Mac (launchd). Justin's yes: 2026-11-07, "Poller keys and
# schedule". Without its keys the poll exits at once and says which key is missing, so the schedule costs nothing.
#   bash scripts/install-poller.sh            # install or update
#   bash scripts/install-poller.sh --remove   # take it out
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.usingaitoscale.rcm-poll"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ "${1:-}" = "--remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"; echo "removed $LABEL"; exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" "$HERE/state"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>-m</string><string>rcm.cli</string><string>poll</string><string>--write-builds</string>
  </array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>$HERE</string></dict>
  <key>StartInterval</key><integer>900</integer>
  <key>StandardOutPath</key><string>$HERE/state/poll.log</string>
  <key>StandardErrorPath</key><string>$HERE/state/poll.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL: every 15 minutes, log in state/poll.log"
