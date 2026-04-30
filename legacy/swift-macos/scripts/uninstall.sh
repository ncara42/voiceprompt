#!/usr/bin/env bash
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.noel.voiceprompt.plist"

echo "==> Uninstalling voiceprompt"

if launchctl list | grep -q "com.noel.voiceprompt"; then
    launchctl unload "$PLIST" 2>/dev/null || true
fi

[ -f "$PLIST" ] && rm -f "$PLIST" && echo "    Removed LaunchAgent"
[ -f "/usr/local/bin/voiceprompt" ] && sudo rm -f "/usr/local/bin/voiceprompt" && echo "    Removed binary"

echo ""
echo "Config and Whisper model left at ~/.config/voiceprompt/ (delete manually if needed)."
echo "✓ Done."
