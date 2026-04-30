# voiceprompt

> Speak. **Claude** refines. Paste. Cross-platform CLI that records your dictation, transcribes it locally with **Whisper**, turns it into a clean prompt with **Anthropic Claude**, and pastes it into the **Claude Code** session you already have open — even when it is not the active window.

```
╭───────────────────────────────╮
│  voiceprompt   v0.2.0         │
│ Speak. Claude refines. Paste. │
╰───────────────────────────────╯

╭─ status ────────────────╮
│   status  ready         │
│   claude  haiku 4.5     │
│  whisper  small  cached │
│ language  en            │
╰─────────────────────────╯
```

Works on **macOS**, **Linux**, and **Windows**.

---

## How it works

1. **Recording** — `sounddevice` captures mono audio at 16 kHz from the default microphone. While recording, you see a live animated waveform (`▁▂▃▄▅▆▇█`).
2. **Local transcription** — `faster-whisper` (default model: `small`, one-time download ~480 MB) runs on CPU without uploading audio to the cloud.
3. **Prompt refinement** — the text is sent to Claude (`claude-haiku-4-5` by default) with a system prompt that asks for a clean, direct prompt ready for a coding assistant.
4. **Delivery** — the result is copied to the clipboard and automatically pasted into the detected Claude Code session (via PID + TTY + AppleScript on macOS).

---

## Installation

### Local from the repo (recommended during development)

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli
cd voiceprompt-cli
./install.sh
```

The script detects `uv` > `pipx` > `pip --user` and installs `voiceprompt` into `~/.local/bin/` (usually already in your PATH).

### Manual

```bash
# uv (recommended)
uv tool install .

# pipx
pipx install .

# pip user-level
pip install --user .
```

To uninstall: `./install.sh --uninstall`.

---

## Setup

1. Get an Anthropic API key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).
2. Configure the key:
   ```bash
   voiceprompt set-key            # prompts through hidden stdin (recommended)
   voiceprompt set-key sk-ant-... # warning: stays in shell history
   ```
   Alternative: export `ANTHROPIC_API_KEY` in your shell rc file.
3. Optional: change model, language, or system prompt in `voiceprompt` → **Advanced settings**.

The config is stored here (with `0600` permissions; the key is never world-readable):

| OS      | Path                                                    |
| ------- | ------------------------------------------------------- |
| macOS   | `~/Library/Application Support/voiceprompt/config.json` |
| Linux   | `~/.config/voiceprompt/config.json`                     |
| Windows | `%APPDATA%\voiceprompt\config.json`                    |

---

## Usage

### `voiceprompt listen` — global hotkey daemon *(recommended)*

```bash
voiceprompt listen
# Press Ctrl+Space from any app to start/stop recording.
```

Infinite loop with a global hotkey (default `ctrl+space`, configurable with `--hotkey`). Toggle: first press starts recording; second press stops, processes, and pastes into Claude Code.

### `voiceprompt` — interactive menu

```bash
voiceprompt
```

Navigate with `↑↓` / `←→` / `Enter`. Useful for setup, connection tests, input-device listing, and advanced settings.

### Other commands

```bash
voiceprompt dictate     # one dictation in this terminal; does not paste elsewhere
voiceprompt set-key     # save API key safely through hidden stdin
voiceprompt config      # show current config without the key
voiceprompt --version
voiceprompt --help
```

---

## Models

### Claude (prompt refinement)

| Model                           | Cost / latency        | When to use              |
| ------------------------------- | --------------------- | ------------------------ |
| `claude-haiku-4-5-20251001`     | cheap, fast           | default, recommended     |
| `claude-sonnet-4-6`             | medium                | better quality           |
| `claude-opus-4-7`               | expensive             | maximum quality          |

### Whisper (transcription)

Approximate model size (one-time download, stored in `~/.cache/huggingface/`):

| Model      | Size     | CPU speed       |
| ---------- | -------- | --------------- |
| `tiny`     | ~75 MB   | fastest         |
| `base`     | ~145 MB  | fast            |
| `small`    | ~480 MB  | balanced        |
| `medium`   | ~1.5 GB  | better quality  |
| `large-v3` | ~3 GB    | maximum quality |

`hf-transfer` is enabled by default for parallel downloads. Set `HF_TOKEN` (Read token from huggingface.co/settings/tokens) for higher rate limits.

---

## Permissions

### macOS (first run)

The system will request permission for each feature. Grant them under **System Settings → Privacy & Security**:

| Permission           | Used for                                             |
| -------------------- | ---------------------------------------------------- |
| **Microphone**       | recording audio                                      |
| **Accessibility**    | simulating `Cmd+V` (auto-paste)                      |
| **Automation**       | reading the active app and focusing Claude Code tabs |
| **Input Monitoring** | listening for the global hotkey (`voiceprompt listen` only) |

Enable the terminal where you run `voiceprompt` (Terminal / iTerm / Ghostty / Warp) in each relevant panel.

### Linux

- **Audio**: `libportaudio2` for capture (Debian/Ubuntu: `apt install libportaudio2 portaudio19-dev`).
- **Auto-paste**: `xdotool` (X11) or `wtype` (Wayland).
- **Window activation**: optional `wmctrl` (X11).

### Windows

No special permissions required. Detecting/focusing specific tabs inside Windows Terminal is not implemented yet; it falls back to pasting into the active app.

---

## Environment variables

| Variable                       | Effect                                                                    |
| ------------------------------ | ------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`            | Overrides the key from config — useful for CI or temporary shells         |
| `HF_TOKEN`                     | Hugging Face token for higher download rate limits                        |
| `HF_HUB_ENABLE_HF_TRANSFER=0`  | Disables the Rust parallel downloader (enabled by default)                |

---

## Security

- The API key is stored **locally** with `0600` permissions (atomic write, never world-readable).
- Error messages are redacted so they never include the key.
- Audio is NOT uploaded to any cloud — transcription is 100% local with Whisper.
- Claude only receives the **transcribed text**, never the audio.
- Security reports: see [`SECURITY.md`](SECURITY.md).

---

## Development

```bash
uv sync --group dev
uv run voiceprompt
uv run ruff check src/
```

After any code change, reinstall the global binary:

```bash
./install.sh   # clears uv cache and reinstalls
```

(Without this, `uv tool install --force` can reuse a cached wheel and miss your changes.)

---

## License

MIT — see [`LICENSE`](LICENSE).

## Credits

The original Swift/macOS MVP is preserved in [`legacy/swift-macos/`](legacy/swift-macos/) for historical reference. The current version is a pure Python CLI.
