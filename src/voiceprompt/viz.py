"""Live recording visualizer: waveform + REC indicator + keybindings.

Renders a compact panel that updates ~20fps while the user records.

Bindings:
  enter / esc / q    -> stop recording (commit, transcribe & paste)
  space              -> pause / resume
  ctrl+c             -> cancel (discard the recording)
"""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from voiceprompt.hotkey import HotkeyContext
from voiceprompt.recorder import Recorder

# 8-level vertical block characters used to draw the waveform.
BARS = "_,-~=^*#"  # ASCII fallback path; not used (kept for reference).
BLOCK_BARS = "▁▂▃▄▅▆▇█"


PT_STYLE = Style.from_dict(
    {
        "rec":      "fg:ansired bold",
        "paused":   "fg:ansiyellow bold",
        "wave":     "fg:ansicyan",
        "wave-hi":  "fg:ansired bold",
        "wave-mid": "fg:ansiyellow",
        "wave-lo":  "fg:ansicyan",
        "wave-zero":"fg:ansibrightblack",
        "label":    "fg:ansibrightblack",
        "time":     "bold",
        "kbd":      "reverse",
        "border":   "fg:ansimagenta",
    }
)


def _waveform(levels: list[int], *, width: int = 40) -> list[tuple[str, str]]:
    """Build a per-character styled waveform (oldest -> newest, padded to `width`)."""
    if not levels:
        levels = [0] * width
    # Pick the latest `width` samples
    if len(levels) > width:
        levels = levels[-width:]
    elif len(levels) < width:
        levels = [0] * (width - len(levels)) + levels

    # Normalize using a soft ceiling so it stays readable even with quiet voices.
    ceiling = max(2000, max(levels) or 1)
    fragments: list[tuple[str, str]] = []
    for v in levels:
        ratio = max(0.0, min(1.0, v / ceiling))
        idx = int(round(ratio * (len(BLOCK_BARS) - 1)))
        ch = BLOCK_BARS[idx]
        if v <= 60:
            style = "class:wave-zero"
        elif ratio >= 0.85:
            style = "class:wave-hi"
        elif ratio >= 0.55:
            style = "class:wave-mid"
        else:
            style = "class:wave-lo"
        fragments.append((style, ch))
    return fragments


def _format_time(secs: float) -> str:
    s = int(secs)
    return f"{s // 60}:{s % 60:02d}"


def record_visual(
    rec: Recorder,
    *,
    width: int = 40,
    hotkey_ctx: HotkeyContext | None = None,
) -> bool:
    """Show the live recording UI. Returns True when stopped normally, False if cancelled.

    The recorder must already be started before calling this.

    `hotkey_ctx`: if provided, registers the prompt_toolkit Application with the
    context so an external thread (the global hotkey listener) can call
    `app.exit(True)` to stop recording remotely. Useful for the listen-mode toggle.
    """
    state = {"cancelled": False}

    def render() -> FormattedText:
        levels = rec.get_levels()
        wave = _waveform(levels, width=width)
        elapsed = _format_time(rec.elapsed())
        peak = rec.latest_peak()

        line: list[tuple[str, str]] = []
        # Top: REC indicator + time
        if rec.is_paused():
            line.append(("class:paused", "  || PAUSED  "))
        else:
            line.append(("class:rec", "  ●  REC  "))
        line.append(("class:time", elapsed))
        line.append(("class:label", "    peak "))
        line.append(("class:time", f"{peak:5d}"))
        line.append(("", "\n\n"))

        # Waveform line
        line.append(("", "  "))
        line.append(("class:border", "│ "))
        line.extend(wave)
        line.append(("class:border", " │"))
        line.append(("", "\n\n"))

        # Footer with keybinds
        line.append(("", "  "))
        line.append(("class:kbd", "enter"))
        line.append(("class:label", " stop    "))
        line.append(("class:kbd", "space"))
        line.append(("class:label", " pause    "))
        line.append(("class:kbd", "ctrl+c"))
        line.append(("class:label", " cancel"))
        return FormattedText(line)

    kb = KeyBindings()

    @kb.add("enter")
    @kb.add("escape")
    @kb.add("q")
    def _(event):
        event.app.exit(result=True)

    @kb.add("space")
    def _(event):  # noqa: ARG001
        if rec.is_paused():
            rec.resume()
        else:
            rec.pause()

    @kb.add("c-c")
    def _(event):
        state["cancelled"] = True
        event.app.exit(result=False)

    control = FormattedTextControl(text=render, focusable=True, show_cursor=False)
    layout = Layout(HSplit([Window(content=control, height=5)]))

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        style=PT_STYLE,
        full_screen=False,
        mouse_support=False,
        refresh_interval=0.05,  # 20fps redraw
    )

    if hotkey_ctx is not None:
        hotkey_ctx.set_running_app(app)
    try:
        result = app.run()
    finally:
        if hotkey_ctx is not None:
            hotkey_ctx.clear_running_app()
    return bool(result) and not state["cancelled"]


def record_headless(rec: Recorder, *, hotkey_ctx: HotkeyContext, max_seconds: float = 600.0) -> bool:
    """Record without a TUI; stop when the global hotkey fires again.

    Used by the listen daemon when it's been started detached from a
    terminal (``voiceprompt start``). prompt_toolkit's input layer cannot
    attach to ``/dev/null``, so the visualizer cannot run in that mode.

    Returns True when the user toggled stop (committed), False when the
    safety cap fired without a stop (still committed — the recording
    should be processed). Currently this function does not support
    cancellation; use ``voiceprompt stop`` to end the daemon entirely if
    something gets stuck.
    """
    hotkey_ctx.stop_event.clear()
    hotkey_ctx.set_headless_recording(True)
    try:
        # The recorder does its own work in a background thread — we just
        # block until the hotkey thread sets the stop event, with a long
        # safety cap so a missed second press can never wedge the daemon.
        return hotkey_ctx.stop_event.wait(timeout=max_seconds)
    finally:
        hotkey_ctx.set_headless_recording(False)
        hotkey_ctx.stop_event.clear()
