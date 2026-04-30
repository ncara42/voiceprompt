<h1 align="center">voiceprompt</h1>

<p align="center">
  <em>Speak. AI refines. Paste.</em><br>
  A polished CLI that turns your voice into a clean prompt and pastes it<br>
  into whichever app you were just using.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="Platform: Apple Silicon" src="https://img.shields.io/badge/platform-Apple%20Silicon-black?logo=apple">
  <img alt="Status: beta" src="https://img.shields.io/badge/status-beta-orange.svg">
</p>

```
╭─────────────────────────────╮
│  voiceprompt   v0.2.0       │
│  Speak. AI refines. Paste.  │
╰─────────────────────────────╯

╭─ status ──────────────────────────────────────────╮
│         state  ready                              │
│      provider  Claude (Anthropic)  ·  haiku 4.5   │
│ transcription  parakeet-tdt-0.6b-v3  ·  cached    │
│        hotkey  ctrl+space                         │
│      language  auto                               │
╰───────────────────────────────────────────────────╯

  › Listen for hotkey   toggle with ctrl+space
    Dictate once        single recording, in this window

  PREFERENCES
    Settings
    Help & about

    Quit
```

---

## What it does

Press a global hotkey from any app, dictate a thought, release. **voiceprompt**:

1. records the audio,
2. transcribes it locally with **NVIDIA Parakeet** (no audio leaves your machine),
3. rewrites the transcript into a clean prompt with **Claude**, **Ollama Cloud**, or **Google Gemini**,
4. pastes the result into whichever window had focus when you stopped recording — Claude Code, Gemini CLI, OpenCode, Codex, an editor, your browser, anything.

It is built for people who already have a coding agent open all day and want to talk to it instead of typing.

---

## Highlights

- **Three AI providers, swap any time** — Anthropic Claude (paid, best quality), Ollama Cloud (free tier with `gpt-oss` / `qwen3-coder`), Google Gemini (generous free tier on `gemini-2.5-flash`).
- **Local speech-to-text** — Parakeet-TDT-0.6B-v3 runs on your Mac via MLX. Your voice never hits the cloud.
- **One global hotkey** — `voiceprompt listen` runs in the background. Toggle recording from any app with `ctrl+space` (configurable).
- **Pastes into whichever window has focus** — the daemon never steals focus, so the prompt lands wherever you were already typing. Works for any terminal-based agent CLI, editor, or chat box without configuration.
- **Polished TUI** — a sectioned menu, aligned status panel, guided first-run setup, hierarchical settings.
- **Secure by default** — API keys saved with `0600` perms; error messages redact secrets; the process renames itself from "Python" to "voiceprompt" in macOS perm prompts and Activity Monitor.

---

## Requirements

| Requirement     | Notes                                                                          |
| --------------- | ------------------------------------------------------------------------------ |
| **macOS**       | Apple Silicon (M-series). Parakeet runs on MLX.                                |
| **Python**      | 3.10 or newer.                                                                 |
| **AI provider** | One API key from Anthropic, Ollama Cloud, or Google AI Studio (free tiers OK). |
| **Disk**        | ~1.2 GB for the default Parakeet model (one-time download).                    |

Linux/Windows: most of the pipeline still works (recording, providers, paste), but the transcription step requires Apple Silicon today. Ports welcome.

---

## Install

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli
cd voiceprompt-cli
./install.sh
```

The installer auto-detects `uv` → `pipx` → `pip --user` and installs the `voiceprompt` binary to `~/.local/bin/`. Output is silent on success; failures replay the full log to stderr.

Manual options:

```bash
uv tool install .                     # recommended
pipx install .
pip install --user .
```

To uninstall: `./install.sh --uninstall`.

---

## Quick start

```bash
voiceprompt
```

The first run shows **Set up voiceprompt**, a guided three-step wizard:

1. Pick a provider (Claude / Ollama Cloud / Gemini).
2. Paste your API key — it's prompted via hidden stdin.
3. Optionally ping the provider to verify the connection.

Then pick **Listen for hotkey** and you're ready: press `ctrl+space` from any app to dictate.

> **Get a key:** [Anthropic](https://console.anthropic.com/settings/keys) · [Ollama](https://ollama.com/settings/keys) · [Google AI Studio](https://aistudio.google.com/apikey)

---

## Usage

### Daemon mode (recommended)

```bash
voiceprompt listen
```

Runs in the background listening for the global hotkey. First press starts recording; second press stops, transcribes, refines, and pastes. `Ctrl+C` in the daemon window quits.

Flags:

```bash
voiceprompt listen --hotkey ctrl+shift+space
voiceprompt listen --no-paste               # clipboard only, no auto-paste
```

### Interactive menu

```bash
voiceprompt
```

The menu also exposes the daemon, a one-shot dictation, settings, and help screens.

### Other commands

| Command                                       | What it does                                              |
| --------------------------------------------- | --------------------------------------------------------- |
| `voiceprompt dictate`                         | One dictation in the current terminal; no auto-paste.     |
| `voiceprompt set-key --provider claude <KEY>` | Save an API key without opening the menu.                 |
| `voiceprompt config`                          | Show the active config (paths, models, key state).        |
| `voiceprompt --version`                       | Print the version.                                        |
| `voiceprompt --help`                          | All flags.                                                |

---

## Providers

| Provider        | Default model            | Cost                            | Notes                                                          |
| --------------- | ------------------------ | ------------------------------- | -------------------------------------------------------------- |
| Anthropic Claude| `claude-haiku-4-5`       | paid                            | Best quality. `sonnet-4-6` and `opus-4-7` available.           |
| Ollama Cloud    | `gpt-oss:120b`           | free tier · paid extras         | Open-weight models including `gpt-oss:20b`, `qwen3-coder:480b`.|
| Google Gemini   | `gemini-2.5-flash`       | free tier · 15 RPM, 1500 RPD    | Closest free analog to Haiku. `gemini-2.5-pro` for better quality.|

Switch providers from **Settings → AI provider**. Switching is instant — pick a model and a key per provider, voiceprompt remembers each.

---

## Transcription models

Parakeet variants exposed in **Settings → Transcription model**:

| Model                                  | Languages          | Size     | Notes                              |
| -------------------------------------- | ------------------ | -------- | ---------------------------------- |
| `mlx-community/parakeet-tdt-0.6b-v3`   | 25 European langs  | ~1.2 GB  | Default. Auto-detects language.    |
| `mlx-community/parakeet-tdt-0.6b-v2`   | English            | ~1.2 GB  | Slightly faster on English-only.   |
| `mlx-community/parakeet-rnnt-1.1b`     | English            | ~2.3 GB  | Larger, marginally more accurate.  |

Models are downloaded on first use and cached at `~/.cache/huggingface/`. `hf-transfer` is enabled by default for parallel downloads — set `HF_HUB_ENABLE_HF_TRANSFER=0` to opt out.

---

## macOS permissions

Grant these the first time the OS prompts (System Settings → Privacy & Security):

| Permission           | Why voiceprompt needs it                                   |
| -------------------- | ---------------------------------------------------------- |
| **Microphone**       | Records audio from the default input device.               |
| **Input Monitoring** | Listens for the global hotkey while in the background.     |
| **Accessibility**    | Simulates `Cmd+V` to paste the refined prompt into focus.  |

The permission prompts identify the app as **voiceprompt** (not "Python") thanks to a `setproctitle` + `NSBundle.CFBundleName` patch applied at startup.

---

## Auto-start at login

| OS      | How                                                                                       |
| ------- | ----------------------------------------------------------------------------------------- |
| macOS   | Add `voiceprompt listen` to **Login Items**, or wrap it in a `launchd` plist.             |
| Linux   | A `systemd --user` service running `voiceprompt listen`.                                  |
| Windows | Task Scheduler at logon → `voiceprompt listen`.                                           |

Combine with a custom hotkey (Raycast / Alfred / Hammerspoon / Apple Shortcuts) if you'd rather not have a daemon resident.

---

## Configuration file

JSON, written atomically with `0600` permissions:

| OS      | Path                                                    |
| ------- | ------------------------------------------------------- |
| macOS   | `~/Library/Application Support/voiceprompt/config.json` |
| Linux   | `~/.config/voiceprompt/config.json`                     |
| Windows | `%APPDATA%\voiceprompt\config.json`                     |

Editable from **Settings** in the menu, or directly with your editor.

---

## How it works

```
   ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌────────────┐
   │  microphone  │ → │  Parakeet (MLX)  │ → │  Claude / Ollama │ → │   paste    │
   │  16 kHz mono │   │  local, on-device│   │   Cloud / Gemini │   │  ⌘V / ^V   │
   └──────────────┘   └──────────────────┘   └──────────────────┘   └────────────┘
                                                       ↑
                                              system prompt
                                              (configurable)
```

1. **Recording** — `sounddevice` captures mono PCM at 16 kHz from the default mic. A live waveform renders in the terminal while you talk.
2. **Transcription** — `parakeet-mlx` runs Parakeet-TDT on the Apple Silicon GPU. The audio file is deleted right after.
3. **Refinement** — only the *text* transcript is sent to the active provider, paired with your system prompt, asking for a single clean prompt in the original language.
4. **Delivery** — the result is copied to the clipboard. If a paste target was found (an agent CLI session via PID + TTY — Claude Code / Gemini / OpenCode / Codex — or the frontmost app), `Cmd+V` / `Ctrl+V` is simulated there. Otherwise, paste it yourself.

---

## Privacy & security

- **Audio never leaves your machine.** Transcription is 100% local; the WAV file is unlinked immediately after.
- **Only the transcript is sent to the AI provider.**
- **API keys** are stored locally with `0600` permissions, written atomically. They never appear in logs or error messages — there are explicit redaction patterns for `sk-ant-*`, `Bearer …`, and `AIza*` tokens.
- **No telemetry.** No analytics, no remote calls beyond the chosen AI provider.
- **No-paste mode** (`--no-paste`) skips automation entirely if you'd rather paste manually.

Found a security issue? See [`SECURITY.md`](SECURITY.md).

---

## Environment variables

| Variable                       | Effect                                                                |
| ------------------------------ | --------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`            | Pre-fills the Claude key on first config load.                        |
| `OLLAMA_API_KEY`               | Pre-fills the Ollama Cloud key on first config load.                  |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Pre-fills the Gemini key on first config load.                   |
| `HF_TOKEN`                     | Hugging Face token for higher download rate limits.                   |
| `HF_HUB_ENABLE_HF_TRANSFER=0`  | Disables the Rust parallel downloader (enabled by default).           |

---

## Development

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli
cd voiceprompt-cli
uv sync --group dev

uv run voiceprompt              # run from source without installing
uv run python -m unittest       # run the test suite
uv run ruff check src/ tests/   # lint
```

After editing source, reinstall the global binary so the `voiceprompt` command picks up your changes:

```bash
./install.sh --uv
```

(Without this, `uv tool install --force` may reuse a cached wheel and miss your edits.)

---

## Roadmap

- [ ] Linux/Windows transcription (e.g. ONNX Parakeet via `parakeet-rs`).
- [ ] Streaming transcription with progressive refinement.
- [ ] Custom system-prompt presets (one for chat, one for code, one for commit messages).
- [ ] Local Ollama (no cloud) as a fourth provider option.
- [ ] Native macOS menu bar app for users who don't want a terminal daemon.

PRs welcome.

---

## License

[MIT](LICENSE) © Noel Caravaca.

The original Swift/macOS prototype is preserved in [`legacy/swift-macos/`](legacy/swift-macos/) for historical reference. The current codebase is pure Python.
