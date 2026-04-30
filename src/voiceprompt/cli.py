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
    help="Speak. Claude refines. Paste: record, refine, and copy prompts.",
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
) -> None:
    """Launch the interactive menu when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    config = cfg_mod.load()
    try:
        run_menu(config)
    except KeyboardInterrupt:
        console.print("\n  [hint]Interrupted.[/hint]\n")


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
        help="Provider to set the key for: 'claude', 'ollama', or 'gemini'. Defaults to the active provider.",
    ),
) -> None:
    """Save the API key for a provider without opening the interactive menu."""
    from voiceprompt import claude as claude_mod  # noqa: PLC0415
    from voiceprompt import gemini as gemini_mod  # noqa: PLC0415
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
    console.print(f"[label]Transcription model:[/label] [value]{config.transcription_model}[/value]")
    console.print(f"[label]Language:[/label] [value]{config.language}[/value]")
    console.print(f"[label]Sample rate:[/label] [value]{config.sample_rate} Hz[/value]")
    anthropic_state = "configured" if config.anthropic_api_key.strip() else "—"
    ollama_state = "configured" if config.ollama_api_key.strip() else "—"
    gemini_state = "configured" if config.gemini_api_key.strip() else "—"
    console.print(f"[label]Anthropic key:[/label] [value]{anthropic_state}[/value]")
    console.print(f"[label]Ollama key:[/label] [value]{ollama_state}[/value]")
    console.print(f"[label]Gemini key:[/label] [value]{gemini_state}[/value]")


@app.command("dictate")
def dictate_oneshot() -> None:
    """Shortcut: one dictation session and exit (does not open the menu)."""
    from voiceprompt.menu import _action_dictate  # noqa: PLC0415

    config = cfg_mod.load()
    if not config.is_configured:
        console.print("[err]Missing API key.[/err] Run [value]voiceprompt set-key <KEY>[/value]")
        raise typer.Exit(code=1)
    _action_dictate(config)


@app.command("listen")
def listen_cmd(
    hotkey: str = typer.Option(
        None,
        "--hotkey",
        "-k",
        help="Global hotkey combination (default: config value, usually 'ctrl+space').",
    ),
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Force target app (skips agent CLI auto-detection).",
    ),
    no_paste: bool = typer.Option(False, "--no-paste", help="Only copy to the clipboard."),
    no_agent: bool = typer.Option(
        False,
        "--no-agent",
        help="Disable auto-detection of agent CLIs (claude / gemini / opencode / codex).",
    ),
) -> None:
    """Daemon: listen for a global hotkey and record when pressed (toggle).

    Auto-detects any open agent CLI (Claude Code, Gemini CLI, OpenCode, Codex)
    and pastes the refined prompt into its terminal pane. Falls back to the
    frontmost app when no agent is running.

    Press the hotkey once to start recording, then press it again (or Enter in
    the voiceprompt window) to stop.

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
        target=target,
        no_paste=no_paste,
        no_agent=no_agent,
    )


if __name__ == "__main__":
    app()
