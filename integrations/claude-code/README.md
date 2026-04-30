# Claude Code integration

A `/voiceprompt` slash command for [Claude Code](https://claude.ai/code).

## Install

```bash
bash integrations/claude-code/install.sh
```

This copies `SKILL.md` to `~/.claude/skills/voiceprompt/`. Restart Claude Code
(or start a new session) and the `/voiceprompt` command will appear in your
skills list.

## Usage

| Command                 | What it does                                                |
|-------------------------|-------------------------------------------------------------|
| `/voiceprompt`          | Record up to 30s, transcribe, refine, treat as your prompt  |
| `/voiceprompt 15`       | Same but cap recording at 15 seconds                        |
| `/voiceprompt start`    | Start the global-hotkey daemon in the background            |
| `/voiceprompt stop`     | Stop it                                                     |
| `/voiceprompt status`   | Show whether the daemon is alive                            |

## How it works

`/voiceprompt` calls the `voiceprompt dictate --stdout` CLI. Because Claude
Code invokes shell commands without a TTY on stdin, recording auto-stops at
the `--max-seconds` cap rather than on Enter — so pick a value that fits the
length of what you want to say (default 30s). All progress and errors go to
stderr, so only the refined prompt appears as the command's output. Claude
then reads that output and responds to it as if you had typed it.

If you'd rather use the global hotkey (recommended for anything beyond a
quick try), run `voiceprompt start` from any terminal once and press
`Ctrl+Space` from any window — including Claude Code's input — to dictate.
