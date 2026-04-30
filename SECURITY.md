# Security Policy

## Reporting a Vulnerability

If you find a security issue in voiceprompt:

1. **Do not** open a public GitHub issue.
2. Email the maintainer: `noel@noelcaravaca.com`.
3. Include a clear description, reproduction steps, and the impact you can demonstrate.

You will get a reply within a reasonable timeframe. Confirmed issues will be fixed
on a private branch and disclosed in the changelog after a coordinated release.

## Scope

Issues considered in scope:

- Anything that could leak the user's API key/token (Anthropic, Ollama, Gemini,
  GitHub Models, Hugging Face).
- Command/script injection through CLI flags or config values
  (especially the AppleScript / xdotool / wmctrl backends in `inject.py`).
- Audio data leaving the machine through any path other than local
  transcription.
- Privilege escalation or escape from the sandboxed config / temp directories.

Out of scope:

- Issues that require the attacker to already have local code execution as the user.
- Vulnerabilities in upstream dependencies (`anthropic`, `faster-whisper`, `pynput`,
  `pyperclip`, `prompt_toolkit`...) — please report those upstream. We track
  advisories via Dependabot and update reasonably promptly.
- Missing rate-limiting on the local CLI.

## What we already do

- API key stored locally with `0o600` permissions, written atomically.
- Error messages from provider clients are redacted to strip anything that
  matches `sk-ant-*`, `AIza*`, GitHub `github_pat_*` / `ghp_*`, bearer tokens,
  or API-key headers before being shown.
- AppleScript invocations pass user-controlled strings as `osascript` `on run argv`
  arguments, never interpolated into the script source.
- Audio is transcribed locally (faster-whisper) and never uploaded anywhere by us.
- Recorded WAVs live only in the OS temp directory and are deleted as soon as the
  reformulation finishes (or the dictation is cancelled).
