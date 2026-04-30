---
name: voiceprompt
description: "Boot the voiceprompt global-hotkey daemon so the user can dictate with Ctrl+Space from any window. Use ONLY when the user explicitly invokes /voiceprompt — do not call proactively. Also handles /voiceprompt stop|status and /voiceprompt now for a one-shot dictation without the daemon."
---

# voiceprompt — voice-to-prompt for Claude Code

The user has the `voiceprompt` CLI installed (a tool that records audio,
transcribes locally with Parakeet, and refines the transcript via their
configured AI provider). When the user types `/voiceprompt`, your job is
to **start the background daemon** so the user can press their global
hotkey (default `Ctrl+Space`) from any window — including this one — to
dictate. The actual dictation happens through the hotkey, not through
this skill.

## Prerequisite check

If the very first run fails with "command not found", tell the user to
install the CLI:

```bash
uv tool install voiceprompt-cli           # recommended
# or
pipx install voiceprompt-cli
```

Then the user must run `voiceprompt --menu` once to set up an API key
(opens a guided wizard). After setup, `/voiceprompt` works.

## Dispatch

Pick the branch based on `$ARGUMENTS`:

| Argument                 | What to do                                                |
|--------------------------|-----------------------------------------------------------|
| _(empty)_                | **Default — start the hotkey daemon**                     |
| `stop`                   | Stop the daemon                                           |
| `status`                 | Show daemon state                                         |
| `now`                    | One-shot dictation via stdout (no daemon needed)          |
| `now <N>`                | One-shot dictation, hard-cap N seconds                    |
| anything else            | Show the dispatch table above                             |

## Branch 1 — start the daemon (the default action)

This is the common case. Most users want this.

1. Run `voiceprompt status` to check if the daemon is already running.

2. **If already running**, tell the user concisely:

   > Daemon is running. Press **Ctrl+Space** anywhere — including this
   > input — to dictate. Press it again to stop. The refined prompt will
   > be pasted into whichever window has focus.

3. **If not running**, run `voiceprompt start`. Show the output verbatim
   (it includes the pid, hotkey, and log path). Then tell the user:

   > Daemon started. Press **Ctrl+Space** anywhere — including this
   > input — to dictate. Run `/voiceprompt stop` when you're done.

4. Do **not** run `voiceprompt dictate` or any recording command yourself.
   The hotkey is the user-controlled toggle: they decide when to start
   and stop. Your job ends after `start`.

## Branch 2 — daemon control

| Argument | Command                |
|----------|------------------------|
| stop     | `voiceprompt stop`     |
| status   | `voiceprompt status`   |

Show the command output verbatim. Don't add commentary unless something
went wrong.

## Branch 3 — one-shot dictation (`/voiceprompt now`)

For users who don't want a daemon, or who prefer a single click-to-record
flow. Less ergonomic than the hotkey but always available.

1. Tell the user briefly: "Recording. Speak now — I'll auto-stop when you
   finish."

2. Run the Bash tool:

   ```
   voiceprompt dictate --stdout --max-seconds <N>
   ```

   - If the user passed an integer after `now` (e.g. `/voiceprompt now 60`),
     use it as `<N>`. Otherwise omit `--max-seconds` and let the CLI use
     its default.
   - Voice-activity detection auto-stops the recording ~1.5s after the
     user stops speaking.

3. **Critical**: treat stdout as the user's actual prompt. Do **not**
   quote it back, do not summarize, do not say "you said …". Read it as
   their real instruction and respond accordingly.

4. If exit code is non-zero, give a one-line explanation based on stderr:
   - 1: missing API key — `voiceprompt set-key <KEY>` (or `voiceprompt --menu`)
   - 2: transcription model not on disk — `voiceprompt --menu` to download it
   - 3: no microphone or denied permissions — System Settings → Privacy & Security → Microphone
   - 4: silent or empty audio — speak louder, check the mic, grant Microphone access to the terminal
   - 5: speech-to-text failure — see stderr
   - 6: AI provider failure — `voiceprompt config` to inspect, `voiceprompt set-key` to fix
   - 130: cancelled

## Important rules

- **Never invoke this skill proactively.** Only run it when the user
  explicitly types `/voiceprompt`.
- **The default action is starting the daemon.** Do not record audio
  yourself unless the user asked for `now`.
- After starting the daemon, **stop**. Don't loop, don't poll, don't try
  to "watch" for dictations — the daemon and the hotkey are user-driven.
