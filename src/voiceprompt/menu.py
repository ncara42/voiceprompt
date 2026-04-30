"""Interactive menu — status, navigation, settings, help.

The structure is intentionally shallow: a single status panel at the top, a main
menu with three or four primary actions, and two submenus (``Settings`` for
configuration, ``Help`` for diagnostics & docs). All selectable rows go through
``select.select`` so navigation, key bindings, and styling stay consistent.
"""

from __future__ import annotations

import contextlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import questionary
from questionary import Style as QStyle
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from voiceprompt import (
    claude,
    gemini,
    github_models,
    history,
    inject,
    ollama,
    recorder,
    reformulator,
    transcriber,
    viz,
)
from voiceprompt import config as cfg_mod
from voiceprompt import select as sel
from voiceprompt.clipboard import copy as clipboard_copy
from voiceprompt.config import Config
from voiceprompt.styles import banner, console

QSTYLE = QStyle(
    [
        ("qmark", "fg:magenta bold"),
        ("question", "bold"),
        ("answer", "fg:cyan bold"),
        ("pointer", "fg:magenta bold"),
        ("highlighted", "fg:magenta bold"),
        ("selected", "fg:cyan"),
        ("instruction", "fg:#888888 italic"),
    ]
)

LANGUAGES = ["auto", "es", "en", "fr", "de", "pt", "it"]

# ──────────────────────────────────────────────────────────────────────────────
# Top-level loop
# ──────────────────────────────────────────────────────────────────────────────


def run_menu(config: Config) -> None:
    """Top-level interactive loop. Returns when the user quits."""
    while True:
        _render_home(config)

        if not config.is_configured:
            choices = [
                sel.Choice("Set up voiceprompt", "setup", hint="guided"),
                sel.Choice("Settings", "settings", hint="advanced"),
                sel.Separator(),
                sel.Choice("Quit", "quit"),
            ]
        else:
            history_count = history.count() if config.history_enabled else 0
            history_hint = (
                f"{history_count} entries" if history_count else "empty"
            )
            choices = [
                sel.Choice(
                    "Listen for hotkey", "listen", hint=f"toggle with {config.hotkey}"
                ),
                sel.Choice("Dictate once", "dictate", hint="single recording, in this window"),
                sel.Choice("History", "history", hint=history_hint),
                sel.Separator("preferences"),
                sel.Choice("Settings", "settings"),
                sel.Choice("Help & about", "help"),
                sel.Separator(),
                sel.Choice("Quit", "quit"),
            ]

        try:
            choice = sel.select("", choices, back_value="quit", can_go_back=True)
        except KeyboardInterrupt:
            choice = "quit"

        if choice in (None, "quit"):
            console.print("\n  [hint]bye.[/hint]\n")
            return
        if choice == "setup":
            _action_setup(config)
        elif choice == "settings":
            _action_settings(config)
        elif choice == "help":
            _action_help(config)
        elif choice == "listen":
            _action_listen(config)
        elif choice == "dictate":
            _action_dictate(config)
        elif choice == "history":
            _action_history(config)


# ──────────────────────────────────────────────────────────────────────────────
# Setup wizard (first-run flow)
# ──────────────────────────────────────────────────────────────────────────────


def _action_setup(config: Config) -> None:
    """Guided first-run flow: pick provider → paste key → optional connection test."""
    console.clear()
    banner(_get_version())
    console.print(_panel(
        "Three quick steps and you're ready to dictate.",
        title="Setup",
    ))
    console.print()

    # Step 1 — provider
    provider = sel.select(
        "1.  Choose an AI provider",
        [
            sel.Choice(
                "Claude  (Anthropic)", "claude",
                hint="paid · highest quality",
            ),
            sel.Choice(
                "Ollama Cloud", "ollama",
                hint="free tier · open-weight models (gpt-oss, qwen…)",
            ),
            sel.Choice(
                "Google Gemini", "gemini",
                hint="generous free tier · gemini-2.5-flash",
            ),
            sel.Choice(
                "GitHub Models", "github_models",
                hint="use a GitHub token · Copilot ecosystem",
            ),
        ],
        default=reformulator.active_provider(config),
        back_value=None,
    )
    if provider is None:
        return
    if provider != config.provider:
        config.provider = provider
        cfg_mod.save(config)

    # Step 2 — API key
    if not _set_api_key(config, provider, intro=True):
        return

    # Step 3 — optional connection test
    do_test = sel.select(
        "3.  Verify the connection?",
        [
            sel.Choice("Yes, run a quick ping", True, hint="recommended"),
            sel.Choice("Skip", False),
        ],
        default=True,
        back_value=False,
    )
    if do_test:
        _action_test(config, pause_after=False)
    _pause()


# ──────────────────────────────────────────────────────────────────────────────
# Settings submenu
# ──────────────────────────────────────────────────────────────────────────────

# Semantic temperature presets (value, label, description)
_TEMP_PRESETS: list[tuple[float, str, str]] = [
    (0.2, "Precise",  "deterministic · minimal variation"),
    (0.5, "Balanced", "accuracy with a touch of creativity"),
    (0.8, "Creative", "more expressive · exploratory"),
]


def _action_settings(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Settings")
        provider = reformulator.active_provider(config)

        # Hint for API keys group: how many are configured
        keys_configured = sum([
            bool(config.anthropic_api_key.strip()),
            bool(config.ollama_api_key.strip()),
            bool(config.gemini_api_key.strip()),
            bool(config.github_models_token.strip()),
        ])
        keys_hint = (
            f"active: {_key_state(config.active_api_key)}  ·  {keys_configured} of 4 set"
        )

        choices = [
            sel.Choice(
                "Provider & model",
                "provider_model",
                hint=f"{reformulator.PROVIDER_LABELS[provider]} · {reformulator.short_model(config)}",
            ),
            sel.Choice("API keys", "api_keys", hint=keys_hint),
            sel.Choice(
                "Transcription",
                "transcription",
                hint=f"{_short_transcription_model(config.transcription_model)} · {config.language}",
            ),
            sel.Choice(
                "Behavior",
                "behavior",
                hint="hotkey · paste · temp · prompt",
            ),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]

        try:
            choice = sel.select("", choices, back_value="back")
        except KeyboardInterrupt:
            return

        if choice in (None, "back"):
            return
        if choice == "provider_model":
            _settings_provider_model(config)
        elif choice == "api_keys":
            _settings_api_keys(config)
        elif choice == "transcription":
            _settings_transcription(config)
        elif choice == "behavior":
            _settings_behavior(config)


# ── Provider & model ──────────────────────────────────────────────────────────


def _settings_provider_model(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Settings › Provider & model", compact=True)
        provider = reformulator.active_provider(config)
        choices = [
            sel.Choice(
                "AI provider",
                "provider",
                hint=reformulator.PROVIDER_LABELS[provider],
            ),
            sel.Choice(
                "Model",
                "model",
                hint=reformulator.short_model(config),
            ),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]
        try:
            choice = sel.select("", choices, back_value="back", show_footer=False)
        except KeyboardInterrupt:
            return
        if choice in (None, "back"):
            return
        if choice == "provider":
            _settings_pick_provider(config)
        elif choice == "model":
            _settings_pick_model(config)


def _settings_pick_provider(config: Config) -> None:
    _render_home(config, subtitle="Settings › Provider", compact=True)
    picked = sel.select(
        "AI provider",
        [sel.Choice(label, key) for key, label in reformulator.PROVIDER_LABELS.items()],
        default=config.provider,
        back_value=None,
        show_footer=False,
    )
    if picked and picked != config.provider:
        config.provider = picked
        cfg_mod.save(config)
        _saved_flash()


def _settings_pick_model(config: Config) -> None:
    provider = reformulator.active_provider(config)
    if provider == "ollama":
        models, current = ollama.MODELS, config.ollama_model
    elif provider == "gemini":
        models, current = gemini.MODELS, config.gemini_model
    elif provider == "github_models":
        models, current = github_models.MODELS, config.github_models_model
    else:
        models, current = claude.MODELS, config.model

    _render_home(config, subtitle="Settings › Model", compact=True)
    picked = sel.select(
        f"{reformulator.PROVIDER_LABELS[provider]} · model",
        [sel.Choice(name, name, hint=desc) for name, desc in models],
        default=current,
        back_value=None,
        show_footer=False,
    )
    if not picked:
        return
    if provider == "ollama":
        config.ollama_model = picked
    elif provider == "gemini":
        config.gemini_model = picked
    elif provider == "github_models":
        config.github_models_model = picked
    else:
        config.model = picked
    cfg_mod.save(config)
    _saved_flash()


# ── API keys ──────────────────────────────────────────────────────────────────

_PROVIDER_KEY_FIELD = {
    "claude":        lambda c: c.anthropic_api_key,
    "ollama":        lambda c: c.ollama_api_key,
    "gemini":        lambda c: c.gemini_api_key,
    "github_models": lambda c: c.github_models_token,
}


def _settings_api_keys(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Settings › API keys", compact=True)
        active = reformulator.active_provider(config)

        # Active provider first, then the rest
        other_providers = [p for p in reformulator.PROVIDER_LABELS if p != active]

        choices: list = [
            sel.Separator("active provider"),
            sel.Choice(
                reformulator.PROVIDER_LABELS[active],
                f"key:{active}",
                hint=_key_state(_PROVIDER_KEY_FIELD[active](config)),
            ),
            sel.Separator("other providers"),
        ]
        for p in other_providers:
            choices.append(sel.Choice(
                reformulator.PROVIDER_LABELS[p],
                f"key:{p}",
                hint=_key_state(_PROVIDER_KEY_FIELD[p](config)),
            ))
        choices += [sel.Separator(), sel.Choice("Back", "back")]

        try:
            choice = sel.select("", choices, back_value="back", show_footer=False)
        except KeyboardInterrupt:
            return
        if choice in (None, "back"):
            return

        provider_key = choice.removeprefix("key:")
        _render_home(
            config,
            subtitle=f"Settings › API keys › {reformulator.PROVIDER_LABELS[provider_key]}",
            compact=True,
        )
        _set_api_key(config, provider_key, intro=False)
        _pause()


# ── Transcription ─────────────────────────────────────────────────────────────


def _settings_transcription(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Settings › Transcription", compact=True)
        choices = [
            sel.Choice(
                "Model",
                "model",
                hint=_transcription_model_hint(config.transcription_model),
            ),
            sel.Choice("Language", "language", hint=config.language),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]
        try:
            choice = sel.select("", choices, back_value="back", show_footer=False)
        except KeyboardInterrupt:
            return
        if choice in (None, "back"):
            return
        if choice == "model":
            _settings_pick_transcription_model(config)
        elif choice == "language":
            _settings_pick_language(config)


def _settings_pick_transcription_model(config: Config) -> None:
    _render_home(config, subtitle="Settings › Transcription › Model", compact=True)
    picked = sel.select(
        "Transcription model",
        [
            sel.Choice(_short_transcription_model(name), name, hint=desc)
            for name, desc in transcriber.PARAKEET_MODELS
        ],
        default=config.transcription_model,
        back_value=None,
        show_footer=False,
    )
    if not picked:
        return
    config.transcription_model = picked
    cfg_mod.save(config)
    _saved_flash()
    _ensure_transcription_model_downloaded(picked, ask_confirm=False)


def _settings_pick_language(config: Config) -> None:
    _render_home(config, subtitle="Settings › Transcription › Language", compact=True)
    picked = sel.select(
        "Dictation language",
        [
            sel.Choice(
                code, code,
                hint="Parakeet auto-detects; this only hints the AI provider"
                if code == "auto" else "",
            )
            for code in LANGUAGES
        ],
        default=config.language,
        back_value=None,
        show_footer=False,
    )
    if picked and picked != config.language:
        config.language = picked
        cfg_mod.save(config)
        _saved_flash()


# ── Behavior ──────────────────────────────────────────────────────────────────


def _settings_behavior(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Settings › Behavior", compact=True)
        temp_label = _temperature_label(config.temperature)
        choices = [
            sel.Choice("Hotkey", "hotkey", hint=config.hotkey),
            sel.Choice(
                "Auto-paste into active app",
                "clipboard",
                hint="on" if config.auto_copy_clipboard else "off",
            ),
            sel.Choice("Temperature", "temp", hint=f"{temp_label}  ({config.temperature:.2f})"),
            sel.Choice("System prompt", "prompt", hint="edit"),
            sel.Choice(
                "History log",
                "history",
                hint=("on" if config.history_enabled else "off")
                + f"  ·  {history.count()} entries",
            ),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]
        try:
            choice = sel.select("", choices, back_value="back", show_footer=False)
        except KeyboardInterrupt:
            return
        if choice in (None, "back"):
            return
        if choice == "hotkey":
            _settings_capture_hotkey(config)
        elif choice == "clipboard":
            config.auto_copy_clipboard = not config.auto_copy_clipboard
            cfg_mod.save(config)
            _saved_flash()
        elif choice == "temp":
            _settings_pick_temperature(config)
        elif choice == "prompt":
            _settings_edit_system_prompt(config)
        elif choice == "history":
            config.history_enabled = not config.history_enabled
            cfg_mod.save(config)
            _saved_flash()


def _temperature_label(temp: float) -> str:
    """Return the preset name for a temperature value, or 'Custom'."""
    for value, label, _ in _TEMP_PRESETS:
        if abs(temp - value) < 0.01:
            return label
    return "Custom"


def _settings_pick_temperature(config: Config) -> None:
    _render_home(config, subtitle="Settings › Behavior › Temperature", compact=True)
    choices = [
        sel.Choice(label, value, hint=desc)
        for value, label, desc in _TEMP_PRESETS
    ] + [
        sel.Choice("Custom…", "custom", hint="enter a value manually"),
    ]

    # Pre-select the matching preset if current temp matches one
    default_val: float | str | None = None
    for value, _, _ in _TEMP_PRESETS:
        if abs(config.temperature - value) < 0.01:
            default_val = value
            break
    if default_val is None:
        default_val = "custom"

    picked = sel.select(
        "Temperature",
        choices,
        default=default_val,
        back_value=None,
        show_footer=False,
    )
    if picked is None:
        return
    if picked == "custom":
        console.print()
        val = questionary.text(
            "Temperature (0.0 – 2.0):",
            default=str(config.temperature),
            validate=lambda x: _is_float_in_range(x, 0.0, 2.0),
            style=QSTYLE,
        ).ask()
        if not val:
            return
        new_temp = float(val)
    else:
        new_temp = float(picked)

    if abs(new_temp - config.temperature) > 0.001:
        config.temperature = new_temp
        cfg_mod.save(config)
        _saved_flash()


def _settings_capture_hotkey(config: Config) -> None:
    """Capture a new hotkey via pynput. Falls back to text input if unavailable."""
    from voiceprompt import hotkey as hk  # noqa: PLC0415

    _render_home(config, subtitle="Settings › Behavior › Hotkey", compact=True)
    console.print(
        f"  [hint]Current hotkey:[/hint]  [accent2]{config.hotkey}[/accent2]\n"
    )

    if not hk.is_supported():
        # Fallback: text input
        console.print(
            "  [hint]Examples: ctrl+space · ctrl+shift+space · cmd+option+v[/hint]"
        )
        val = questionary.text(
            "New hotkey:",
            default=config.hotkey,
            style=QSTYLE,
        ).ask()
        if val and val.strip() and val.strip() != config.hotkey:
            config.hotkey = val.strip()
            cfg_mod.save(config)
            _saved_flash()
            console.print(
                "  [hint]Restart the listen daemon for the change to take effect.[/hint]"
            )
            _pause()
        return

    # pynput capture path
    import threading  # noqa: PLC0415

    from pynput import keyboard as kb  # noqa: PLC0415

    console.print("  [brand]Press your new hotkey combination…[/brand]")
    console.print("  [hint](esc to cancel)[/hint]\n")

    captured: list[str] = []
    done = threading.Event()
    pressed: set = set()

    _MOD_NAMES = {
        kb.Key.ctrl, kb.Key.ctrl_l, kb.Key.ctrl_r,
        kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r,
        kb.Key.alt, kb.Key.alt_l, kb.Key.alt_r,
        kb.Key.cmd, kb.Key.cmd_l, kb.Key.cmd_r,
    }
    _MOD_LABELS = {
        kb.Key.ctrl: "ctrl", kb.Key.ctrl_l: "ctrl", kb.Key.ctrl_r: "ctrl",
        kb.Key.shift: "shift", kb.Key.shift_l: "shift", kb.Key.shift_r: "shift",
        kb.Key.alt: "alt", kb.Key.alt_l: "alt", kb.Key.alt_r: "alt",
        kb.Key.cmd: "cmd", kb.Key.cmd_l: "cmd", kb.Key.cmd_r: "cmd",
    }

    def on_press(key):
        if key == kb.Key.esc:
            done.set()
            return False
        pressed.add(key)

    def on_release(key):
        if key == kb.Key.esc or done.is_set():
            return False
        # Fire when a non-modifier key is released while modifiers are held
        if key not in _MOD_NAMES and pressed:
            parts: list[str] = []
            seen_mods: set[str] = set()
            for k in sorted(pressed, key=lambda x: str(x)):
                label = _MOD_LABELS.get(k)
                if label and label not in seen_mods:
                    parts.append(label)
                    seen_mods.add(label)
            # The main key
            if hasattr(key, "char") and key.char:
                parts.append(key.char.lower())
            elif hasattr(key, "name") and key.name:
                parts.append(key.name.lower())
            else:
                parts.append(str(key))
            captured.clear()
            captured.append("+".join(parts))
            done.set()
            return False
        pressed.discard(key)

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    done.wait(timeout=15)
    listener.stop()

    if not captured:
        console.print("  [hint]cancelled.[/hint]")
        _pause()
        return

    new_hotkey = captured[0]
    console.print(f"  [hint]Captured:[/hint]  [accent2]{new_hotkey}[/accent2]\n")

    confirm = sel.select(
        "",
        [
            sel.Choice("Save this hotkey", True),
            sel.Choice("Cancel", False),
        ],
        back_value=False,
        show_footer=False,
    )
    if confirm:
        config.hotkey = new_hotkey
        cfg_mod.save(config)
        _saved_flash()
        console.print(
            "  [hint]Restart the listen daemon for the change to take effect.[/hint]"
        )
        _pause()


def _settings_edit_system_prompt(config: Config) -> None:
    _render_home(config, subtitle="Settings › Behavior › System prompt", compact=True)
    console.print(
        Panel(
            Text(config.system_prompt, style="value"),
            title="[accent2]current system prompt[/accent2]",
            title_align="left",
            border_style="hint",
            padding=(1, 2),
        )
    )
    new = questionary.text(
        "New system prompt (Enter on an empty line to cancel):",
        style=QSTYLE,
        multiline=True,
    ).ask()
    if new and new.strip():
        config.system_prompt = new.strip()
        cfg_mod.save(config)
        _saved_flash()
    _pause()


# ──────────────────────────────────────────────────────────────────────────────
# Help submenu
# ──────────────────────────────────────────────────────────────────────────────


def _action_help(config: Config) -> None:
    while True:
        _render_home(config, subtitle="Help & about")
        choices = [
            sel.Choice("Quick start", "quickstart"),
            sel.Choice("Keyboard & permissions", "perms"),
            sel.Choice(
                "Test provider connection",
                "test",
                hint=reformulator.PROVIDER_LABELS[reformulator.active_provider(config)],
            ),
            sel.Choice("System information", "info"),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]
        try:
            choice = sel.select("", choices, back_value="back")
        except KeyboardInterrupt:
            return

        if choice in (None, "back"):
            return
        if choice == "quickstart":
            _show_quickstart(config)
        elif choice == "perms":
            _show_permissions(config)
        elif choice == "test":
            _action_test(config)
        elif choice == "info":
            _action_info(config)


def _show_quickstart(config: Config) -> None:
    console.clear()
    banner(_get_version())
    body = Text.assemble(
        ("voiceprompt runs as a background ", "value"),
        ("daemon", "accent"),
        (" listening for a global hotkey.\n", "value"),
        ("You don't need to come back to this CLI to dictate.\n\n", "value"),
        ("STEPS\n", "section"),
        ("  1. Start the daemon from this menu, or run ", "value"),
        ("voiceprompt listen", "kbd"),
        (" in any terminal.\n", "value"),
        ("  2. Press ", "value"),
        (config.hotkey, "kbd"),
        (" anywhere on your system to start recording.\n", "value"),
        ("  3. Press it again to stop.\n", "value"),
        ("  4. Parakeet transcribes locally; the AI provider refines the prompt.\n", "value"),
        ("  5. The result is pasted into whatever app had focus.\n\n", "value"),
        ("AUTO-START AT LOGIN\n", "section"),
        ("  macOS    launchd plist or Login Items → ", "value"),
        ("voiceprompt listen", "kbd"),
        ("\n", ""),
        ("  Linux    systemd --user service running ", "value"),
        ("voiceprompt listen", "kbd"),
        ("\n", ""),
        ("  Windows  Task Scheduler at logon → ", "value"),
        ("voiceprompt listen", "kbd"),
    )
    console.print(_panel(body, title="Quick start"))
    _pause()


def _show_permissions(config: Config) -> None:
    console.clear()
    banner(_get_version())
    body = Text.assemble(
        ("RECORDING & PASTING (macOS)\n", "section"),
        ("  System Settings → Privacy & Security → ", "value"),
        ("Microphone\n", "accent"),
        ("                                          records audio\n", "hint"),
        ("  System Settings → Privacy & Security → ", "value"),
        ("Input Monitoring\n", "accent"),
        ("                                          listens for the global hotkey\n", "hint"),
        ("  System Settings → Privacy & Security → ", "value"),
        ("Accessibility\n", "accent"),
        ("                                          simulates Cmd+V into focus\n\n", "hint"),
        ("HOTKEY\n", "section"),
        ("  Default ", "value"),
        (config.hotkey, "kbd"),
        (".  Change it under Settings → Hotkey.\n", "value"),
        ("  Press it once to start recording, again to stop.\n\n", "value"),
        ("LINUX\n", "section"),
        ("  Install ", "value"),
        ("xdotool", "kbd"),
        (" (X11) or ", "value"),
        ("wtype", "kbd"),
        (" (Wayland) for auto-paste.\n", "value"),
        ("  Some hotkey daemons may need uinput access (see pynput docs).\n", "value"),
    )
    console.print(_panel(body, title="Keyboard & permissions"))
    _pause()


# ──────────────────────────────────────────────────────────────────────────────
# History
# ──────────────────────────────────────────────────────────────────────────────


def _action_history(config: Config) -> None:
    """Browse, replay, and clear past dictations."""
    while True:
        entries = history.read(limit=20)
        _render_home(config, subtitle="History", compact=True)

        if not entries:
            console.print(
                "  [hint]no dictations yet — press any key to go back.[/hint]"
            )
            _pause()
            return

        choices: list = []
        for i, entry in enumerate(entries):
            preview = entry.prompt.splitlines()[0] if entry.prompt else ""
            if not preview:
                preview = "(empty)"
            elif len(preview) > 60:
                preview = preview[:57] + "…"
            ts = _format_relative_ts(entry.ts)
            choices.append(
                sel.Choice(preview, i, hint=f"{ts}  ·  {entry.provider}")
            )

        choices += [
            sel.Separator(),
            sel.Choice(
                "Clear all history", "clear", hint=f"{history.count()} total"
            ),
            sel.Choice("Back", "back"),
        ]

        try:
            choice = sel.select(
                "Recent dictations",
                choices,
                back_value="back",
                show_footer=True,
            )
        except KeyboardInterrupt:
            return

        if choice in (None, "back"):
            return
        if choice == "clear":
            confirm = sel.select(
                "Clear all history? This cannot be undone.",
                [
                    sel.Choice("Yes, delete every entry", True),
                    sel.Choice("Cancel", False),
                ],
                default=False,
                back_value=False,
                show_footer=False,
            )
            if confirm:
                history.clear()
                console.print("\n  [ok]history cleared.[/ok]")
                _pause()
            continue

        # Drill into a single entry.
        _action_history_entry(config, entries[choice])


def _action_history_entry(config: Config, entry: history.Entry) -> None:
    """Show a single history entry and offer copy / paste actions."""
    while True:
        _render_home(config, subtitle="History › entry", compact=True)
        meta = (
            f"  [hint]{_format_relative_ts(entry.ts)}  ·  {entry.provider} · "
            f"{entry.model}  ·  {entry.language}[/hint]"
        )
        console.print(meta)
        console.print()
        console.print(
            Panel(
                Text(entry.transcript or "(empty)", style="value"),
                border_style="subtle",
                title="[accent2]transcript[/accent2]",
                title_align="left",
                padding=(0, 2),
            )
        )
        console.print(
            Panel(
                Text(entry.prompt or "(empty)", style="value"),
                border_style="ok",
                title="[ok]refined prompt[/ok]",
                title_align="left",
                padding=(1, 2),
            )
        )

        choices = [
            sel.Choice("Copy prompt to clipboard", "copy"),
            sel.Choice("Paste into focused window", "paste"),
            sel.Separator(),
            sel.Choice("Back", "back"),
        ]
        try:
            choice = sel.select("", choices, back_value="back", show_footer=False)
        except KeyboardInterrupt:
            return
        if choice in (None, "back"):
            return
        if choice == "copy":
            if clipboard_copy(entry.prompt):
                console.print("\n  [ok]copied to clipboard[/ok]")
            else:
                console.print(
                    "\n  [warn]Could not copy.[/warn] "
                    "[hint]Install xclip / xsel on Linux.[/hint]"
                )
            _pause()
            continue
        if choice == "paste":
            if not clipboard_copy(entry.prompt):
                console.print("\n  [warn]Could not copy to clipboard.[/warn]")
                _pause()
                continue
            if inject.paste():
                console.print("\n  [ok]pasted.[/ok]")
                _pause()
                return
            console.print(
                "\n  [warn]Could not paste automatically.[/warn] "
                f"[hint]{inject.missing_tool_hint()}[/hint]"
            )
            _pause()


def _format_relative_ts(ts: str) -> str:
    """Format an ISO 8601 UTC timestamp as a friendly relative time."""
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ts or "?"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - dt).total_seconds()
    if delta < 30:
        return "just now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86_400:
        return f"{int(delta // 3600)}h ago"
    if delta < 7 * 86_400:
        return f"{int(delta // 86_400)}d ago"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


# ──────────────────────────────────────────────────────────────────────────────
# Connection test
# ──────────────────────────────────────────────────────────────────────────────


def _action_test(config: Config, *, pause_after: bool = True) -> None:
    console.print()
    started = time.monotonic()
    provider_label = reformulator.PROVIDER_LABELS[reformulator.active_provider(config)]
    short = reformulator.short_model(config)
    with console.status(f"[brand]pinging {short}…[/brand]", spinner="dots"):
        try:
            reformulator.quick_test(config)
            elapsed = time.monotonic() - started
            console.print(
                Panel(
                    Text.assemble(
                        ("[ok] ", "ok"),
                        (f"{provider_label} · {short}", "ok2"),
                    ),
                    subtitle=f"[hint]{elapsed:.2f}s[/hint]",
                    subtitle_align="right",
                    border_style="ok",
                    padding=(1, 2),
                    expand=False,
                )
            )
        except reformulator.AuthError as e:
            console.print(
                _error_panel("Authentication failed", str(e), hint="Check the API key in Settings.")
            )
        except reformulator.QuotaExceededError as e:
            hint = (
                f"Wait ~{e.retry_after:.0f}s or switch models in Settings."
                if e.retry_after
                else "Try again in a moment, or switch models in Settings."
            )
            console.print(_error_panel("Quota exceeded", str(e), hint=hint))
        except reformulator.ProviderError as e:
            console.print(_error_panel("Provider error", str(e)))
    if pause_after:
        _pause()


# ──────────────────────────────────────────────────────────────────────────────
# Listen daemon
# ──────────────────────────────────────────────────────────────────────────────


def _action_listen(
    config: Config,
    *,
    hotkey_override: str | None = None,
    no_paste: bool = False,
) -> None:
    """Run the global-hotkey daemon loop. Shared by the menu and ``voiceprompt listen``.

    The daemon never steals focus, so the refined prompt is pasted into whichever
    window the user was already using when they pressed the hotkey.
    """
    from voiceprompt import hotkey as hk  # noqa: PLC0415

    if not hk.is_supported():
        console.print(
            "  [err]Global hotkey is not supported in this environment.[/err] "
            f"[hint]{hk.import_error_hint()}[/hint]"
        )
        _pause()
        return

    combo = hotkey_override or config.hotkey
    ctx = hk.HotkeyContext()
    try:
        listener = hk.listen(combo, ctx)
    except hk.HotkeyError as e:
        console.print(f"  [err]Could not register hotkey:[/err] {e}")
        _pause()
        return

    console.clear()
    banner(_get_version())
    console.print(_panel(
        Text.assemble(
            ("Hotkey active · ", "ok"),
            (combo, "accent"),
            ("\n\n", ""),
            ("Press the hotkey from any app to start recording, then again to stop.\n", "value"),
            ("The refined prompt is pasted into whichever window has focus.\n", "value"),
            ("Ctrl+C in this window quits the daemon.", "hint"),
        ),
        title="Listening",
    ))

    try:
        while True:
            ctx.start_event.wait()
            ctx.start_event.clear()

            console.clear()
            banner(_get_version())
            console.print(
                _panel(
                    Text.assemble(("hotkey  ", "hint"), (combo, "accent")),
                    title="Recording",
                )
            )

            _action_dictate(
                config,
                paste=not no_paste,
                exit_after=True,
                hotkey_ctx=ctx,
            )

            console.print(
                f"\n  [hint]ready · press [/hint][accent2]{combo}[/accent2]"
                f"[hint] to record again, or Ctrl+C here to quit.[/hint]"
            )
    except KeyboardInterrupt:
        console.print("\n  [hint]daemon stopped.[/hint]\n")
    finally:
        with contextlib.suppress(Exception):
            listener.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Single-shot dictation cycle
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class _RecordingResult:
    """Intermediate result from the recording phase."""

    wav_path: Path
    duration: float
    peak: int
    elapsed: float


def _record_audio(
    config: Config, *, hotkey_ctx: object | None = None,
) -> _RecordingResult | None:
    """Record audio from the microphone, validate it, and return the WAV path.

    Returns ``None`` (and prints diagnostics) when the recording is cancelled,
    too short, silent, or the microphone cannot be opened.
    """
    rec = recorder.Recorder(sample_rate=config.sample_rate)

    started = time.monotonic()
    try:
        rec.start()
    except recorder.NoInputDeviceError:
        console.print("  [err][!] No audio input found.[/err]")
        return None
    except Exception as e:  # noqa: BLE001
        console.print(f"  [err][!] Could not start recording:[/err] {e}")
        return None

    committed = viz.record_visual(rec, hotkey_ctx=hotkey_ctx)

    result = rec.stop()
    if not committed:
        console.print("  [hint]recording cancelled.[/hint]")
        if result is not None:
            with contextlib.suppress(OSError):
                result[0].unlink(missing_ok=True)
        return None
    if result is None:
        console.print("  [warn]Recording too short. Try again.[/warn]")
        return None

    wav_path, duration, peak = result
    elapsed = time.monotonic() - started
    console.print(
        f"  [hint]captured[/hint] [value]{duration:.1f}s[/value]   "
        f"[hint]peak[/hint] {_peak_bar(peak)} "
        f"[value]{peak}[/value][hint]/32767[/hint]"
    )

    if peak < 50:
        console.print()
        console.print(
            _error_panel(
                "Silent audio",
                f"peak = {peak}",
                hint=(
                    "Common causes:\n"
                    "  · the terminal does not have microphone permission\n"
                    "  · the input device is muted or disconnected\n"
                    "  · another app is using the microphone exclusively\n\n"
                    "macOS:   System Settings → Privacy & Security → Microphone\n"
                    "Linux:   check with `arecord -l`\n"
                    "Windows: Privacy → Microphone → allow desktop apps"
                ),
            )
        )
        with contextlib.suppress(OSError):
            wav_path.unlink(missing_ok=True)
        return None

    if peak < 500:
        console.print(
            f"  [warn][!] Audio is low[/warn] "
            f"[hint](peak {peak}). Speak closer to the mic.[/hint]"
        )

    return _RecordingResult(wav_path=wav_path, duration=duration, peak=peak, elapsed=elapsed)


def _transcribe_audio(config: Config, wav_path: Path) -> str | None:
    """Run local STT with Parakeet. Returns the transcript or ``None`` on failure."""
    first_load = not transcriber.is_model_cached(config.transcription_model)
    short_name = _short_transcription_model(config.transcription_model)
    spinner_msg = (
        f"[brand]loading parakeet · {short_name}…[/brand]"
        if first_load
        else f"[brand]transcribing · {short_name}…[/brand]"
    )

    transcript: str | None = None
    with console.status(spinner_msg, spinner="dots"):
        try:
            transcript = transcriber.transcribe(
                wav_path, model_name=config.transcription_model, language=config.language,
            )
        except transcriber.ModelDownloadError as e:
            console.print(_error_panel(
                "Model download failed", str(e),
                hint="Check your internet connection or pick a smaller model.",
            ))
        except transcriber.TranscriptionError as e:
            console.print(_error_panel("Transcription failed", str(e)))

    if not transcript:
        if transcript is not None:
            # transcriber returned an empty string — no speech detected.
            console.print("  [warn]Parakeet did not detect speech. Try again.[/warn]")
        return None

    console.print()
    console.print(
        Panel(
            Text(transcript, style="value"),
            border_style="subtle",
            title="[accent2]transcription[/accent2]",
            title_align="left",
            padding=(0, 2),
        )
    )
    return transcript


@dataclass
class _RefinementResult:
    """Intermediate result from the AI refinement phase."""

    prompt: str
    elapsed: float


def _refine_transcript(config: Config, transcript: str) -> _RefinementResult | None:
    """Send the transcript to the active AI provider for refinement.

    Returns the refined prompt and timing info, or ``None`` on failure.
    """
    provider_label = reformulator.PROVIDER_LABELS[reformulator.active_provider(config)]
    started = time.monotonic()

    final_prompt: str | None = None
    with console.status(
        f"[brand]refining · {reformulator.short_model(config)}…[/brand]",
        spinner="dots",
    ):
        try:
            final_prompt = reformulator.reformulate_text(transcript, config)
        except reformulator.AuthError as e:
            console.print(_error_panel(
                "Authentication failed", str(e),
                hint="Check your API key in Settings.",
            ))
        except reformulator.QuotaExceededError as e:
            hint = (
                f"Retry in ~{e.retry_after:.0f}s."
                if e.retry_after
                else "Switch models or wait a moment."
            )
            console.print(_error_panel("Quota exceeded", str(e), hint=hint))
        except reformulator.ProviderError as e:
            console.print(_error_panel(f"{provider_label} error", str(e)))

    if final_prompt is None:
        return None
    return _RefinementResult(prompt=final_prompt, elapsed=time.monotonic() - started)


def _deliver_prompt(
    config: Config,
    prompt: str,
    *,
    record_secs: float,
    refine_secs: float,
    total_secs: float,
    paste: bool,
) -> None:
    """Display the final prompt, copy to clipboard, and optionally paste."""
    word_count = len(prompt.split())
    meta = (
        f"[hint]{record_secs:.1f}s rec · "
        f"{refine_secs:.1f}s {reformulator.active_provider(config)} · "
        f"{total_secs:.1f}s total · "
        f"{word_count} words[/hint]"
    )
    console.print()
    console.print(
        Panel(
            Text(prompt, style="value"),
            border_style="ok",
            title="[ok]refined prompt[/ok]",
            subtitle=meta,
            subtitle_align="right",
            title_align="left",
            padding=(1, 2),
        )
    )

    copied = False
    if config.auto_copy_clipboard:
        copied = clipboard_copy(prompt)
        if copied:
            if not paste:
                console.print(
                    "\n  [ok]copied to clipboard[/ok]   "
                    "[hint]paste with [/hint][kbd]⌘V[/kbd][hint] / [/hint][kbd]Ctrl+V[/kbd]"
                )
        else:
            console.print(
                "\n  [warn]Could not copy.[/warn] "
                "[hint]Install xclip / xsel on Linux, or select the text manually.[/hint]"
            )

    if copied and paste:
        ok = inject.paste()
        if not ok:
            console.print(
                "\n  [warn]Could not paste automatically.[/warn] "
                f"[hint]{inject.missing_tool_hint()}[/hint]"
            )


def _action_dictate(
    config: Config,
    *,
    paste: bool = False,
    exit_after: bool = False,
    hotkey_ctx=None,
) -> None:
    """Run a dictation cycle: record → transcribe → refine → deliver.

    ``paste=True`` simulates ⌘V / Ctrl+V into whichever window has focus when
    the cycle finishes. The listen daemon enables it; the menu's "Dictate once"
    leaves it off (clipboard only).
    """
    console.print()

    # Make sure the transcription model is on disk before recording — downloading
    # mid-dictation would block for minutes and waste the captured audio.
    if not _ensure_transcription_model_downloaded(config.transcription_model, ask_confirm=True):
        if not exit_after:
            _pause()
        return

    started = time.monotonic()

    # 1. Record ───────────────────────────────────────────────────────────────
    recording = _record_audio(config, hotkey_ctx=hotkey_ctx)
    if recording is None:
        if not exit_after:
            _pause()
        return

    # 2. Transcribe ───────────────────────────────────────────────────────────
    transcript = _transcribe_audio(config, recording.wav_path)
    if transcript is None:
        with contextlib.suppress(OSError):
            recording.wav_path.unlink(missing_ok=True)
        if not exit_after:
            _pause()
        return

    # 3. Refine ───────────────────────────────────────────────────────────────
    refinement = _refine_transcript(config, transcript)
    with contextlib.suppress(OSError):
        recording.wav_path.unlink(missing_ok=True)
    if refinement is None:
        if not exit_after:
            _pause()
        return

    # 4. Deliver ──────────────────────────────────────────────────────────────
    _deliver_prompt(
        config,
        refinement.prompt,
        record_secs=recording.elapsed,
        refine_secs=refinement.elapsed,
        total_secs=time.monotonic() - started,
        paste=paste,
    )

    # 5. History ──────────────────────────────────────────────────────────────
    # Best-effort logging — failures here must never break the dictation flow.
    if config.history_enabled:
        history.log(
            transcript=transcript,
            prompt=refinement.prompt,
            provider=reformulator.active_provider(config),
            model=reformulator.active_model(config),
            language=config.language,
            record_secs=recording.elapsed,
            refine_secs=refinement.elapsed,
            max_entries=config.history_max_entries,
        )

    if not exit_after:
        _pause()


# ──────────────────────────────────────────────────────────────────────────────
# System info
# ──────────────────────────────────────────────────────────────────────────────


def _action_info(config: Config) -> None:
    sys_table = Table(show_header=False, box=None, padding=(0, 2))
    sys_table.add_column(style="hint", justify="right")
    sys_table.add_column(style="value")
    sys_table.add_row("version", _get_version())
    sys_table.add_row("python", sys.version.split()[0])
    sys_table.add_row("platform", sys.platform)
    sys_table.add_row("config", str(cfg_mod.config_path()))

    provider = reformulator.active_provider(config)
    cfg_table = Table(show_header=False, box=None, padding=(0, 2))
    cfg_table.add_column(style="hint", justify="right")
    cfg_table.add_column(style="value")
    cfg_table.add_row("provider", reformulator.PROVIDER_LABELS[provider])
    cfg_table.add_row("model", reformulator.short_model(config))
    cfg_table.add_row("transcription", _short_transcription_model(config.transcription_model))
    cfg_table.add_row("language", config.language)
    cfg_table.add_row("hotkey", config.hotkey)
    cfg_table.add_row("sample rate", f"{config.sample_rate} Hz")
    cfg_table.add_row("anthropic key", _key_state(config.anthropic_api_key))
    cfg_table.add_row("ollama key", _key_state(config.ollama_api_key))
    cfg_table.add_row("gemini key", _key_state(config.gemini_api_key))
    cfg_table.add_row("github key", _key_state(config.github_models_token))

    console.print()
    console.print(
        Panel(sys_table, border_style="hint", title="[accent2]system[/accent2]", title_align="left")
    )
    console.print(
        Panel(
            cfg_table,
            border_style="hint",
            title="[accent2]configuration[/accent2]",
            title_align="left",
        )
    )

    try:
        devs = recorder.list_input_devices()
        if devs:
            dev_table = Table(show_header=False, box=None, padding=(0, 1))
            dev_table.add_column(style="brand2", width=3)
            dev_table.add_column(style="hint", justify="right", width=4)
            dev_table.add_column(style="value")
            dev_table.add_column(style="hint")
            for d in devs:
                marker = "›" if d["default"] else " "
                dev_table.add_row(marker, str(d["index"]), d["name"], f"{d['channels']}ch")
            console.print(
                Panel(
                    dev_table,
                    border_style="hint",
                    title="[accent2]microphones[/accent2]",
                    title_align="left",
                )
            )
    except Exception as e:  # noqa: BLE001
        console.print(f"  [warn]Could not list devices: {e}[/warn]")

    _pause()


# ──────────────────────────────────────────────────────────────────────────────
# Status panel + helpers
# ──────────────────────────────────────────────────────────────────────────────


def _render_home(
    config: Config,
    *,
    subtitle: str | None = None,
    compact: bool = False,
) -> None:
    """Render the header and flush atomically (no blank-frame flicker).

    ``compact=True`` renders a single status line instead of the full panel.
    Use it in drill-down sub-menus to reduce visual weight.
    """
    buf = console.capture()
    with buf:
        if compact:
            _render_status_compact(config, subtitle=subtitle)
        else:
            banner(_get_version())
            _render_status(config, subtitle=subtitle)

    sys.stdout.write(f"\033[H\033[J{buf.get()}")
    sys.stdout.flush()


def _saved_flash() -> None:
    """Brief confirmation shown after persisting a setting."""
    console.print("  [ok]✓[/ok] [hint]saved[/hint]")


def _render_status(config: Config, *, subtitle: str | None = None) -> None:
    """Compact status block: state, provider, transcription, hotkey, language."""
    state_text = (
        Text("ready", style="ok")
        if config.is_configured
        else Text("setup needed", style="warn")
    )

    provider = reformulator.active_provider(config)
    provider_text = Text.assemble(
        Text(reformulator.PROVIDER_LABELS[provider], style="value"),
        Text("  ·  ", style="hint"),
        Text(reformulator.short_model(config), style="accent2"),
    )

    transcription_cached = transcriber.is_model_on_disk(config.transcription_model)
    transcription_text = Text.assemble(
        Text(_short_transcription_model(config.transcription_model), style="value"),
        Text("  ·  ", style="hint"),
        Text("cached", style="ok2") if transcription_cached else Text("not downloaded", style="warn"),
    )

    grid = Table.grid(padding=(0, 2), expand=False)
    grid.add_column(style="hint", justify="right")
    grid.add_column()
    grid.add_row("state", state_text)
    grid.add_row("provider", provider_text)
    grid.add_row("transcription", transcription_text)
    grid.add_row("hotkey", Text(config.hotkey, style="value"))
    grid.add_row("language", Text(config.language, style="value"))

    title_text = "[accent2]status[/accent2]"
    if subtitle:
        title_text = f"[accent2]status[/accent2] [hint]·[/hint] [brand]{subtitle}[/brand]"

    console.print(
        Panel(
            grid,
            border_style="hint",
            title=title_text,
            title_align="left",
            padding=(0, 2),
            expand=False,
        )
    )
    console.print()


def _render_status_compact(config: Config, *, subtitle: str | None = None) -> None:
    """Single-line status bar for drill-down sub-menus."""
    provider = reformulator.active_provider(config)
    state = "[ok]ready[/ok]" if config.is_configured else "[warn]setup needed[/warn]"
    model = reformulator.short_model(config)
    label = reformulator.PROVIDER_LABELS[provider]
    version = _get_version()

    breadcrumb = f"  [hint]voiceprompt[/hint] [hint]v{version}[/hint]"
    if subtitle:
        breadcrumb += f"  [hint]·[/hint]  [brand]{subtitle}[/brand]"
    breadcrumb += (
        f"  [hint]·[/hint]  [value]{label}[/value] [hint]·[/hint] "
        f"[accent2]{model}[/accent2]  [hint]·[/hint]  {state}"
    )

    console.print(breadcrumb)
    console.print()


def _panel(body, *, title: str) -> Panel:
    return Panel(
        body,
        border_style="brand",
        title=f"[brand]{title}[/brand]",
        title_align="left",
        padding=(1, 2),
        expand=False,
    )


def _error_panel(title: str, body: str, *, hint: str | None = None) -> Panel:
    text = Text(body, style="value")
    if hint:
        text.append("\n\n")
        text.append(hint, style="hint")
    return Panel(
        text,
        border_style="err",
        title=f"[err][!] {title}[/err]",
        title_align="left",
        padding=(1, 2),
        expand=False,
    )


def _key_state(value: str) -> str:
    return "configured" if value.strip() else "not set"


def _pause() -> None:
    console.print()
    with contextlib.suppress(KeyboardInterrupt):
        questionary.press_any_key_to_continue("Press any key to continue…").ask()


# ──────────────────────────────────────────────────────────────────────────────
# Provider key prompt (shared by the wizard and the settings menu)
# ──────────────────────────────────────────────────────────────────────────────


_KEY_PROMPTS = {
    "claude": (
        "Anthropic API key",
        "https://console.anthropic.com/settings/keys",
        claude.looks_like_anthropic_key,
        "the key does not start with 'sk-ant-' like Anthropic keys usually do",
    ),
    "ollama": (
        "Ollama Cloud API key",
        "https://ollama.com/settings/keys",
        ollama.looks_like_ollama_key,
        "the key looks unusually short",
    ),
    "gemini": (
        "Google Gemini API key",
        "https://aistudio.google.com/apikey",
        gemini.looks_like_gemini_key,
        "the key does not start with 'AIza' like AI Studio keys usually do",
    ),
    "github_models": (
        "GitHub token for GitHub Models",
        "https://github.com/settings/personal-access-tokens",
        github_models.looks_like_github_token,
        "the token does not look like a GitHub PAT/token",
    ),
}


def _set_api_key(config: Config, provider: str, *, intro: bool) -> bool:
    """Prompt for the API key of ``provider`` and persist it. Returns True on success."""
    title, url, validator, warn_text = _KEY_PROMPTS[provider]
    body = Text.assemble(
        ("Get a key at:\n", "value"),
        (f"  {url}\n\n", "accent2"),
        ("It is saved locally at\n", "hint"),
        (f"  {cfg_mod.config_path()}", "subtle"),
    )
    console.print(_panel(body, title=("2.  " + title) if intro else title))
    console.print()

    try:
        key = sel.password_input("Paste your API key:")
    except KeyboardInterrupt:
        return False
    if not key:
        return False

    cleaned = key.strip()
    if not validator(cleaned):
        console.print(f"  [warn][!] Warning:[/warn] [hint]{warn_text}. Saving anyway.[/hint]")

    if provider == "ollama":
        config.ollama_api_key = cleaned
    elif provider == "gemini":
        config.gemini_api_key = cleaned
    elif provider == "github_models":
        config.github_models_token = cleaned
    else:
        config.anthropic_api_key = cleaned
    cfg_mod.save(config)
    console.print(f"  [ok]Saved to[/ok] [hint]{cfg_mod.config_path()}[/hint]")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Misc helpers
# ──────────────────────────────────────────────────────────────────────────────


def _ensure_transcription_model_downloaded(model_name: str, *, ask_confirm: bool) -> bool:
    """Make sure the Parakeet model weights are on disk. Returns False if user cancels."""
    if transcriber.is_model_on_disk(model_name):
        return True

    size = transcriber.model_download_size(model_name) or "around 1.2 GB"
    short = _short_transcription_model(model_name)
    if ask_confirm:
        console.print(
            f"\n  [warn][!] Parakeet model '{short}' is not downloaded yet[/warn] "
            f"[hint]({size}).[/hint]"
        )
        proceed = questionary.confirm(
            f"Download '{short}' now ({size})?",
            default=True,
            style=QSTYLE,
        ).ask()
        if not proceed:
            console.print("  [hint]Cancelled. Pick a different model in Settings.[/hint]")
            return False

    console.print(
        f"  [brand]Downloading parakeet '{short}' ({size}) — first run, this can take a while…[/brand]"
    )
    try:
        transcriber.download_model(model_name)
    except transcriber.ModelDownloadError as e:
        console.print(_error_panel("Download failed", str(e),
                                   hint="Check your internet connection or pick a different model."))
        return False
    console.print(f"  [ok]'{short}' downloaded.[/ok]")
    return True


def _short_transcription_model(model_id: str) -> str:
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def _transcription_model_hint(model_id: str) -> str:
    state = "cached" if transcriber.is_model_on_disk(model_id) else "not downloaded"
    return f"{_short_transcription_model(model_id)} · {state}"


def _peak_bar(peak: int, width: int = 16) -> str:
    """Visual bar of the recording peak. Color shifts as it approaches clipping."""
    ratio = max(0.0, min(1.0, peak / 32767))
    filled = int(round(ratio * width))
    if peak >= 32000:
        color = "err"
    elif peak >= 25000:
        color = "warn"
    elif peak >= 500:
        color = "ok"
    else:
        color = "subtle"
    bar = "█" * filled + "·" * (width - filled)
    return f"[{color}][{bar}][/{color}]"


def _is_float_in_range(s: str, lo: float, hi: float) -> bool | str:
    try:
        v = float(s)
    except ValueError:
        return "Must be a number."
    if not (lo <= v <= hi):
        return f"Must be between {lo} and {hi}."
    return True


def _get_version() -> str:
    try:
        from voiceprompt import __version__  # noqa: PLC0415

        return __version__
    except ImportError:
        return "?"
