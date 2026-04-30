# voiceprompt — Claude Code plugin

A `/voiceprompt` slash command for [Claude Code](https://claude.ai/code) that
captures voice dictations, transcribes them locally with Parakeet, refines
them with the AI provider of your choice, and treats the result as your
actual prompt.

## Install

### 1. Install the underlying CLI

The plugin is a thin wrapper around the `voiceprompt` CLI. Install it first:

```bash
# recommended
uv tool install voiceprompt-cli

# or with pipx
pipx install voiceprompt-cli
```

Then run `voiceprompt` once to set up your API key (opens a guided wizard):

```bash
voiceprompt
```

### 2. Add the plugin to Claude Code

```text
/plugin marketplace add ncara42/voiceprompt
/plugin install voiceprompt@voiceprompt
```

Restart Claude Code (or start a new session) so the skill loads.

## Use

| Command                 | What it does                                                  |
|-------------------------|---------------------------------------------------------------|
| `/voiceprompt`          | Record freely, auto-stop ~1.5s after you finish speaking      |
| `/voiceprompt 60`       | Same, with a hard cap of 60 seconds (default cap is 120)      |
| `/voiceprompt start`    | Start the global-hotkey daemon in the background              |
| `/voiceprompt stop`     | Stop it                                                       |
| `/voiceprompt status`   | Check whether the daemon is alive                             |

## How it works

`/voiceprompt` calls `voiceprompt dictate --stdout` under the hood. Voice
activity detection ends the recording about 1.5 s after you stop talking,
so the duration is whatever you want — there's no fixed timer to wait out.
`--max-seconds` is just a safety net in case VAD never sees silence.

All progress and error messages go to stderr, so only the refined prompt
appears as the command output. Claude reads that output and responds to it
as if you had typed it.

## Tip: prefer the global hotkey

For anything beyond a quick one-shot, `/voiceprompt start` once and then
press **Ctrl+Space** from any window — including Claude Code's input — to
dictate. The hotkey is a true toggle: press once to start, once to stop.
The refined prompt is auto-pasted into whichever window has focus.

## Troubleshooting

| Symptom                                  | Fix                                                                |
|------------------------------------------|--------------------------------------------------------------------|
| `voiceprompt: command not found`         | Install the CLI (step 1 above)                                     |
| Exit 1 — Missing API key                 | Run `voiceprompt --menu` to open settings, paste your provider key |
| Exit 2 — Transcription model not on disk | Run `voiceprompt --menu`; the wizard downloads it (~1.2 GB)        |
| Exit 3 — No microphone                   | macOS: System Settings → Privacy & Security → Microphone           |
| Exit 4 — Silent audio                    | Grant microphone permission to the terminal running `voiceprompt`  |
| Hotkey doesn't fire inside Claude Code   | Change it via `voiceprompt --menu` → Settings → Behavior → Hotkey  |

## Source

[github.com/ncara42/voiceprompt](https://github.com/ncara42/voiceprompt)
