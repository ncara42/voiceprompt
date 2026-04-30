<h1 align="center">voiceprompt</h1>

<p align="center">
  <em>Speak. AI refines. Paste.</em><br>
  A polished CLI that turns your voice into a clean prompt and pastes it<br>
  into whichever app you were just using.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey">
  <img alt="Status: beta" src="https://img.shields.io/badge/status-beta-orange.svg">
  <a href="https://github.com/noelcaravaca/voiceprompt-cli/actions"><img alt="CI" src="https://github.com/noelcaravaca/voiceprompt-cli/actions/workflows/ci.yml/badge.svg"></a>
</p>

```
╭─────────────────────────────╮
│  voiceprompt   v0.3.0       │
│  Speak. AI refines. Paste.  │
╰─────────────────────────────╯

╭─ status ──────────────────────────────────────────╮
│         state  ready                              │
│      provider  Claude (Anthropic)  ·  haiku 4.5   │
│ transcription  distil-large-v3  ·  cached         │
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
2. transcribes it locally with **faster-whisper** (no audio leaves your machine),
3. rewrites the transcript into a clean prompt with **Claude**, **Ollama Cloud**, **Google Gemini**, or **GitHub Models**,
4. pastes the result into whichever window had focus when you stopped recording — Claude Code, Gemini CLI, OpenCode, Codex, an editor, your browser, anything.

It is built for people who already have a coding agent open all day and want to talk to it instead of typing.

---

## Highlights

- **Cross-platform** — runs on macOS (Intel + Apple Silicon), Linux, and Windows from a single code path. CUDA `float16` is used automatically when an NVIDIA GPU is present; otherwise CPU `int8` for fast inference everywhere.
- **Four AI providers, swap any time** — Anthropic Claude (paid, best quality), Ollama Cloud (free tier with `gpt-oss` / `qwen3-coder`), Google Gemini (generous free tier on `gemini-2.5-flash`), and GitHub Models for Copilot/GitHub ecosystem users.
- **Local speech-to-text** — `faster-whisper` runs entirely on-device. Default model is `distil-large-v3` (~95 % of `large-v3` quality at roughly 2× the speed). Six models selectable from the settings menu.
- **One global hotkey** — `voiceprompt listen` runs in the background. Toggle recording from any app with `ctrl+space` (configurable).
- **Pastes into whichever window has focus** — the daemon never steals focus, so the prompt lands wherever you were already typing. Works for any terminal-based agent CLI, editor, or chat box without configuration.
- **Polished TUI** — a sectioned menu, aligned status panel, guided first-run setup, hierarchical settings.
- **Secure by default** — API keys saved with `0600` perms; error messages redact secrets; the process renames itself from "Python" to "voiceprompt" in macOS perm prompts and Activity Monitor.

---

## Requirements

| Requirement     | Notes                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------- |
| **OS**          | macOS 12+ (Intel or Apple Silicon), Linux (X11 or Wayland), Windows 10/11.                |
| **Python**      | 3.10 or newer.                                                                            |
| **AI provider** | One API key/token from Anthropic, Ollama Cloud, Google AI Studio, or GitHub Models.       |
| **Disk**        | ~1.5 GB for the default `distil-large-v3` model (one-time download). Smaller models from ~75 MB are also available. |
| **Linux only**  | `xdotool` (X11) or `wtype` (Wayland) for paste injection; `xclip` or `xsel` for clipboard. |

---

## Install

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli
cd voiceprompt-cli
./install.sh
```

The installer auto-detects `uv` → `pipx` → `pip --user` and installs the `voiceprompt` binary to `~/.local/bin/`.

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

1. Pick a provider (Claude / Ollama Cloud / Gemini / GitHub Models).
2. Paste your API key — it's prompted via hidden stdin.
3. Optionally ping the provider to verify the connection.

Then pick **Listen for hotkey** and you're ready: press `ctrl+space` from any app to dictate.

> **Get a key:** [Anthropic](https://console.anthropic.com/settings/keys) · [Ollama](https://ollama.com/settings/keys) · [Google AI Studio](https://aistudio.google.com/apikey) · [GitHub token](https://github.com/settings/personal-access-tokens) with `models: read`

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

### Background daemon (no terminal needed)

```bash
voiceprompt start            # detach as a background process
voiceprompt status           # show PID and uptime
voiceprompt stop             # terminate cleanly
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
| `voiceprompt history`                         | List recent dictations.                                   |
| `voiceprompt replay <id>`                     | Re-paste a recent prompt without re-recording.            |
| `voiceprompt set-key --provider claude <KEY>` | Save an API key without opening the menu.                 |
| `voiceprompt config`                          | Show the active config (paths, models, key state).        |
| `voiceprompt --version`                       | Print the version.                                        |
| `voiceprompt --help`                          | All flags.                                                |

---

## Providers

| Provider         | Default model          | Cost                            | Notes                                                          |
| ---------------- | ---------------------- | ------------------------------- | -------------------------------------------------------------- |
| Anthropic Claude | `claude-haiku-4-5`     | paid                            | Best quality. `sonnet-4-6` and `opus-4-7` available.           |
| Ollama Cloud     | `gpt-oss:120b`         | free tier · paid extras         | Open-weight models including `gpt-oss:20b`, `qwen3-coder:480b`.|
| Google Gemini    | `gemini-2.5-flash`     | free tier · 15 RPM, 1500 RPD    | Closest free analog to Haiku. `gemini-2.5-pro` for better quality.|
| GitHub Models    | `openai/gpt-4o-mini`   | GitHub Models / Copilot billing | Uses a GitHub token with `models: read`; `gpt-5-mini` is available but stricter. |

Switch providers from **Settings → AI provider**. Switching is instant — pick a model and a key per provider, voiceprompt remembers each.

---

## Transcription models

`faster-whisper` variants exposed in **Settings → Transcription model**:

| Model              | Approx. size | Notes                                                |
| ------------------ | ------------ | ---------------------------------------------------- |
| `distil-large-v3`  | ~1.5 GB      | **Default.** ~95 % of `large-v3` quality at ~2× speed.|
| `large-v3`         | ~3.0 GB      | Best accuracy. Slower on CPU; fast on GPU.           |
| `medium`           | ~1.5 GB      | Good balance.                                        |
| `small`            | ~480 MB      | Fast on CPU, decent accuracy.                        |
| `base`             | ~145 MB      | Very fast, basic accuracy.                           |
| `tiny`             | ~75 MB       | Fastest, lowest accuracy.                            |

All variants support 99 languages with automatic detection. Models are downloaded on first use and cached at `~/.cache/huggingface/`. `hf-transfer` is enabled by default for parallel downloads — set `HF_HUB_ENABLE_HF_TRANSFER=0` to opt out.

---

## OS permissions

### macOS

Grant these the first time the OS prompts (System Settings → Privacy & Security):

| Permission           | Why voiceprompt needs it                                   |
| -------------------- | ---------------------------------------------------------- |
| **Microphone**       | Records audio from the default input device.               |
| **Input Monitoring** | Listens for the global hotkey while in the background.     |
| **Accessibility**    | Simulates `Cmd+V` to paste the refined prompt into focus.  |

The permission prompts identify the app as **voiceprompt** (not "Python") thanks to a `setproctitle` + `NSBundle.CFBundleName` patch applied at startup.

### Linux

- **X11:** install `xdotool` for paste injection and `xclip` (or `xsel`) for clipboard.
- **Wayland:** install `wtype` for paste injection. Some compositors may also require running the daemon under the same user session.

### Windows

No special configuration. Hotkey, paste, and clipboard work via the Win32 APIs.

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
   │  microphone  │ → │  faster-whisper  │ → │ Claude / Ollama  │ → │   paste    │
   │  16 kHz mono │   │  local, on-device│   │ Gemini / GitHub  │   │  ⌘V / ^V   │
   └──────────────┘   └──────────────────┘   └──────────────────┘   └────────────┘
                                                       ↑
                                              system prompt
                                              (configurable)
```

1. **Recording** — `sounddevice` captures mono PCM at 16 kHz from the default mic. A live waveform renders in the terminal while you talk.
2. **Transcription** — `faster-whisper` (CTranslate2 implementation of Whisper) runs the chosen model locally. The audio file is deleted right after.
3. **Refinement** — only the *text* transcript is sent to the active provider, paired with your system prompt, asking for a single clean prompt in the original language.
4. **Delivery** — the result is copied to the clipboard, then `Cmd+V` (macOS) / `Ctrl+V` (Linux/Windows) is simulated against whichever window has focus.

---

## Source layout

```
src/voiceprompt/
├── cli.py           # Typer entry point
├── config.py        # User config (JSON, OS-appropriate dir)
├── history.py       # Local history (JSONL)
├── reformulator.py  # Provider-agnostic dispatcher
├── audio/           # Microphone capture + speech-to-text
├── providers/       # LLM providers (Claude, Ollama, Gemini, GitHub Models)
├── system/          # OS integration (hotkey, paste, clipboard, proctitle)
└── ui/              # Rich/prompt_toolkit menu + visualizer
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev loop.

---

## Privacy & security

- **Audio never leaves your machine.** Transcription is 100 % local; the WAV file is unlinked immediately after.
- **Only the transcript is sent to the AI provider.**
- **API keys** are stored locally with `0600` permissions, written atomically. They never appear in logs or error messages — there are explicit redaction patterns for `sk-ant-*`, `Bearer …`, `AIza*`, and GitHub `github_pat_*` / `ghp_*` tokens.
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
| `GITHUB_MODELS_TOKEN` / `GITHUB_TOKEN` | Pre-fills the GitHub Models token on first config load.         |
| `HF_TOKEN`                     | Hugging Face token for higher download rate limits.                   |
| `HF_HUB_ENABLE_HF_TRANSFER=0`  | Disables the Rust parallel downloader (enabled by default).           |

---

## Development

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli
cd voiceprompt-cli
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/voiceprompt                            # run from source
.venv/bin/python -m unittest discover -s tests   # run tests
.venv/bin/ruff check src tests                   # lint
```

After editing source, the editable install picks up changes immediately. To refresh a global `pipx`/`uv` install, run `./install.sh` again.

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## Roadmap

- [ ] Streaming transcription with progressive refinement.
- [ ] Custom system-prompt presets (one for chat, one for code, one for commit messages).
- [ ] Local Ollama (no cloud) as a fourth provider option.
- [ ] Native menu bar / tray app for users who don't want a terminal daemon.

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[MIT](LICENSE) © Noel Caravaca.

The original Swift/macOS prototype is preserved in [`legacy/swift-macos/`](legacy/swift-macos/) for historical reference. The current codebase is pure Python.
