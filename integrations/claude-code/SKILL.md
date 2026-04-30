---
name: voiceprompt
description: "Capture a voice dictation through the voiceprompt CLI and treat the refined prompt as the user's actual instruction. Use ONLY when the user explicitly invokes /voiceprompt — never proactively, since this requires the user to physically speak. Also handles /voiceprompt start|stop|status to control the background daemon."
---

# voiceprompt — voice-to-prompt for Claude Code

The user has voiceprompt installed (a CLI tool that records audio, transcribes
it locally with Parakeet, and refines the transcript into a clean prompt via
their configured AI provider). When they type `/voiceprompt`, run the CLI to
capture a dictation and treat the printed text as if the user had typed it.

## Dispatch

Pick the branch based on the user's `$ARGUMENTS`:

| Argument                          | What to do                                             |
|-----------------------------------|--------------------------------------------------------|
| _(empty)_                         | Run a one-shot dictation (default 30s cap)             |
| an integer (e.g. `15`, `45`)      | One-shot dictation with that many seconds as the cap   |
| `start`                           | Start the background daemon                            |
| `stop`                            | Stop the background daemon                             |
| `status`                          | Report whether the daemon is running                   |
| anything else                     | Treat as one-shot, pass through to `--max-seconds` if numeric, otherwise show usage |

## Branch 1 — One-shot dictation (the common case)

1. Tell the user briefly: "Recording for up to N seconds. Speak now."
   (replace N with the chosen --max-seconds)

2. Run the Bash tool with this command, exactly:

   ```
   voiceprompt dictate --stdout --max-seconds <N>
   ```

   Notes:
   - `--stdout` suppresses the TUI; the refined prompt prints to stdout.
   - All progress + errors go to stderr.
   - Stdin is not a TTY when invoked from Bash, so the recorder auto-stops
     at `--max-seconds`. The user cannot press Enter to stop early —
     pick a short value (10–30s) for normal use, longer only if they ask.

3. **Critical**: Treat stdout as the user's actual prompt. Do **not** quote
   it back, do not summarize, do not say "you said …". Read it as their
   real instruction and respond accordingly. Behave exactly as if they had
   typed it themselves.

4. If exit code is non-zero, give a one-line explanation based on stderr:
   - 1: missing API key — `voiceprompt set-key <KEY>`
   - 2: transcription model not on disk — run `voiceprompt dictate` once interactively to download
   - 3: no microphone or denied permissions — System Settings → Privacy & Security → Microphone
   - 4: silent or empty audio — speak louder, check the mic, or grant Microphone access to the terminal
   - 5: speech-to-text failure — see stderr
   - 6: AI provider failure (auth, quota) — check Settings or `voiceprompt config`
   - 130: cancelled

## Branch 2 — Daemon control

For `start`, `stop`, or `status`, run the matching command and print the result:

| Argument | Command                |
|----------|------------------------|
| start    | `voiceprompt start`    |
| stop     | `voiceprompt stop`     |
| status   | `voiceprompt status`   |

Show the command output verbatim. Do not add commentary unless something
went wrong.

## Important rules

- **Never invoke this skill proactively.** It requires the user to be at
  their microphone and ready to speak. Only run it when they explicitly
  type `/voiceprompt`.
- **Don't echo back the dictated prompt.** Just respond to it.
- **Don't suggest the daemon flow** unless the user asks — they may be
  using `/voiceprompt` precisely because they don't want a daemon.
- The CLI is on `$PATH` as `voiceprompt`. If it's not found, tell the
  user to install it from the project repo.
