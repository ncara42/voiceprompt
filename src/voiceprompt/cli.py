"""Top-level CLI: entry point invoked by `voiceprompt`."""

from __future__ import annotations

# Run before anything that may initialize AppKit (pynput in particular). Once
# NSApplication latches onto the original "Python" name the menu bar / dock
# label can't be changed for the lifetime of the process.
from voiceprompt import proctitle  # noqa: I001 -- intentional: keep before other imports

proctitle.apply()

import typer  # noqa: E402

from voiceprompt import __version__  # noqa: E402
from voiceprompt import config as cfg_mod  # noqa: E402
from voiceprompt.menu import run_menu  # noqa: E402
from voiceprompt.styles import console  # noqa: E402

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Speak. AI refines. Paste: record, refine, and copy prompts.",
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"voiceprompt [brand]{__version__}[/brand]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version."
    ),
    menu: bool = typer.Option(
        False,
        "--menu",
        "-m",
        help="Open the interactive menu instead of auto-starting the daemon.",
    ),
) -> None:
    """Default action: start the listen daemon in the background.

    When voiceprompt is fully configured, running `voiceprompt` with no
    subcommand spawns the global-hotkey daemon and returns to the shell
    immediately — press the hotkey from any window to dictate. If the
    daemon is already running, prints its status and exits cleanly.

    If the user has not yet configured an API key, falls back to the
    interactive setup wizard. Pass --menu to open the menu explicitly.
    """
    if ctx.invoked_subcommand is not None:
        return

    config = cfg_mod.load()

    if menu or not config.is_configured:
        try:
            run_menu(config)
        except KeyboardInterrupt:
            console.print("\n  [hint]Interrupted.[/hint]\n")
        return

    # Configured: behave like `voiceprompt start` but idempotent.
    pid = _read_daemon_pid(_daemon_pid_path())
    if pid is not None and _process_alive(pid):
        log_path = _daemon_log_path()
        console.print(
            f"  [ok]daemon: running[/ok] [hint](pid {pid})[/hint]\n"
            f"  Hotkey:  [accent2]{config.hotkey}[/accent2]\n"
            f"  Log:     [hint]{log_path}[/hint]\n"
            f"  [hint]voiceprompt --menu[/hint] to open settings, "
            f"[hint]voiceprompt stop[/hint] to stop."
        )
        return

    _start_daemon_background(config, hotkey=None, no_paste=False)
    console.print(
        "  [hint]Press the hotkey from any window to dictate. "
        "Run [/hint][value]voiceprompt stop[/value][hint] when done.[/hint]"
    )


@app.command("set-key")
def set_key(
    api_key: str = typer.Argument(
        None,
        help="API key for the chosen provider. If omitted, it is requested through hidden "
        "stdin (safer: it does not stay in shell history).",
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help=(
            "Provider to set the key for: 'claude', 'ollama', 'gemini', or "
            "'github_models'. Defaults to the active provider."
        ),
    ),
) -> None:
    """Save the API key for a provider without opening the interactive menu."""
    from voiceprompt import claude as claude_mod  # noqa: PLC0415
    from voiceprompt import gemini as gemini_mod  # noqa: PLC0415
    from voiceprompt import github_models as github_models_mod  # noqa: PLC0415
    from voiceprompt import ollama as ollama_mod  # noqa: PLC0415
    from voiceprompt import reformulator as ref  # noqa: PLC0415
    from voiceprompt import select as sel  # noqa: PLC0415

    config = cfg_mod.load()
    target = ref.normalize(provider) if provider else ref.active_provider(config)
    label = ref.PROVIDER_LABELS[target]

    if api_key is None:
        try:
            api_key = sel.password_input(f"Paste your {label} API key:")
        except KeyboardInterrupt:
            console.print("[warn]cancelled.[/warn]")
            raise typer.Exit(code=1) from None
        if not api_key:
            console.print("[warn]cancelled.[/warn]")
            raise typer.Exit(code=1)

    api_key = api_key.strip()
    if target == "ollama":
        if not ollama_mod.looks_like_ollama_key(api_key):
            console.print(
                "[warn]Warning:[/warn] the key looks unusually short. "
                "I will save it anyway; if it fails, paste it again."
            )
        config.ollama_api_key = api_key
    elif target == "gemini":
        if not gemini_mod.looks_like_gemini_key(api_key):
            console.print(
                "[warn]Warning:[/warn] the key does not start with 'AIza' like AI Studio "
                "keys usually do. I will save it anyway; if it fails, paste it again."
            )
        config.gemini_api_key = api_key
    elif target == "github_models":
        if not github_models_mod.looks_like_github_token(api_key):
            console.print(
                "[warn]Warning:[/warn] the token does not look like a GitHub PAT/token. "
                "I will save it anyway; if it fails, paste it again."
            )
        config.github_models_token = api_key
    else:
        if not claude_mod.looks_like_anthropic_key(api_key):
            console.print(
                "[warn]Warning:[/warn] the key does not start with 'sk-ant-' like Anthropic "
                "keys usually do. I will save it anyway; if it fails, paste it again."
            )
        config.anthropic_api_key = api_key

    path = cfg_mod.save(config)
    console.print(f"[ok]{label} API key saved to[/ok] [hint]{path}[/hint]")


@app.command("config")
def show_config() -> None:
    """Show the path and contents (without the key) of the config file."""
    from voiceprompt import reformulator as ref  # noqa: PLC0415

    config = cfg_mod.load()
    provider = ref.active_provider(config)
    console.print(f"[label]Path:[/label] [value]{cfg_mod.config_path()}[/value]")
    console.print(f"[label]Provider:[/label] [value]{ref.PROVIDER_LABELS[provider]}[/value]")
    console.print(f"[label]Claude model:[/label] [value]{config.model}[/value]")
    console.print(f"[label]Ollama model:[/label] [value]{config.ollama_model}[/value]")
    console.print(f"[label]Gemini model:[/label] [value]{config.gemini_model}[/value]")
    console.print(f"[label]GitHub Models model:[/label] [value]{config.github_models_model}[/value]")
    console.print(f"[label]Transcription model:[/label] [value]{config.transcription_model}[/value]")
    console.print(f"[label]Language:[/label] [value]{config.language}[/value]")
    console.print(f"[label]Sample rate:[/label] [value]{config.sample_rate} Hz[/value]")
    anthropic_state = "configured" if config.anthropic_api_key.strip() else "—"
    ollama_state = "configured" if config.ollama_api_key.strip() else "—"
    gemini_state = "configured" if config.gemini_api_key.strip() else "—"
    github_state = "configured" if config.github_models_token.strip() else "—"
    console.print(f"[label]Anthropic key:[/label] [value]{anthropic_state}[/value]")
    console.print(f"[label]Ollama key:[/label] [value]{ollama_state}[/value]")
    console.print(f"[label]Gemini key:[/label] [value]{gemini_state}[/value]")
    console.print(f"[label]GitHub token:[/label] [value]{github_state}[/value]")
    history_state = "on" if config.history_enabled else "off"
    console.print(
        f"[label]History:[/label] [value]{history_state}[/value]  "
        f"[hint](max {config.history_max_entries} entries)[/hint]"
    )


@app.command("dictate")
def dictate_oneshot(
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help=(
            "Headless mode: print only the refined prompt to stdout (no TUI, no "
            "clipboard, no paste). Diagnostics go to stderr. Auto-stops on "
            "extended silence (see --silence) or after --max-seconds, whichever "
            "comes first. Designed for piping into editors, plugins, and scripts."
        ),
    ),
    max_seconds: int = typer.Option(
        120,
        "--max-seconds",
        help="Hard cap on recording duration. Always enforced as a safety net.",
    ),
    silence_seconds: float = typer.Option(
        1.5,
        "--silence",
        help=(
            "Auto-stop after this many seconds of silence FOLLOWING detected "
            "speech (in --stdout mode). Set to 0 to disable and rely solely "
            "on --max-seconds."
        ),
    ),
) -> None:
    """Shortcut: one dictation session and exit (does not open the menu)."""
    config = cfg_mod.load()
    if not config.is_configured:
        message = "Missing API key. Run `voiceprompt set-key <KEY>`."
        if stdout:
            import sys  # noqa: PLC0415

            print(f"voiceprompt: {message}", file=sys.stderr)
        else:
            console.print(f"[err]{message}[/err]")
        raise typer.Exit(code=1)

    if stdout:
        _dictate_headless(
            config,
            max_seconds=max_seconds,
            silence_seconds=silence_seconds,
        )
        return

    from voiceprompt.menu import _action_dictate  # noqa: PLC0415

    _action_dictate(config)


def _dictate_headless(
    config,
    *,
    max_seconds: int,
    silence_seconds: float = 1.5,
) -> None:
    """Record → transcribe → refine → print prompt to stdout. No TUI, no side effects.

    Stops when (whichever comes first):
      * Enter on stdin (only if stdin is a TTY),
      * after ``silence_seconds`` of silence following detected speech (VAD),
      * after ``max_seconds`` (hard cap),
      * SIGINT is received (cancels the cycle, no output).

    Exit codes:
      0  success — the refined prompt was printed to stdout
      1  configuration / generic failure
      2  transcription model not present on disk
      3  microphone unavailable
      4  silent or empty audio
      5  STT failure
      6  AI provider failure
      130 cancelled by SIGINT
    """
    import contextlib  # noqa: PLC0415
    import select  # noqa: PLC0415
    import sys  # noqa: PLC0415
    import time  # noqa: PLC0415

    from voiceprompt import history as hist  # noqa: PLC0415
    from voiceprompt import recorder as rec_mod  # noqa: PLC0415
    from voiceprompt import reformulator as ref  # noqa: PLC0415
    from voiceprompt import transcriber as tr  # noqa: PLC0415

    # Voice-activity detection thresholds. Values are int16 peak amplitude per
    # audio callback (one chunk ~= 60–100 ms at 16 kHz). The hysteresis gap
    # between the speech and silence levels avoids flapping on the boundary.
    _SPEECH_PEAK = 500
    _SILENCE_PEAK = 200
    _POLL_INTERVAL = 0.1

    def _err(msg: str) -> None:
        print(f"voiceprompt: {msg}", file=sys.stderr, flush=True)

    if not tr.is_model_on_disk(config.transcription_model):
        _err(
            f"transcription model '{config.transcription_model}' is not on disk. "
            f"Run `voiceprompt dictate` once interactively to download it."
        )
        raise typer.Exit(code=2)

    rec = rec_mod.Recorder(sample_rate=config.sample_rate)
    try:
        rec.start()
    except rec_mod.NoInputDeviceError:
        _err("no audio input device found.")
        raise typer.Exit(code=3) from None
    except Exception as e:  # noqa: BLE001
        _err(f"could not start recorder: {e}")
        raise typer.Exit(code=3) from None

    interactive = sys.stdin.isatty()
    vad_enabled = silence_seconds > 0
    if interactive:
        _err("recording — press Enter to stop, Ctrl+C to cancel.")
    elif vad_enabled:
        _err(
            f"recording — speak now; auto-stops {silence_seconds:.1f}s after "
            f"you finish (max {max_seconds}s, Ctrl+C to cancel)."
        )
    else:
        _err(f"recording — auto-stop in {max_seconds}s (Ctrl+C to cancel).")

    started = time.monotonic()
    cancelled = False
    speech_started = False
    silence_started_at: float | None = None
    try:
        while True:
            if time.monotonic() - started >= max_seconds:
                _err(f"max duration reached ({max_seconds}s), stopping.")
                break

            # Voice-activity detection — only relevant when stdin is not a TTY.
            if vad_enabled and not interactive:
                peak = rec.latest_peak()
                if peak >= _SPEECH_PEAK:
                    speech_started = True
                    silence_started_at = None
                elif speech_started and peak < _SILENCE_PEAK:
                    if silence_started_at is None:
                        silence_started_at = time.monotonic()
                    elif (
                        time.monotonic() - silence_started_at >= silence_seconds
                    ):
                        _err(
                            f"silence detected ({silence_seconds:.1f}s), stopping."
                        )
                        break

            if interactive:
                ready, _, _ = select.select([sys.stdin], [], [], _POLL_INTERVAL)
                if ready:
                    sys.stdin.readline()
                    break
            else:
                time.sleep(_POLL_INTERVAL)
    except KeyboardInterrupt:
        cancelled = True

    record_secs = time.monotonic() - started
    result = rec.stop()

    if cancelled:
        if result is not None:
            with contextlib.suppress(OSError):
                result[0].unlink(missing_ok=True)
        _err("cancelled.")
        raise typer.Exit(code=130)
    if result is None:
        _err("recording too short.")
        raise typer.Exit(code=4)

    wav_path, _duration, peak = result
    if peak < 50:
        with contextlib.suppress(OSError):
            wav_path.unlink(missing_ok=True)
        _err(
            f"silent audio (peak={peak}). "
            "Check microphone permissions or that the device is unmuted."
        )
        raise typer.Exit(code=4)

    _err("transcribing…")
    try:
        transcript = tr.transcribe(
            wav_path,
            model_name=config.transcription_model,
            language=config.language,
        )
    except (tr.TranscriptionError, tr.ModelDownloadError) as e:
        with contextlib.suppress(OSError):
            wav_path.unlink(missing_ok=True)
        _err(f"transcription failed: {e}")
        raise typer.Exit(code=5) from None

    if not transcript or not transcript.strip():
        with contextlib.suppress(OSError):
            wav_path.unlink(missing_ok=True)
        _err("no speech detected.")
        raise typer.Exit(code=4)

    _err("refining…")
    refine_started = time.monotonic()
    try:
        prompt = ref.reformulate_text(transcript, config)
    except ref.ProviderError as e:
        with contextlib.suppress(OSError):
            wav_path.unlink(missing_ok=True)
        _err(f"provider error: {e}")
        raise typer.Exit(code=6) from None
    refine_secs = time.monotonic() - refine_started

    with contextlib.suppress(OSError):
        wav_path.unlink(missing_ok=True)

    if not prompt or not prompt.strip():
        _err("empty response from AI provider.")
        raise typer.Exit(code=6)

    if config.history_enabled:
        hist.log(
            transcript=transcript,
            prompt=prompt,
            provider=ref.active_provider(config),
            model=ref.active_model(config),
            language=config.language,
            record_secs=record_secs,
            refine_secs=refine_secs,
            max_entries=config.history_max_entries,
        )

    # The whole point: only the prompt goes to stdout.
    sys.stdout.write(prompt)
    if not prompt.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()


@app.command("history")
def history_cmd(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of recent entries to show.",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Print entries as a JSON array (newest first).",
    ),
    full: bool = typer.Option(
        False, "--full", help="Show full prompts instead of one-line previews.",
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Delete the entire history file (no confirmation).",
    ),
) -> None:
    """List recent dictations stored in the local history log.

    History is appended to history.jsonl in the config directory. Nothing
    is uploaded; the log is purely a local convenience for replay and audit.
    """
    from dataclasses import asdict  # noqa: PLC0415

    from voiceprompt import history as hist  # noqa: PLC0415

    if clear:
        hist.clear()
        console.print("[ok]history cleared.[/ok]")
        return

    entries = hist.read(limit=limit if limit > 0 else None)
    if json_out:
        import json as _json  # noqa: PLC0415

        payload = [asdict(e) for e in entries]
        console.print(_json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not entries:
        console.print(
            f"  [hint]no history yet.[/hint] [hint]Path: {hist.history_path()}[/hint]"
        )
        return

    from voiceprompt.menu import _format_relative_ts  # noqa: PLC0415

    for i, entry in enumerate(entries, start=1):
        ts = _format_relative_ts(entry.ts)
        meta = (
            f"[hint]{i:>3}  {ts:>10}  ·  {entry.provider} · "
            f"{entry.model}[/hint]"
        )
        console.print(meta)
        body = entry.prompt if full else entry.prompt.splitlines()[0] if entry.prompt else ""
        if not full and len(body) > 100:
            body = body[:97] + "…"
        console.print(f"     [value]{body}[/value]")
        console.print()


@app.command("replay")
def replay_cmd(
    index: int = typer.Option(
        1, "--index", "-n",
        help="Re-paste the Nth most recent entry. 1 = latest, 2 = second latest, …",
    ),
    no_paste: bool = typer.Option(
        False, "--no-paste", help="Only copy to clipboard, do not simulate the paste shortcut.",
    ),
) -> None:
    """Re-paste a recent prompt from history without re-recording.

    Handy when the previous paste landed in the wrong window or you want to
    insert the same prompt into a different app.
    """
    from voiceprompt import history as hist  # noqa: PLC0415
    from voiceprompt import inject as inj  # noqa: PLC0415
    from voiceprompt.clipboard import copy as clipboard_copy  # noqa: PLC0415

    if index < 1:
        console.print("[err]--index must be >= 1.[/err]")
        raise typer.Exit(code=1)

    entries = hist.read(limit=index)
    if not entries:
        console.print("  [hint]no history yet.[/hint]")
        raise typer.Exit(code=1)
    if index > len(entries):
        console.print(
            f"  [warn]only {len(entries)} entries in history.[/warn]"
        )
        raise typer.Exit(code=1)
    entry = entries[index - 1]

    if not clipboard_copy(entry.prompt):
        console.print("[warn]Could not copy to clipboard.[/warn]")
        raise typer.Exit(code=1)

    if no_paste:
        console.print("  [ok]copied to clipboard[/ok]")
        return

    if not inj.paste():
        console.print(
            f"  [warn]Could not paste automatically.[/warn] "
            f"[hint]{inj.missing_tool_hint()}[/hint]"
        )
        raise typer.Exit(code=1)
    console.print("  [ok]pasted.[/ok]")


@app.command("start")
def start_cmd(
    hotkey: str = typer.Option(
        None,
        "--hotkey",
        "-k",
        help="Override the global hotkey for this run (e.g. 'ctrl+alt+space').",
    ),
    no_paste: bool = typer.Option(
        False, "--no-paste", help="Only copy to clipboard; do not auto-paste.",
    ),
) -> None:
    """Start the listen daemon in the background and return to the shell.

    The daemon detaches from this terminal, survives shell exit, and writes
    its output to a rotating log file. Press the hotkey from any window to
    dictate, then run `voiceprompt stop` when done.
    """
    config = cfg_mod.load()
    if not config.is_configured:
        console.print("[err]Missing API key.[/err] Run [value]voiceprompt set-key <KEY>[/value]")
        raise typer.Exit(code=1)

    existing = _read_daemon_pid(_daemon_pid_path())
    if existing is not None and _process_alive(existing):
        console.print(
            f"  [warn]daemon already running[/warn] [hint](pid {existing})[/hint]\n"
            f"  Stop it first with [value]voiceprompt stop[/value]."
        )
        raise typer.Exit(code=1)

    _start_daemon_background(config, hotkey=hotkey, no_paste=no_paste)


def _start_daemon_background(config, *, hotkey: str | None, no_paste: bool) -> None:
    """Spawn `voiceprompt listen` as a detached background process.

    Writes the pid file, redirects stdout/stderr to ``daemon.log``, and prints
    a short status message. Cleans up stale pid files left by a previous crash.
    Raises ``typer.Exit`` on failure.
    """
    import contextlib  # noqa: PLC0415
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    import time  # noqa: PLC0415

    pid_path = _daemon_pid_path()
    log_path = _daemon_log_path()

    # If a pid file exists but the process is dead, drop it before starting.
    existing = _read_daemon_pid(pid_path)
    if existing is not None and not _process_alive(existing):
        with contextlib.suppress(OSError):
            pid_path.unlink()

    cmd = [sys.executable, "-m", "voiceprompt", "listen"]
    if hotkey:
        cmd.extend(["--hotkey", hotkey])
    if no_paste:
        cmd.append("--no-paste")

    try:
        log_handle = log_path.open("ab", buffering=0)
    except OSError as e:
        console.print(f"[err]Could not open daemon log {log_path}: {e}[/err]")
        raise typer.Exit(code=1) from None

    try:
        if sys.platform == "win32":
            creation_flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
            proc = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
    finally:
        with contextlib.suppress(OSError):
            log_handle.close()

    time.sleep(0.6)
    if not _process_alive(proc.pid):
        console.print(
            f"[err]daemon failed to start.[/err]  See log: [hint]{log_path}[/hint]"
        )
        raise typer.Exit(code=1)

    try:
        pid_path.write_text(str(proc.pid))
    except OSError as e:
        with contextlib.suppress(OSError):
            os.kill(proc.pid, 15)
        console.print(f"[err]Could not write pid file {pid_path}: {e}[/err]")
        raise typer.Exit(code=1) from None

    combo = hotkey or config.hotkey
    console.print(
        f"  [ok]daemon started[/ok] [hint](pid {proc.pid})[/hint]\n"
        f"  Hotkey:  [accent2]{combo}[/accent2]\n"
        f"  Log:     [hint]{log_path}[/hint]"
    )


@app.command("stop")
def stop_cmd() -> None:
    """Stop the background daemon started with `voiceprompt start`."""
    import contextlib  # noqa: PLC0415
    import os  # noqa: PLC0415
    import signal  # noqa: PLC0415
    import time  # noqa: PLC0415

    pid_path = _daemon_pid_path()
    pid = _read_daemon_pid(pid_path)
    if pid is None:
        console.print("  [hint]daemon is not running.[/hint]")
        return
    if not _process_alive(pid):
        console.print(f"  [hint]daemon was not running (stale pid {pid}).[/hint]")
        with contextlib.suppress(OSError):
            pid_path.unlink()
        return

    sig = getattr(signal, "SIGTERM", 15)
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        with contextlib.suppress(OSError):
            pid_path.unlink()
        console.print(f"  [hint]daemon already gone (pid {pid}).[/hint]")
        return
    except OSError as e:
        console.print(f"[err]Could not stop daemon pid {pid}: {e}[/err]")
        raise typer.Exit(code=1) from None

    # Give it up to 2s to exit gracefully.
    for _ in range(20):
        if not _process_alive(pid):
            break
        time.sleep(0.1)
    if _process_alive(pid):
        kill_sig = getattr(signal, "SIGKILL", 9)
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, kill_sig)

    with contextlib.suppress(OSError):
        pid_path.unlink()
    console.print(f"  [ok]daemon stopped[/ok] [hint](pid {pid})[/hint]")


@app.command("status")
def status_cmd() -> None:
    """Show whether the background daemon is running."""
    import contextlib  # noqa: PLC0415

    pid_path = _daemon_pid_path()
    log_path = _daemon_log_path()
    pid = _read_daemon_pid(pid_path)
    if pid is None:
        console.print(
            "  [hint]daemon: not running.[/hint]\n"
            "  Start it with [value]voiceprompt start[/value]."
        )
        return
    if not _process_alive(pid):
        console.print(
            f"  [warn]daemon: stale pid file[/warn] [hint](pid {pid} not alive).[/hint]"
        )
        with contextlib.suppress(OSError):
            pid_path.unlink()
        return
    config = cfg_mod.load()
    console.print(
        f"  [ok]daemon: running[/ok] [hint](pid {pid})[/hint]\n"
        f"  Hotkey:  [accent2]{config.hotkey}[/accent2]\n"
        f"  Log:     [hint]{log_path}[/hint]"
    )


def _daemon_pid_path():
    return cfg_mod.config_dir() / "daemon.pid"


def _daemon_log_path():
    return cfg_mod.config_dir() / "daemon.log"


def _read_daemon_pid(pid_path) -> int | None:
    try:
        text = pid_path.read_text().strip()
    except (OSError, FileNotFoundError):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _process_alive(pid: int) -> bool:
    """Cross-platform liveness check that does not actually signal the process."""
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415

    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok) and exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but lives in a different uid/security context — still alive.
        return True
    except OSError:
        return False
    return True


@app.command("listen")
def listen_cmd(
    hotkey: str = typer.Option(
        None,
        "--hotkey",
        "-k",
        help="Global hotkey combination (default: config value, usually 'ctrl+space').",
    ),
    no_paste: bool = typer.Option(False, "--no-paste", help="Only copy to the clipboard."),
) -> None:
    """Daemon: listen for a global hotkey and record when pressed (toggle).

    The refined prompt is pasted into whichever window has focus when the cycle
    finishes. The daemon never steals focus, so make sure your target window
    (Claude Code, Gemini CLI, an editor, anything) is in front before pressing
    the hotkey.

    First-run macOS permissions:
      System Settings -> Privacy & Security -> Input Monitoring  (listen for the hotkey)
      System Settings -> Privacy & Security -> Accessibility     (simulate Cmd+V)
    """
    from voiceprompt.menu import _action_listen  # noqa: PLC0415

    config = cfg_mod.load()
    if not config.is_configured:
        console.print("[err]Missing API key.[/err] Run [value]voiceprompt set-key <KEY>[/value]")
        raise typer.Exit(code=1)

    _action_listen(
        config,
        hotkey_override=hotkey,
        no_paste=no_paste,
    )


if __name__ == "__main__":
    app()
