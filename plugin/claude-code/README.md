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
| `/voiceprompt`          | Start the hotkey daemon in the background                     |
| `/voiceprompt stop`     | Stop the daemon                                               |
| `/voiceprompt status`   | Check whether the daemon is alive                             |
| `/voiceprompt now`      | One-shot dictation without the daemon (auto-stops on silence) |
| `/voiceprompt now 60`   | Same, hard-capped at 60 seconds                               |

## How it works

The default `/voiceprompt` boots the global-hotkey daemon as a detached
background process and returns. Once it's up, press **Ctrl+Space** from
any window — including Claude Code's input — to start recording, and
again to stop. The refined prompt is pasted into whichever window has
focus when the cycle finishes.

This means the slash command is a one-time bootstrap. After it succeeds,
all dictation happens through the hotkey, which is a true toggle — you
control exactly when to start and stop, with no fixed timer.

If you'd rather not run a daemon, use `/voiceprompt now` for a single
recording cycle. Voice-activity detection ends the recording ~1.5 s after
you stop speaking, so duration is dictated by the speaker, not by a timer.

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
