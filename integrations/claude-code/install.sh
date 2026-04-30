#!/usr/bin/env bash
# Install the voiceprompt skill for Claude Code.
#
# After running this script, restart Claude Code (or start a new session) and
# the `/voiceprompt` slash command will appear in your skills list.

set -eu

skill_src="$(cd "$(dirname "$0")" && pwd)/SKILL.md"
skill_dir="${HOME}/.claude/skills/voiceprompt"

if [ ! -f "$skill_src" ]; then
  echo "error: cannot find SKILL.md at $skill_src" >&2
  exit 1
fi

mkdir -p "$skill_dir"
cp "$skill_src" "$skill_dir/SKILL.md"

echo "installed: $skill_dir/SKILL.md"
echo
echo "next steps:"
echo "  1. start a new Claude Code session (skills load at startup)"
echo "  2. type /voiceprompt to dictate"
echo "  3. /voiceprompt start | stop | status to control the daemon"
