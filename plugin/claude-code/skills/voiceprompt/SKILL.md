---
name: voiceprompt
description: "Capture a voice dictation through the voiceprompt CLI and treat the refined prompt as the user's actual instruction. Use ONLY when the user explicitly invokes /voiceprompt — never proactively, since this requires the user to physically speak. Also handles /voiceprompt start|stop|status to control the background hotkey daemon."
---

# voiceprompt — voice-to-prompt for Claude Code

The user has the `voiceprompt` CLI installed (a tool that records audio,
transcribes locally with Parakeet, and refines the transcript via their
configured AI provider). When the user types `/voiceprompt`, run the CLI
and treat the printed prompt as if they had typed it.

## Prerequisite check

If the very first run fails with "command not found", tell the user to
install the CLI:

```bash
uv tool install voiceprompt-cli           # recommended
# or
pipx install voiceprompt-cli
```

Then the user must run `voiceprompt` once to set up an API key (this opens
a guided wizard). After setup, `/voiceprompt` works.

## Dispatch

Pick the branch based on `$ARGUMENTS`:

| Argument                          | What to do                                             |
|-----------------------------------|--------------------------------------------------------|
| _(empty)_                         | One-shot dictation, default 30s cap                    |
| an integer (e.g. `15`, `45`)      | One-shot dictation, that many seconds as the cap       |
| `start`                           | Start the global-hotkey daemon                         |
| `stop`                            | Stop the daemon                                        |
| `status`                          | Show daemon state                                      |
| anything else                     | Treat as one-shot if numeric, otherwise show usage     |

## Branch 1 — one-shot dictation (the common case)

1. Tell the user briefly: "Recording for up to N seconds. Speak now."
   (replace N with the chosen --max-seconds)

2. Run the Bash tool with this command, exactly:

   ```
   voiceprompt dictate --stdout --max-seconds <N>
   ```

   Notes:
   - `--stdout` suppresses the TUI; only the refined prompt prints to stdout.
   - All progress + errors go to stderr.
   - Stdin is not a TTY when invoked from Bash, so the recorder auto-stops
     at `--max-seconds`. The user cannot press Enter to stop early —
     pick a short value (10–30s) for normal use.

3. **Critical**: Treat stdout as the user's actual prompt. Do **not** quote
   it back, do not summarize, do not say "you said …". Read it as their
   real instruction and respond accordingly. Behave exactly as if they had
   typed it themselves.

4. If exit code is non-zero, give a one-line explanation based on stderr:
   - 1: missing API key — `voiceprompt set-key <KEY>` (or `voiceprompt --menu`)
   - 2: transcription model not on disk — run `voiceprompt --menu` once interactively to download it
   - 3: no microphone or denied permissions — System Settings → Privacy & Security → Microphone
   - 4: silent or empty audio — speak louder, check the mic, or grant Microphone access to the terminal
   - 5: speech-to-text failure — see stderr
   - 6: AI provider failure (auth, quota) — `voiceprompt config` to inspect, `voiceprompt set-key` to fix
   - 130: cancelled

## Branch 2 — daemon control

For `start`, `stop`, or `status`, run the matching command:

| Argument | Command                |
|----------|------------------------|
| start    | `voiceprompt start`    |
| stop     | `voiceprompt stop`     |
| status   | `voiceprompt status`   |

Show the command output verbatim. Don't add commentary unless something
went wrong.

After a successful `start`, suggest the global-hotkey workflow:

> The daemon is running. Press **Ctrl+Space** (or your configured hotkey)
> from any window — including this one — to dictate, then press it again
> to stop. The refined prompt will be pasted into whichever window has
> focus. The slash command is best for short, occasional dictations; the
> hotkey is better when you'll dictate repeatedly.

## Important rules

- **Never invoke this skill proactively.** It requires the user to be at
  their microphone and ready to speak. Only run it when they explicitly
  type `/voiceprompt`.
- **Don't echo back the dictated prompt.** Just respond to it.
- **Don't warn about the CLI flow** unless the slash command failed — the
  user picked the slash command on purpose.
