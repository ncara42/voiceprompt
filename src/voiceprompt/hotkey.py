"""Global hotkey listener via pynput.

Lets `voiceprompt listen` toggle recording from anywhere on the system without
the user having to change windows.

Permissions on macOS (one-time, the OS will prompt the first time pynput attaches):
  - System Settings -> Privacy & Security -> Input Monitoring
  - System Settings -> Privacy & Security -> Accessibility
Both must include the terminal you launch `voiceprompt listen` from
(Terminal / iTerm2 / Ghostty / Warp...). Without these the listener silently
no-ops on every press.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

# pynput is platform-specific; import errors should surface a clean message
# when the user runs `voiceprompt listen`, not when the package is imported.
try:
    from pynput import keyboard  # type: ignore[import-not-found]

    _PYNPUT_OK = True
    _PYNPUT_ERR: Exception | None = None
except Exception as e:  # noqa: BLE001
    keyboard = None  # type: ignore[assignment]
    _PYNPUT_OK = False
    _PYNPUT_ERR = e


_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "meta": "cmd",
}

# Multi-character key tokens pynput expects in <angle brackets>.
_NAMED_KEYS = {
    "space",
    "enter",
    "return",
    "tab",
    "esc",
    "escape",
    "backspace",
    "delete",
    "home",
    "end",
    "page_up",
    "page_down",
    "left",
    "right",
    "up",
    "down",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
}


def parse_hotkey(spec: str) -> str:
    """Convert a friendly spec like 'ctrl+space' to pynput's '<ctrl>+<space>'."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    out: list[str] = []
    for p in parts:
        if p in _MODIFIER_ALIASES:
            out.append(f"<{_MODIFIER_ALIASES[p]}>")
        elif p in _NAMED_KEYS:
            out.append(f"<{p}>")
        elif len(p) == 1:
            out.append(p)
        else:
            out.append(f"<{p}>")
    return "+".join(out)


class HotkeyContext:
    """Shared state between the pynput listener thread and the main daemon thread."""

    def __init__(self) -> None:
        self.start_event = threading.Event()
        self._current_app: Any | None = None
        self._lock = threading.Lock()

    def set_running_app(self, app: Any) -> None:
        with self._lock:
            self._current_app = app

    def clear_running_app(self) -> None:
        with self._lock:
            self._current_app = None

    def has_running_app(self) -> bool:
        with self._lock:
            return self._current_app is not None

    def on_hotkey(self) -> None:
        """Called from the pynput thread. Toggles between start and stop."""
        with self._lock:
            app = self._current_app
        if app is not None:
            # We're recording -- ask prompt_toolkit to exit cleanly.
            with contextlib.suppress(Exception):
                app.exit(result=True)
        else:
            self.start_event.set()


class HotkeyError(Exception):
    pass


def is_supported() -> bool:
    return _PYNPUT_OK


def import_error_hint() -> str:
    if _PYNPUT_ERR is None:
        return ""
    return f"pynput no se pudo cargar: {_PYNPUT_ERR}"


def listen(combo: str, ctx: HotkeyContext):
    """Start a global hotkey listener. Returns the listener (call .stop() to stop)."""
    if not _PYNPUT_OK:
        raise HotkeyError(import_error_hint())
    pt_combo = parse_hotkey(combo)
    try:
        listener = keyboard.GlobalHotKeys({pt_combo: ctx.on_hotkey})  # type: ignore[union-attr]
        listener.start()
    except Exception as e:  # noqa: BLE001
        raise HotkeyError(f"Could not register hotkey '{combo}' ({pt_combo}): {e}") from e
    return listener


def listen_simple(combo: str, on_press: Callable[[], None]):
    """Variant for one-shot callbacks (no toggle). Used when you don't need a context."""
    if not _PYNPUT_OK:
        raise HotkeyError(import_error_hint())
    pt_combo = parse_hotkey(combo)
    try:
        listener = keyboard.GlobalHotKeys({pt_combo: on_press})  # type: ignore[union-attr]
        listener.start()
    except Exception as e:  # noqa: BLE001
        raise HotkeyError(f"Could not register hotkey '{combo}' ({pt_combo}): {e}") from e
    return listener
